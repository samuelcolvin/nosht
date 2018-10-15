import asyncio
import logging
from datetime import datetime
from time import time
from typing import Sequence

import pytz
from aiohttp import BasicAuth, ClientResponse, ClientSession, ClientTimeout
from aiohttp.hdrs import METH_GET, METH_POST, METH_PUT
from arq import concurrent

from .actions import ActionTypes
from .actor import BaseActor
from .settings import Settings
from .utils import RequestError, display_cash, lenient_json

logger = logging.getLogger('nosht.donorfy')


class DonorfyClient:
    def __init__(self, settings: Settings, loop):
        self._settings = settings
        self._client = ClientSession(
            timeout=ClientTimeout(total=30),
            loop=loop,
            auth=BasicAuth('nosht', settings.donorfy_access_key),
        )

    async def close(self):
        await self._client.close()

    async def get(self, path, *, allowed_statuses: Sequence[int]=(200,), data=None, params=None):
        return await self._request(METH_GET, path, allowed_statuses, data, params)

    async def put(self, path, *, allowed_statuses: Sequence[int]=(200,), data=None):
        return await self._request(METH_PUT, path, allowed_statuses, data)

    async def post(self, path, *, allowed_statuses: Sequence[int]=(200, 201), data=None):
        return await self._request(METH_POST, path, allowed_statuses, data)

    async def _request(self, method, path, allowed_statuses, data, params=None) -> ClientResponse:
        assert path.startswith('/'), path
        full_path = self._settings.donorfy_api_root + self._settings.donorfy_api_key + path
        start = time()
        try:
            async with self._client.request(method, full_path, params=params, json=data) as r:
                response_text = await r.text()
        except TimeoutError:  # pragma: no cover
            logger.warning('timeout %s %s', method, path)
            raise

        time_taken = time() - start

        if r.status not in allowed_statuses:
            data = {
                'request_real_url': str(r.request_info.real_url),
                'request_headers': dict(r.request_info.headers),
                'request_method': method,
                'request_data': data,
                'response_status': r.status,
                'response_headers': dict(r.headers),
                'response_content': lenient_json(response_text),
                'time_taken': time_taken,
            }
            # debug(data)
            logger.warning('%s %s > %d unexpected response', method, r.request_info.real_url, r.status, extra={
                'fingerprint': ['donorfy', r.request_info.real_url, str(r.status)],
                'data': data
            })
            raise RequestError(r.status, full_path)
        else:
            logger.info('successful request %s %s > %d (%0.2fs)', method, path, r.status, time_taken)
            return r


