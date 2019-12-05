import logging

from aiohttp import BasicAuth, ClientSession
from aiohttp.hdrs import METH_GET, METH_POST
from buildpg.asyncpg import BuildPgConnection

from shared.settings import Settings
from shared.utils import RequestError

logger = logging.getLogger('nosht.stripe.base')


async def get_stripe_processing_fee(action_id: int, client, settings, conn: BuildPgConnection) -> float:
    stripe_transaction_id, currency, stripe_secret_key = await conn.fetchrow(
        """
        select extra->>'stripe_balance_transaction', currency, stripe_secret_key
        from actions a
        join events as e on a.event = e.id
        join categories cat on e.category = cat.id
        join companies co on cat.company = co.id
        where a.id=$1
        """,
        action_id,
    )
    assert stripe_transaction_id and stripe_transaction_id.startswith('txn_'), stripe_transaction_id

    stripe = StripeClient({'stripe_client': client, 'settings': settings}, stripe_secret_key)
    r = await stripe.get(f'balance/history/{stripe_transaction_id}')
    if r['currency'] != currency:
        logger.warning(
            'transaction currency does not match company, trans_currency=%r company_currency=%r transaction_id=%r',
            r['currency'],
            currency,
            stripe_transaction_id,
        )
        return 0
    else:
        return r['fee'] / 100


class StripeClient:
    def __init__(self, app, stripe_secret_key):
        self._client: ClientSession = app['stripe_client']
        self._settings: Settings = app['settings']
        self._auth = BasicAuth(stripe_secret_key)

    async def get(self, path, *, idempotency_key=None, **data):
        return await self._request(METH_GET, path, idempotency_key=idempotency_key, **data)

    async def post(self, path, *, idempotency_key=None, **data):
        return await self._request(METH_POST, path, idempotency_key=idempotency_key, **data)

    async def _request(self, method, path, *, idempotency_key=None, **data):
        post = {}
        for k, v in data.items():
            if isinstance(v, dict):
                post.update({f'{k}[{kk}]': str(vv) for kk, vv in v.items()})
            else:
                post[k] = str(v)
        headers = {'Stripe-Version': self._settings.stripe_api_version}
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key + self._settings.stripe_idempotency_extra
        full_path = self._settings.stripe_root_url + path
        async with self._client.request(method, full_path, data=post or None, auth=self._auth, headers=headers) as r:
            if r.status == 200:
                return await r.json()
            else:
                # check stripe > developer > logs for more info
                text = await r.text()
                raise RequestError(r.status, full_path, text=text)
