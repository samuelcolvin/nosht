import logging
from datetime import datetime
from time import time
from typing import Sequence, Union

import pytz
from aiohttp import BasicAuth, ClientSession, ClientResponse, ClientTimeout
from aiohttp.hdrs import METH_GET, METH_POST
from arq import concurrent

from .utils import RequestError, lenient_json, display_cash
from .settings import Settings
from .actor import BaseActor

logger = logging.getLogger('nosht.donorfy')


def format_dt(dt: datetime):
    return f'{dt.astimezone(pytz.utc):%Y-%m-%dT%H:%M:%SZ}'


class DonorfyClient:
    def __init__(self, settings: Settings, loop):
        self._client = ClientSession(
            timeout=ClientTimeout(total=30),
            loop=loop,
            auth=BasicAuth('nosht', settings.donorfy_access_key),
        )
        self._root = settings.donorfy_api_root + settings.donorfy_api_key

    async def close(self):
        await self._client.close()

    async def get(self, path, *, allowed_statuses: Union[int, Sequence[int]]=200, data=None, params=None):
        return await self._request(METH_GET, path, allowed_statuses, data, params)

    async def post(self, path, *, allowed_statuses: Union[int, Sequence[int]]=(200, 201), data=None):
        return await self._request(METH_POST, path, allowed_statuses, data)

    async def delete(self, path, *, allowed_statuses: Union[int, Sequence[int]]=(200, 201), data=None):
        return await self._request(METH_DELETE, path, allowed_statuses, data)

    async def _request(self, method, path, allowed_statuses, data, params=None) -> ClientResponse:
        assert path.startswith('/'), path
        full_path = self._root + path
        start = time()
        try:
            async with self._client.request(method, full_path, params=params, json=data) as r:
                response_text = await r.text()
        except TimeoutError:
            logger.warning('timeout %s %s', method, path)
            raise

        time_taken = time() - start

        if isinstance(allowed_statuses, int):
            allowed_statuses = allowed_statuses,
        if allowed_statuses != '*' and r.status not in allowed_statuses:
            data = {
                'request_real_url': str(r.request_info.real_url),
                'request_headers': dict(r.request_info.headers),
                'request_data': data,
                'response_status': r.status,
                'response_headers': dict(r.headers),
                'response_content': lenient_json(response_text),
                'time_taken': time_taken,
            }
            debug(data)
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

        first_name, last_name, email = await self.pg.fetchrow(
            'select first_name, last_name, email from users where id=$1', user_id
        )
        constituent_id = await self._get_constituent(email=email)
        if not constituent_id:
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
                    RecruitmentCampaign='Events.HUF',
                    JobTitle='host',
                    EmailFormat='HTML'
                )
            )
            data = await r.json()
            constituent_id = data['ConstituentId']

        await self.client.post(
            f'/constituents/{constituent_id}/AddActiveTags', data='Hosting and helper volunteers_host'
        )

    @concurrent
    async def event_created(self, event_id):
        async with self.pg.acquire() as conn:
            evt = await conn.fetchrow(
                """
                select 
                  start_ts, duration, cat.slug, location_name, ticket_limit, short_description, long_description,
                  event_link(cat.slug, e.slug, e.public, $2) AS link, host, co.currency
                from events e
                join categories cat on e.category = cat.id
                join companies co on cat.company = co.id
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
            ExistingConstituentId=123,
            ActivityType='Event Hosted',
            ActivityDate=format_dt(start_ts),
            Campaign='Events.HUF',
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
        for i, r in enumerate(prices, start=1):
            data[f'Number{i}'] = r[0]

        constituent_id = await self._get_constituent(user_id=evt['host'])
        if constituent_id:
            data['ExistingConstituentId'] = constituent_id
        await self.client.post('/activities', data=data)

    @concurrent
    async def tickets_booked(self, action_id):
        pass

    async def _get_constituent(self, user_id=None, email=None):
        assert user_id or email, 'either the user_id or email argument are required'
        if user_id:
            url = f'/constituents/ExternalKey/nosht_{user_id}'
        else:
            url = f'/constituents/EmailAddress/{email}'
        r = await self.client.get(url, allowed_statuses=(200, 404))
        if r.status == 404:
            constituents_data = await r.json()
            return constituents_data[0]['ConstituentId']