class DonorfyActor(BaseActor):
    async def startup(self):
        await super().startup()
        if self.settings.donorfy_api_key:
            logger.info('donorfy api key present, submitting data to donorfy')
            self.client = DonorfyClient(self.settings, self.loop)
        else:
            logger.info('donorfy api key not set, not submitting data to donorfy')

    @concurrent
    async def host_signuped(self, user_id):
        if not self.client:
            return

        constituent_id = await self._get_or_create_constituent(user_id, 'Events.HUF')

        await self.client.post(f'/constituents/{constituent_id}/AddActiveTags',
                               data='Hosting and helper volunteers_host')

    @concurrent
    async def event_created(self, event_id):
        if not self.client:
            return

        async with self.pg.acquire() as conn:
            evt = await conn.fetchrow(
                """
                select
                  start_ts, duration, cat.slug, location_name, ticket_limit, short_description, long_description,
                  event_link(cat.slug, e.slug, e.public, $2) AS link, cat.slug as cat_slug, co.currency,
                  host as host_user_id, host_user.email as host_email
                from events e
                join categories cat on e.category = cat.id
                join companies co on cat.company = co.id
                join users host_user on e.host = host_user.id
                where e.id=$1
                """,
                event_id, self.settings.auth_key
            )
            created = await conn.fetchval("select ts from actions where event=$1 and type='create-event'", event_id)
            prices = await conn.fetch(
                'select price from ticket_types where event=$1 and active is true and price is not null',
                event_id
            )
        start_ts = evt['start_ts'].astimezone(pytz.utc)
        if not evt['duration']:
            start_ts = start_ts.date()

        evt = dict(evt)
        evt['price_text'] = ', '.join(display_cash(r[0], evt['currency']) for r in prices) or 'free'
        data = dict(
            ActivityType='Event Hosted',
            ActivityDate=format_dt(start_ts),
            Campaign=evt['cat_slug'] + '-host',
            Notes=(
                'URL: {link}\n'
                'location: {location_name}\n'
                'ticket limit: {ticket_limit}\n'
                'price: price_text\n'
                'description: {long_description}'
            ).format(**evt),
            Code1=evt['link'],
            Code2=evt['location_name'],
            Code3=evt['short_description'],
            Number1=evt['ticket_limit'],
            Date1=format_dt(created),
            Date2=format_dt(start_ts),
        )
        for i, r in enumerate(prices, start=2):
            data[f'Number{i}'] = float(r[0])

        constituent_id = await self._get_constituent(user_id=evt['host_user_id'], email=evt['host_email'])
        if constituent_id:
            data['ExistingConstituentId'] = constituent_id
        await self.client.post('/activities', data=data)

    @concurrent
    async def tickets_booked(self, action_id):
        if not self.client:
            return

        async with self.pg.acquire() as conn:
            buyer_user_id = await self.pg.fetchval('select user_id from actions where id=$1', action_id)

            action_ts, event_ts, duration, action_type, cat_name, cat_slug, event_slug, currency = await conn.fetchrow(
                """
                select a.ts as action_ts, e.start_ts, e.duration, a.type, cat.name, cat.slug, e.slug, currency
                from actions a
                join events as e on a.event = e.id
                join categories cat on e.category = cat.id
                join companies co on cat.company = co.id
                where a.id=$1
                """,
                action_id
            )
            if not duration:
                event_ts = event_ts.date()

            tickets = await conn.fetch(
                """
                select
                  u.id as user_id, u.email,
                  coalesce(t.first_name, u.first_name) as first_name,
                  coalesce(t.last_name, u.last_name) as last_name,
                  t.extra_info,
                  t.price
                from tickets t
                left join users u on t.user_id = u.id
                where t.booked_action = $1
                """,
                action_id
            )
        ticket_count = len(tickets)
        campaign = f'{cat_slug}-guest'
        buyer_constituent_id = await self._get_or_create_constituent(buyer_user_id, campaign)

        async def create_ticket_constituent(row):
            user_id, email, first_name, last_name, extra_info, ticket_price = row
            if not user_id and not email:
                return

            if user_id == buyer_user_id:
                constituent_id = buyer_constituent_id
            else:
                constituent_id = await self._get_constituent(user_id=user_id, email=email)

            if not constituent_id:
                return

            await self.client.post('/activities', data=dict(
                ExistingConstituentId=constituent_id,
                ActivityType='Event Booked',
                ActivityDate=format_dt(action_ts),
                Campaign=campaign,
                Notes=extra_info,
                Code1=buyer_user_id,
                Number1=float(ticket_price or 0),
                Number2=ticket_count,
                YesNo1=user_id == buyer_user_id,
                Date1=format_dt(event_ts)
            ))

        await asyncio.gather(*[create_ticket_constituent(r) for r in tickets])

        if action_type == ActionTypes.book_free_tickets:
            return

        price, extra = await self.pg.fetchrow(
            'select sum(price), sum(extra_donated) from tickets where booked_action = $1',
            action_id,
        )
        price = float(price)
        extra = float(extra or 0)
        r = await self.client.post('/transactions', data=dict(
            ConnectedConstituentId=buyer_constituent_id,
            ExistingConstituentId=buyer_constituent_id,
            Channel=f'nosht-{cat_slug}',
            Currency=currency,
            Campaign=f'{cat_slug}-guest',
            PaymentMethod='Payment Card via Stripe' if action_type == ActionTypes.buy_tickets else 'Offline Payment',
            Product='Event Ticket(s)',
            Fund='Unrestricted General',
            Department='200 Fund Raising Income',
            BankAccount='Main Account',
            DatePaid=format_dt(action_ts),
            Amount=price + extra,
            Acknowledgement=f'{cat_slug}-thanks',
            AcknowledgementText=f'{cat_name} Donation Thanks',
            Reference=f'Events.HUF:{cat_slug} {event_slug}',
            AddGiftAidDeclaration=False,
            GiftAidClaimed=False,
        ))
        trans_id = (await r.json())['Id']
        if not extra:
            # no need to update or add allocations
            return

        r = await self.client.get(f'/transactions/{trans_id}/Allocations')
        data = await r.json()
        allocation_id = data['AllocationsList'][0]['AllocationId']
        update_data = dict(
            Product='Event Ticket(s)',
            Quantity=ticket_count,
            Amount=price,
            Department='200 Fund Raising Income',
            Fund='Unrestricted General',
            AllocationDate=format_dt(action_ts),
            CanRecoverTax=False,
            Comments=f'{cat_slug} {event_slug}',
            BeneficiaryConstituentId=buyer_constituent_id,
        )
        add_data = dict(
            Product='Donation',
            Quantity=ticket_count,
            Amount=extra,
            Department='200 Fund Raising Income',
            Fund='Unrestricted General',
            AllocationDate=format_dt(action_ts),
            CanRecoverTax=False,
            Comments=f'{cat_slug} {event_slug}',
            BeneficiaryConstituentId=buyer_constituent_id,
        )
        # PUT request seems to be currently broken and returns 405
        await asyncio.gather(
            self.client.put(f'/transactions/{trans_id}/Allocation/{allocation_id}', data=update_data),
            self.client.post(f'/transactions/{trans_id}/AddAllocation', data=add_data),
        )

    @concurrent
    async def donation(self, action_id):
        if not self.client:
            return

        d = await self.pg.fetchrow(
            """
            select a.ts as action_ts, a.user_id, d.amount,
              d.gift_aid, d.first_name, d.last_name, d.address, d.city, d.postcode,
              donopt.id as donopt,
              cat.name as cat_name, cat.slug as cat_slug, currency
            from actions a
            join donations d on a.id = d.action
            join donation_options donopt on d.donation_option = donopt.id
            join categories cat on donopt.category = cat.id
            join companies co on cat.company = co.id
            where a.id=$1
            """,
            action_id
        )
        cat_slug = d['cat_slug']
        campaign = f'{cat_slug}-guest'
        constituent_id = await self._get_or_create_constituent(d['user_id'], campaign)
        await self.client.post('/transactions', data=dict(
            ConnectedConstituentId=constituent_id,
            ExistingConstituentId=constituent_id,
            Channel=f'nosht-{cat_slug}',
            Currency=d['currency'],
            Campaign=campaign,
            PaymentMethod='Payment Card via Stripe',
            Product='Donation',
            Fund='Unrestricted General',
            Department='200 Fund Raising Income',
            BankAccount='Main Account',
            DatePaid=format_dt(d['action_ts']),
            Amount=float(d['amount']),
            Acknowledgement=f'{cat_slug}-thanks',
            AcknowledgementText=f'{d["cat_name"]} Donation Thanks',
            Reference=f'Events.HUF:{cat_slug} donation {d["donopt"]}',
            AddGiftAidDeclaration=d['gift_aid'],
            GiftAidClaimed=d['gift_aid'],
            FirstName=d['first_name'],
            LastName=d['last_name'],
            AddressLine1=d['address'],
            Town=d['city'],
            PostalCode=d['postcode'],
        ))

    @concurrent
    async def update_user(self, user_id, update_user=True, update_marketing=True):
        if not self.client:
            return
        constituent_id = await self._get_constituent(user_id=user_id)
        if not constituent_id:
            return
        first_name, last_name, email, allow_marketing = await self.pg.fetchrow(
            'select first_name, last_name, email, allow_marketing from users where id=$1', user_id)

        requests = []
        if update_user:
            requests.append(
                self.client.put(f'/constituents/{constituent_id}', data=dict(
                    FirstName=first_name,
                    LastName=last_name,
                    EmailAddress=email,
                ))
            )

        if update_marketing:
            requests.append(
                self.client.post(f'/constituents/{constituent_id}/Preferences', data=dict(
                    ConsentStatement='Events.HUF website',
                    Reason='Updated in Events.HUF booking',
                    PreferredChannel='Email',
                    PreferencesList=[
                        {
                            'PreferenceType': 'Channel',
                            'PreferenceName': 'Email',
                            'PreferenceAllowed': allow_marketing
                        }
                    ]
                ))
            )
        requests and await asyncio.gather(*requests)

    async def _get_or_create_constituent(self, user_id, campaign):
        email, first_name, last_name = await self.pg.fetchrow(
            'select email, first_name, last_name from users where id=$1', user_id
        )

        constituent_id = await self._get_constituent(user_id=user_id, email=email)
        return constituent_id or await self._create_constituent(user_id, email, first_name, last_name, campaign)

    async def _get_constituent(self, *, user_id, email=None):
        ext_key = f'nosht_{user_id}'
        r = await self.client.get(f'/constituents/ExternalKey/{ext_key}', allowed_statuses=(200, 404))
        if email is not None and r.status == 404:
            r = await self.client.get(f'/constituents/EmailAddress/{email}', allowed_statuses=(200, 404))

        if r.status != 404:
            constituent_data = (await r.json())[0]
            constituent_id = constituent_data['ConstituentId']
            if constituent_data['ExternalKey'] is None:
                await self.client.put(f'/constituents/{constituent_id}', data=dict(ExternalKey=ext_key))
            elif constituent_data['ExternalKey'] != ext_key:
                logger.warning('user with matching email but different external key %s: %r != %r',
                               constituent_id, constituent_data['ExternalKey'], ext_key)
                return None
            return constituent_id

    async def _create_constituent(self, user_id, email, first_name, last_name, campaign):
        r = await self.client.post(
            '/constituents',
            data=dict(
                FirstName=first_name,
                LastName=last_name,
                EmailAddress=email,
                ConstituentType='Individual',
                AllowNameSwap=False,
                NoGiftAid=False,
                ExternalKey=f'nosht_{user_id}',
                RecruitmentCampaign=campaign,
                EmailFormat='HTML'
            )
        )
        data = await r.json()
        return data['ConstituentId']


def format_dt(dt: datetime):
    return f'{dt:%Y-%m-%dT%H:%M:%SZ}'