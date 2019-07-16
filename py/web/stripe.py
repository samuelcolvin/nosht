import hashlib
import json
import logging
import re
from contextlib import contextmanager
from enum import Enum
from typing import Optional, Tuple, Union, cast

from aiohttp import BasicAuth, ClientSession
from aiohttp.abc import Application
from aiohttp.hdrs import METH_GET, METH_POST
from buildpg import Values
from buildpg.asyncpg import BuildPgConnection
from pydantic import BaseModel, MissingError, constr, validator

from shared.settings import Settings
from shared.utils import RequestError, pseudo_random_str

from .actions import ActionTypes
from .utils import JsonErrors, decrypt_json

logger = logging.getLogger('nosht.stripe')


class Reservation(BaseModel):
    user_id: int
    action_id: int
    event_id: int
    price_cent: Optional[int]
    ticket_count: int
    event_name: str


class Donation(BaseModel):
    user_id: int
    price_cent: int
    donation_option_name: str


class BookingModel(BaseModel):
    booking_token: bytes


class BookActions(str, Enum):
    buy_tickets_offline = 'buy-tickets-offline'
    book_free_tickets = 'book-free-tickets'


class BookFreeModel(BookingModel):
    book_action: BookActions


class StripeNewCard(BaseModel):
    token: str
    card_ref: str
    client_ip: str


class StripeOldCard(BaseModel):
    source_hash: str


class StripeModel(BaseModel):
    stripe: Union[StripeNewCard, StripeOldCard]


class StripeBuyModel(StripeModel, BookingModel):
    pass


class StripeDonateModel(StripeModel):
    donation_option_id: int
    event_id: int
    gift_aid: bool
    title: constr(max_length=31) = None
    first_name: constr(max_length=255) = None
    last_name: constr(max_length=255) = None
    address: constr(max_length=255) = None
    city: constr(max_length=255) = None
    postcode: constr(max_length=31) = None

    @validator('title', 'first_name', 'last_name', 'address', 'city', 'postcode', always=True, pre=True)
    def check_required_fields(cls, v, values, **kwargs):
        if v is None and values.get('gift_aid'):
            raise MissingError()
        return v or ''  # https://github.com/samuelcolvin/pydantic/issues/132


