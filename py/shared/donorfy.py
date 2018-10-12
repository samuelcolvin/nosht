import logging

from aiohttp import BasicAuth, ClientSession, ClientResponse, ClientTimeout
from aiohttp.hdrs import METH_GET, METH_POST
from arq import concurrent

from .utils import RequestError, lenient_json
from .settings import Settings
from .actor import BaseActor

logger = logging.getLogger('nosht.donorfy')


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

    async def get(self, path, *, allowed_statuses=200, data=None):
        return await self._request(METH_GET, path, allowed_statuses, data)

    async def post(self, path, *, allowed_statuses=(200, 201), data=None):
        return await self._request(METH_POST, path, allowed_statuses, data)

    async def _request(self, method, path, allowed_statuses, data) -> ClientResponse:
        assert path.startswith('/'), path
        full_path = self._root + path
        async with self._client.request(method, full_path, json=data) as r:
            response_text = await r.text()

        if isinstance(allowed_statuses, int):
            allowed_statuses = allowed_statuses,
        if allowed_statuses != '*' and r.status not in allowed_statuses:
            data = {
                'request_real_url': str(r.request_info.real_url),
                'request_headers': dict(r.request_info.headers),
                'request_data': data,
                'response_headers': dict(r.headers),
                'response_content': lenient_json(response_text),
            }
            # debug(data)
            logger.warning('%s unexpected response %s /%s -> %s', self.__class__.__name__, method, path, r.status,
                           extra={'data': data})
            raise RequestError(r.status, full_path)
        else:
            logger.debug('%s /%s -> %s', method, path, r.status)
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

        async with self.pg.acquire() as conn:
            first_name, last_name, email = await conn.fetchrow(
                'SELECT first_name, last_name, email FROM users WHERE id=$1',
                user_id
            )

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

        tag = 'Hosting and helper volunteers_host'
        await self.client.post(
            f'/constituents/{constituent_id}/AddActiveTags', data=tag
        )
