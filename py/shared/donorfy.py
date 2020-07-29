import asyncio
import logging
from datetime import datetime
from textwrap import shorten
from time import time
from typing import Sequence, Tuple

import pytz
from aiohttp import BasicAuth, ClientResponse, ClientSession, ClientTimeout
from aiohttp.hdrs import METH_GET, METH_POST, METH_PUT
from arq import concurrent

from .actions import ActionTypes
from .actor import BaseActor
from .settings import Settings
from .stripe_base import get_stripe_processing_fee
from .utils import RequestError, display_cash, lenient_json, ticket_id_signed

logger = logging.getLogger('nosht.donorfy')


class DonorfyClient:
    def __init__(self, settings: Settings, loop):
        self._settings = settings
        self._client = ClientSession(
            timeout=ClientTimeout(total=30), loop=loop, auth=BasicAuth('nosht', settings.donorfy_access_key),
        )

    @property
    def client_session(self):
        return self._client

    async def close(self):
        await self._client.close()

    async def get(self, path, *, allowed_statuses: Sequence[int] = (200,), data=None, params=None):
        return await self._request(METH_GET, path, allowed_statuses, data, params)

    async def put(self, path, *, allowed_statuses: Sequence[int] = (200,), data=None):
        return await self._request(METH_PUT, path, allowed_statuses, data)

    async def post(self, path, *, allowed_statuses: Sequence[int] = (200, 201), data=None):
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
        log_extra = {
            'fingerprint': ['donorfy', r.request_info.real_url, str(r.status)],
            'data': {
                'request_real_url': str(r.request_info.real_url),
                'request_headers': dict(r.request_info.headers),
                'request_method': method,
                'request_data': data,
                'response_status': r.status,
                'response_headers': dict(r.headers),
                'response_content': lenient_json(response_text),
                'time_taken': time_taken,
            },
        }

        if r.status not in allowed_statuses:
            logger.warning('%s %s > %d unexpected response', method, r.request_info.real_url, r.status, extra=log_extra)
            raise RequestError(r.status, full_path)
        else:
            logger.info('successful request %s %s > %d (%0.2fs)', method, path, r.status, time_taken, extra=log_extra)
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
        if self.client:
            await self._get_or_create_constituent(user_id)

    @concurrent
    async def event_created(self, event_id):
        if not self.client:
            return

        async with self.pg.acquire() as conn:
            evt = await conn.fetchrow(
                """
                select
                  start_ts, duration, location_name, ticket_limit, short_description, long_description,
                  event_link(cat.slug, e.slug, e.public, $2) AS link, e.slug as event_slug,
                  cat.slug as cat_slug, co.currency,
                  host as host_user_id, host_user.email as host_email
                from events e
                join categories cat on e.category = cat.id
                join companies co on cat.company = co.id
                join users host_user on e.host = host_user.id
                where e.id=$1
                """,
                event_id,
                self.settings.auth_key,
            )
            created = await conn.fetchval("select ts from actions where event=$1 and type='create-event'", event_id)
            prices = await conn.fetch(
                'select price from ticket_types where event=$1 and active is true and price is not null', event_id
            )
        campaign = await self._get_or_create_campaign(evt['cat_slug'], evt['event_slug'])
        constituent_id, _ = await self._get_or_create_constituent(evt['host_user_id'], campaign)

        await self.client.post(
            f'/constituents/{constituent_id}/AddActiveTags',
            data=f'Hosting and helper volunteers_{evt["cat_slug"]}-host',
        )

        start_ts = evt['start_ts'].astimezone(pytz.utc)
        if not evt['duration']:
            start_ts = start_ts.date()

        evt = dict(evt)
        evt['price_text'] = ', '.join(display_cash(r[0], evt['currency']) for r in prices) or 'free'
        data = dict(
            ExistingConstituentId=constituent_id,
            ActivityType='Event Hosted',
            ActivityDate=format_dt(start_ts),
            Campaign=campaign,
            Notes=(
                'URL: {link}\n'
                'location: {location_name}\n'
                'ticket limit: {ticket_limit}\n'
                'price: {price_text}\n'
                'description: {long_description}'
            ).format(**evt),
            Number1=evt['ticket_limit'],
            Date1=format_dt(created),
            Date2=format_dt(start_ts),
        )

        codes = evt['link'], evt['location_name'], evt['short_description']
        for i, v in enumerate(codes, start=1):
            if v:
                data[f'Code{i}'] = shorten(v, width=50, placeholder='...')

        for i, r in enumerate(prices, start=2):
            data[f'Number{i}'] = float(r[0])

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
                action_id,
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
                  t.price,
                  t.id as ticket_id
                from tickets t
                left join users u on t.user_id = u.id
                where t.booked_action = $1
                """,
                action_id,
            )
        ticket_count = len(tickets)
        campaign = await self._get_or_create_campaign(cat_slug, event_slug)
        buyer_constituent_id, _ = await self._get_or_create_constituent(buyer_user_id, campaign)
        ticket_id = None

        async def create_ticket_constituent(row):
            user_id, email, first_name, last_name, extra_info, ticket_price, _ticket_id = row
            nonlocal ticket_id
            if not user_id and not email:
                return

            if user_id == buyer_user_id:
                constituent_id = buyer_constituent_id
                ticket_id = _ticket_id
            else:
                constituent_id = await self._get_constituent(user_id=user_id, email=email, campaign=campaign)

            if not constituent_id:
                return

            await self.client.post(
                '/activities',
                data=dict(
                    ExistingConstituentId=constituent_id,
                    ActivityType='Event Booked',
                    ActivityDate=format_dt(action_ts),
                    Campaign=campaign,
                    Notes=extra_info,
                    Code1=buyer_user_id,
                    Number1=float(ticket_price or 0),
                    Number2=ticket_count,
                    YesNo1=user_id == buyer_user_id,
                    Date1=format_dt(event_ts),
                ),
            )

        await asyncio.gather(*[create_ticket_constituent(r) for r in tickets])

        if action_type in (ActionTypes.book_free_tickets, ActionTypes.buy_tickets_offline):
            # for both free tickets and offline purchases we don't want to report any revenue to donorfy
            return

        ticket_count, price, extra = await self.pg.fetchrow(
            'select count(*), sum(price), sum(extra_donated) from tickets where booked_action = $1', action_id,
        )
        price = float(price)
        ticket_id = ticket_id or tickets[0]['ticket_id']
        processing_fee = await self._get_stripe_processing_fee(action_id)

        r = await self.client.post(
            '/transactions',
            data=dict(
                ExistingConstituentId=buyer_constituent_id,
                Channel=f'nosht-{cat_slug}',
                Currency=currency,
                Campaign=campaign,
                PaymentMethod='Payment Card via Stripe',
                Product='Event Ticket(s)',
                Fund=self.settings.donorfy_fund,
                Department=self.settings.donorfy_account_salies,
                BankAccount=self.settings.donorfy_bank_account,
                DatePaid=format_dt(action_ts),
                Amount=price,
                ProcessingCostsAmount=processing_fee,
                Quantity=ticket_count,
                Acknowledgement=f'{cat_slug}-thanks',
                AcknowledgementText=f'Ticket ID: {ticket_id_signed(ticket_id, self.settings)}',
                Reference=f'Events.HUF:{cat_slug} {event_slug}',
                AddGiftAidDeclaration=False,
                GiftAidClaimed=False,
            ),
        )
        if extra:
            trans_id = (await r.json())['Id']
            await self.client.post(
                f'/transactions/{trans_id}/AddAllocation',
                data=dict(
                    Product='Donation',
                    Quantity=ticket_count,
                    Amount=float(extra),
                    Department=self.settings.donorfy_account_donations,
                    Fund=self.settings.donorfy_fund,
                    AllocationDate=format_dt(action_ts),
                    CanRecoverTax=False,
                    Comments=f'{cat_slug} {event_slug}',
                    BeneficiaryConstituentId=buyer_constituent_id,
                ),
            )

    @concurrent
    async def donation(self, action_id):
        if not self.client:
            return

        d = await self.pg.fetchrow(
            """
            select a.ts as action_ts, a.user_id, d.amount,
              d.gift_aid, d.title, d.first_name, d.last_name, d.address, d.city, d.postcode,
              d.donation_option as donopt_id, evt.id as event_id,
              cat.name as cat_name, cat.slug as cat_slug, evt.slug as evt_slug, currency
            from actions a
            join donations d on a.id = d.action
            join events evt on a.event = evt.id
            join categories cat on evt.category = cat.id
            join companies co on cat.company = co.id
            where a.id=$1
            """,
            action_id,
        )
        cat_slug, evt_slug = d['cat_slug'], d['evt_slug']
        campaign = await self._get_or_create_campaign(cat_slug, evt_slug)

        constituent_id, _ = await self._get_or_create_constituent(d['user_id'], campaign)
        datestamp = format_dt(d['action_ts'])
        processing_fee = await self._get_stripe_processing_fee(action_id)

        await self.client.post(
            '/transactions',
            data=dict(
                ExistingConstituentId=constituent_id,
                Channel=f'nosht-{cat_slug}',
                Currency=d['currency'],
                Campaign=campaign,
                PaymentMethod='Payment Card via Stripe',
                Product='Donation',
                Fund=self.settings.donorfy_fund,
                Department=self.settings.donorfy_account_donations,
                BankAccount=self.settings.donorfy_bank_account,
                DatePaid=datestamp,
                Amount=float(d['amount']),
                ProcessingCostsAmount=processing_fee,
                Acknowledgement=f'{cat_slug}-thanks',
                AcknowledgementText=f'{d["cat_name"]} Donation Thanks',
                Reference=(
                    f'Events.HUF:{cat_slug} donation option {d["donopt_id"] or "-"}, event {d["event_id"] or "-"}'
                ),
                AddGiftAidDeclaration=False,  # since we manually create the gift aid declaration below
                GiftAidClaimed=d['gift_aid'],
                Title=d['title'],
                FirstName=d['first_name'],
                LastName=d['last_name'],
                AddressLine1=d['address'],
                Town=d['city'],
                PostalCode=d['postcode'],
            ),
        )
        if d['gift_aid']:
            await self.client.post(
                f'/constituents/{constituent_id}/GiftAidDeclarations',
                data=dict(
                    Campaign=campaign,
                    DeclarationMethod='Web',
                    DeclarationDate=datestamp,
                    DeclarationStartDate=datestamp,
                    DeclarationEndDate=datestamp,
                    TaxPayerTitle=d['title'],
                    TaxPayerFirstName=d['first_name'],
                    TaxPayerLastName=d['last_name'],
                    ConfirmationRequired=False,
                ),
            )

    @concurrent
    async def update_user(self, user_id, update_user=True, update_marketing=True):
        if not self.client:
            return
        constituent_id, created = await self._get_or_create_constituent(user_id=user_id)

        first_name, last_name, email, allow_marketing = await self.pg.fetchrow(
            'select first_name, last_name, email, allow_marketing from users where id=$1', user_id
        )

        requests = []
        if update_user and not created:
            requests.append(
                self.client.put(
                    f'/constituents/{constituent_id}',
                    data=dict(FirstName=first_name, LastName=last_name, EmailAddress=email),
                )
            )

        if update_marketing:
            requests.append(
                self.client.post(
                    f'/constituents/{constituent_id}/Preferences',
                    data=dict(
                        ConsentStatement='Events.HUF website',
                        Reason='Updated in Events.HUF booking',
                        PreferredChannel='Email',
                        PreferencesList=[
                            {
                                'PreferenceType': 'Channel',
                                'PreferenceName': 'Email',
                                'PreferenceAllowed': allow_marketing,
                            },
                            {
                                'PreferenceType': 'Purpose',
                                'PreferenceName': 'All',
                                'PreferenceAllowed': allow_marketing,
                            },
                        ],
                    ),
                )
            )
        requests and await asyncio.gather(*requests)

    async def _get_or_create_constituent(self, user_id, campaign=None) -> Tuple[str, bool]:
        email, first_name, last_name = await self.pg.fetchrow(
            'select email, first_name, last_name from users where id=$1', user_id
        )

        constituent_id = await self._get_constituent(user_id=user_id, email=email, campaign=campaign)
        if constituent_id:
            return constituent_id, False

        data = dict(
            FirstName=first_name,
            LastName=last_name,
            EmailAddress=email,
            ConstituentType='Individual',
            AllowNameSwap=False,
            NoGiftAid=False,
            ExternalKey=f'nosht_{user_id}',
            EmailFormat='HTML',
        )
        if campaign:
            data['RecruitmentCampaign'] = campaign

        r = await self.client.post('/constituents', data=data)
        data = await r.json()
        constituent_id = data['ConstituentId']

        redis = await self.get_redis()
        await redis.setex(self._constituent_cache_key(user_id, email, campaign), 3600, constituent_id)
        return constituent_id, True

    @staticmethod
    def _constituent_cache_key(user_id, email, campaign):
        return f'donorfy-constituent-{user_id}-{email}-{campaign}'

    async def _get_constituent(self, *, user_id, email=None, campaign=None):
        redis = await self.get_redis()
        cache_key = self._constituent_cache_key(user_id, email, campaign)
        constituent_id = await redis.get(cache_key)
        if constituent_id:
            return None if constituent_id == b'null' else constituent_id.decode()

        ext_key = f'nosht_{user_id}'
        r = await self.client.get(f'/constituents/ExternalKey/{ext_key}', allowed_statuses=(200, 404))
        if email is not None and r.status == 404:
            r = await self.client.get(f'/constituents/EmailAddress/{email}', allowed_statuses=(200, 404))

        if r.status != 404:
            constituent_data = (await r.json())[0]
            constituent_id = constituent_data['ConstituentId']

            update_data = {}
            if constituent_data['ExternalKey'] is None:
                update_data['ExternalKey'] = ext_key
            if campaign:
                # have to get the constituent again by ID to check "RecruitmentCampaign"
                r_ = await self.client.get(f'/constituents/{constituent_id}')
                extra_data = await r_.json()
                if not extra_data['RecruitmentCampaign']:
                    update_data['RecruitmentCampaign'] = campaign
            if update_data:
                await self.client.put(f'/constituents/{constituent_id}', data=update_data)

            if constituent_data['ExternalKey'] is not None and constituent_data['ExternalKey'] != ext_key:
                logger.warning(
                    'user with matching email but different external key %s: %r != %r',
                    constituent_id,
                    constituent_data['ExternalKey'],
                    ext_key,
                )
            else:
                await redis.setex(cache_key, 300, constituent_id)
                return constituent_id
        await redis.setex(cache_key, 300, b'null')

    async def _get_or_create_campaign(self, cat_slug, event_slug):
        description = f'{cat_slug}:{event_slug}'
        cache_key = f'donorfy-campaigns|{description}'
        redis = await self.get_redis()
        campaign_created = await redis.get(cache_key)
        if campaign_created:
            return description

        r = await self.client.get('/System/LookUpTypes/Campaigns')
        data = await r.json()
        try:
            next(1 for v in data['LookUps'] if v['LookUpDescription'] == description)
        except StopIteration:
            await self.client.post('/System/LookUpTypes/Campaigns', data=dict(LookUpDescription=description))
        await redis.setex(cache_key, 86400, '1')
        return description

    async def _get_stripe_processing_fee(self, action_id: int) -> float:
        return await get_stripe_processing_fee(action_id, self.client.client_session, self.settings, self.pg)


def format_dt(dt: datetime):
    return f'{dt:%Y-%m-%dT%H:%M:%SZ}'