async def get_reservation(m: BookingModel, user_id, app, conn: BuildPgConnection) -> Reservation:
    res = Reservation(**decrypt_json(app, m.booking_token, ttl=app['settings'].ticket_ttl - 10))
    assert user_id in {None, res.user_id}, "user ids don't match"

    reserved_tickets = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM tickets
        WHERE event=$1 AND reserve_action=$2 AND status='reserved' AND booked_action IS NULL
        """,
        res.event_id, res.action_id,
    )
    if res.ticket_count != reserved_tickets:
        # reservation could have already been used or event id could be wrong
        logger.warning('res ticket count %d, db reserved tickets %d', res.ticket_count, reserved_tickets)
        raise JsonErrors.HTTPBadRequest(message='invalid reservation')

    return res


async def stripe_buy_intent(res: Reservation, company_id: int, app, conn: BuildPgConnection) -> str:
    with _catch_stripe_errors():
        return await _create_payment_intent(
            user_id=res.user_id,
            price_cents=res.price_cent,
            description=f'{res.ticket_count} tickets for {res.event_name} ({res.event_id})',
            metadata={
                'purpose': 'buy-tickets',
                'event': res.event_id,
                'tickets_bought': res.ticket_count,
                'reserve_action': res.action_id,
            },
            company_id=company_id,
            app=app,
            conn=conn,
        )


async def book_free(m: BookFreeModel, company_id: int, session: dict, app, conn: BuildPgConnection) -> int:
    user_id = session.get('user_id')
    res = await get_reservation(m, user_id, app, conn)
    if m.book_action is BookActions.book_free_tickets:
        if res.price_cent is not None:
            raise JsonErrors.HTTPBadRequest(message='booking not free')
    else:
        if session.get('role') != 'admin':
            event_host = await conn.fetchval('SELECT host FROM events WHERE id=$1', res.event_id)
            if user_id != event_host:
                raise JsonErrors.HTTPBadRequest(message='to buy tickets offline you must be the host or an admin')

    async with conn.transaction():
        confirm_action_id = await conn.fetchval_b(
            'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
            values=Values(
                company=company_id,
                user_id=res.user_id,
                event=res.event_id,
                type=m.book_action,
            )
        )
        await conn.execute(
            "UPDATE tickets SET status='booked', booked_action=$1 WHERE reserve_action=$2",
            confirm_action_id, res.action_id,
        )
        await conn.execute('SELECT check_tickets_remaining($1, $2)', res.event_id, app['settings'].ticket_ttl)

    return confirm_action_id


async def stripe_buy(m: StripeBuyModel, company_id: int, user_id: Optional[int], app,
                     conn: BuildPgConnection) -> Tuple[int, str]:
    res = await get_reservation(m, user_id, app, conn)
    with _catch_stripe_errors():
        return await _stripe_pay(m=m, company_id=company_id, app=app, conn=conn, res=res)


async def stripe_donate(m: StripeDonateModel, company_id: int, user_id: Optional[int], app,
                        conn: BuildPgConnection) -> Tuple[int, str]:
    r = await conn.fetchrow(
        """
        SELECT opt.name, opt.amount, cat.id
        FROM donation_options AS opt
        JOIN categories AS cat ON opt.category = cat.id
        WHERE opt.id = $1 AND opt.live AND cat.company = $2
        """,
        m.donation_option_id, company_id
    )
    if not r:
        raise JsonErrors.HTTPBadRequest(message='donation option not found')

    name, amount, cat_id = r
    event = await conn.fetchval('SELECT 1 FROM events WHERE id=$1 AND category=$2', m.event_id, cat_id)
    if not event:
        raise JsonErrors.HTTPBadRequest(message='event not found on the same category as donation_option')

    don = Donation(
        user_id=user_id,
        price_cent=int(amount * 100),
        donation_option_name=name
    )
    with _catch_stripe_errors():
        return await _stripe_pay(m=m, company_id=company_id, app=app, conn=conn, don=don)


async def stripe_refund(
    refund_charge_id: Optional[str],
    ticket_id: int,
    amount: int,
    user_id: int,
    company_id: int,
    app: Application,
    conn: BuildPgConnection
):
    """
    Should be called inside ticket cancellation transaction/
    """
    user_email, stripe_secret_key = await conn.fetchrow(
        """
        SELECT email, stripe_secret_key
        FROM users AS u
        JOIN companies c on u.company = c.id
        WHERE u.id=$1 AND c.id=$2
        """,
        user_id, company_id
    )
    stripe = StripeClient(app, stripe_secret_key)
    return await stripe.post(
        'refunds',
        idempotency_key=f'refund-ticket-{ticket_id}',
        charge=refund_charge_id,
        amount=amount,
        reason='requested_by_customer',
        metadata={
            'admin_email': user_email,
            'admin_user_id': user_id,
        }
    )


async def _create_payment_intent(
    *,
    user_id: int,
    price_cents: int,
    description: str,
    metadata: dict,
    company_id: int,
    app: Application,
    conn: BuildPgConnection,
) -> str:

    if price_cents is None or price_cents < 100:
        raise JsonErrors.HTTPBadRequest(message='booking price cent < 100')

    user_name, user_email, user_role, stripe_customer_id, stripe_secret_key, currency = await conn.fetchrow(
        """
        SELECT
          full_name(first_name, last_name, email) AS name, email, role, stripe_customer_id, stripe_secret_key, currency
        FROM users AS u
        JOIN companies c on u.company = c.id
        WHERE u.id=$1 AND c.id=$2
        """,
        user_id, company_id
    )

    # could move the customer stuff to the worker
    new_customer = True
    stripe = StripeClient(app, stripe_secret_key)
    if stripe_customer_id:
        try:
            await stripe.get(f'customers/{stripe_customer_id}')
        except RequestError as e:
            # 404 is ok, it happens when the customer has been deleted, we create a new customer below
            if e.status != 404:
                raise
        else:
            new_customer = False

    if new_customer:
        customer = await stripe.post(
            'customers',
            email=user_email,
            description=f'{user_name} ({user_role})',
            metadata={
                'role': user_role,
                'user_id': user_id,
            }
        )
        stripe_customer_id = customer['id']
        await conn.execute('UPDATE users SET stripe_customer_id=$1 WHERE id=$2', stripe_customer_id, user_id)
    settings: Settings = app['settings']
    intent = await stripe.post(
        'payment_intents',
        amount=price_cents,
        currency=currency,
        setup_future_usage='on_session',
        customer=stripe_customer_id,
        description=description,
        metadata=metadata,
        statement_descriptor=_clean_descriptor(f'{settings.stripe_descriptor_prefix}: {description}')
    )
    debug(intent)
    return intent['client_secret']


async def _stripe_pay():
    async with conn.transaction():
        # mark the tickets paid in DB, then create charge in stripe, then finish transaction
        if res:
            action_id = await conn.fetchval_b(
                'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
                values=Values(
                    company=company_id,
                    user_id=user_id,
                    type=ActionTypes.buy_tickets,
                    event=res.event_id,
                )
            )
            await conn.execute(
                "UPDATE tickets SET status='booked', booked_action=$1 WHERE reserve_action=$2",
                action_id, res.action_id,
            )
            await conn.execute('SELECT check_tickets_remaining($1, $2)', res.event_id, app['settings'].ticket_ttl)
            idempotency_key = f'buy-reservation-{res.action_id}'
            metadata = {
                'purpose': 'buy-tickets',
                'event': res.event_id,
                'tickets_bought': res.ticket_count,
                'booked_action': action_id,
                'reserve_action': res.action_id,
            }
            description = f'{res.ticket_count} tickets for {res.event_name} ({res.event_id})'
        else:
            assert don
            m = cast(StripeDonateModel, m)
            action_id = await conn.fetchval_b(
                'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
                values=Values(
                    company=company_id,
                    user_id=user_id,
                    type=ActionTypes.donate,
                    event=m.event_id,
                )
            )
            don_values = dict(
                donation_option=m.donation_option_id,
                amount=price_cents / 100,
                gift_aid=m.gift_aid,
                action=action_id,
            )
            if m.gift_aid:
                don_values.update(
                    first_name=m.first_name,
                    last_name=m.last_name,
                    title=m.title,
                    address=m.address,
                    city=m.city,
                    postcode=m.postcode,
                )
            don_id = await conn.fetchval_b(
                'INSERT INTO donations (:values__names) VALUES :values RETURNING id',
                values=Values(**don_values)
            )
            cache_key = f'idempotency-donate-{m.donation_option_id}-{user_id}'
            with await app['redis'] as redis:
                idempotency_key = await redis.get(cache_key)
                if idempotency_key:
                    idempotency_key = idempotency_key.decode()
                else:
                    idempotency_key = f'{cache_key}-{pseudo_random_str()}'
                    await redis.setex(cache_key, 20, idempotency_key)
            metadata = {
                'purpose': 'donate',
                'donation_option': m.donation_option_id,
                'donation_id': don_id,
                'event': m.event_id,
            }
            description = f'donation towards {don.donation_option_name} ({don_id})'

        charge = await stripe.post(
            'charges',
            idempotency_key=idempotency_key,
            amount=price_cents,
            currency=currency,
            customer=stripe_customer_id,
            source=source_id,
            description=description,
            metadata=metadata
        )
    await conn.execute(
        'UPDATE actions SET extra=$1 WHERE id=$2',
        json.dumps({
            'new_customer': new_customer,
            'new_card': new_card,
            'charge_id': charge['id'],
            'brand': charge['source']['brand'],
            'card_last4': charge['source']['last4'],
            'card_expiry': f"{charge['source']['exp_month']}/{charge['source']['exp_year'] - 2000}",
        }),
        action_id,
    )
    if new_customer:
        await conn.execute('UPDATE users SET stripe_customer_id=$1 WHERE id=$2', stripe_customer_id, user_id)
    return action_id, None if use_saved_card else _hash_src(source_id)


@contextmanager
def _catch_stripe_errors():
    try:
        yield
    except RequestError as e:
        if e.status != 402:
            raise
        data = e.json()
        code = data['error']['code']
        message = data['error']['message']
        logger.info('stripe payment failed: %s, %s', code, message)
        raise JsonErrors.HTTPPaymentRequired(message=message, code=code) from e


def _card_ref(c):
    return '{last4}-{exp_year}-{exp_month}'.format(**c)


def _hash_src(source_id):
    return hashlib.sha1(source_id.encode()).hexdigest()


descriptor_remove = re.compile(r"""[<>'"*]""")


def _clean_descriptor(s: str) -> str:
    return descriptor_remove.sub('', s)[:22]


class StripeClient:
    def __init__(self, app, stripe_secret_key):
        self._client: ClientSession = app['stripe_client']
        self._settings: Settings = app['settings']
        self._auth = BasicAuth(stripe_secret_key)

    async def get(self, path, *, idempotency_key=None, **data):
        return await self._request(METH_GET, path, idempotency_key=idempotency_key, **data)

    async def post(self, path, *, idempotency_key=None, **data):
        debug(data)
        return await self._request(METH_POST, path, idempotency_key=idempotency_key, **data)

    async def _request(self, method, path, *, idempotency_key=None, **data):
        metadata = data.pop('metadata', None)
        if metadata:
            data.update({f'metadata[{k}]': v for k, v in metadata.items()})
        headers = {'Stripe-Version': self._settings.stripe_api_version}
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key + self._settings.stripe_idempotency_extra
        full_path = self._settings.stripe_root_url + path
        async with self._client.request(method, full_path, data=data or None, auth=self._auth, headers=headers) as r:
            if r.status == 200:
                return await r.json()
            else:
                # check stripe > developer > logs for more info
                text = await r.text()
                raise RequestError(r.status, full_path, text=text)
