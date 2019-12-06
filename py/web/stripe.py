import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime
from enum import Enum
from time import time
from typing import Optional

from aiohttp.abc import Application
from buildpg import Values
from buildpg.asyncpg import BuildPgConnection
from pydantic import BaseModel

from shared.stripe_base import StripeClient
from shared.utils import RequestError

from .utils import JsonErrors, decrypt_json

logger = logging.getLogger('nosht.stripe')


class Reservation(BaseModel):
    user_id: int
    action_id: int
    event_id: int
    price_cent: Optional[int]
    ticket_count: int
    event_name: str


class BookActions(str, Enum):
    buy_tickets_offline = 'buy-tickets-offline'
    book_free_tickets = 'book-free-tickets'


class BookFreeModel(BaseModel):
    booking_token: bytes
    book_action: BookActions


async def stripe_buy_intent(res: Reservation, company_id: int, app, conn: BuildPgConnection) -> str:
    return await stripe_payment_intent(
        user_id=res.user_id,
        price_cents=res.price_cent,
        description=f'{res.ticket_count} tickets for {res.event_name} ({res.event_id})',
        metadata={
            'purpose': 'buy-tickets',
            'event_id': res.event_id,
            'tickets_bought': res.ticket_count,
            'reserve_action_id': res.action_id,
            'user_id': res.user_id,
        },
        company_id=company_id,
        idempotency_key=f'buy-reservation-{res.action_id}',
        app=app,
        conn=conn,
    )


async def book_free(m: BookFreeModel, company_id: int, session: dict, app, conn: BuildPgConnection) -> int:
    user_id = session.get('user_id')

    res = Reservation(**decrypt_json(app, m.booking_token, ttl=app['settings'].ticket_ttl - 10))
    assert user_id in {None, res.user_id}, "user ids don't match"

    reserved_tickets = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM tickets
        WHERE event=$1 AND reserve_action=$2 AND status='reserved' AND booked_action IS NULL
        """,
        res.event_id,
        res.action_id,
    )
    if res.ticket_count != reserved_tickets:
        # reservation could have already been used or event id could be wrong
        logger.warning('res ticket count %d, db reserved tickets %d', res.ticket_count, reserved_tickets)
        raise JsonErrors.HTTPBadRequest(message='invalid reservation')

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
            values=Values(company=company_id, user_id=res.user_id, event=res.event_id, type=m.book_action),
        )
        # mark the tickets as price=0 although they could all already be zero,
        # this avoids reporting false revenue for buy-tickets-offline, see #237
        await conn.execute(
            """
            UPDATE tickets SET status='booked', booked_action=$1, price=null, extra_donated=null
            WHERE reserve_action=$2
            """,
            confirm_action_id,
            res.action_id,
        )
        await conn.execute('SELECT check_tickets_remaining($1, $2)', res.event_id, app['settings'].ticket_ttl)
        await conn.execute('delete from waiting_list where event=$1 and user_id=$2', res.event_id, user_id)

    return confirm_action_id


async def get_stripe_payment_method(
    *, payment_method_id: str, company_id: int, user_id: int, app, conn: BuildPgConnection
) -> dict:
    stripe_customer_id, stripe_secret_key = await conn.fetchrow(
        """
        SELECT stripe_customer_id, stripe_secret_key
        FROM users AS u
        JOIN companies c on u.company = c.id
        WHERE u.id=$1 AND c.id=$2
        """,
        user_id,
        company_id,
    )
    stripe = StripeClient(app, stripe_secret_key)
    try:
        data = await stripe.get(f'payment_methods/{payment_method_id}')
    except RequestError as e:
        if e.status == 404:
            raise JsonErrors.HTTPNotFound(message='payment method not found')
        else:
            raise
    else:
        if data['customer'] != stripe_customer_id:
            raise JsonErrors.HTTPNotFound(message='payment method not found for this customer')
        payment_method_age = datetime.now() - datetime.fromtimestamp(data['created'])
        if payment_method_age.total_seconds() > 3600:
            raise JsonErrors.HTTPNotFound(message='payment method expired')
        return {
            'card': {k: data['card'][k] for k in ('brand', 'exp_month', 'exp_year', 'last4')},
            'address': data['billing_details']['address'],
            'name': data['billing_details']['name'],
        }


async def stripe_refund(
    refund_charge_id: Optional[str],
    ticket_id: int,
    amount: int,
    user_id: int,
    company_id: int,
    app: Application,
    conn: BuildPgConnection,
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
        user_id,
        company_id,
    )
    stripe = StripeClient(app, stripe_secret_key)
    return await stripe.post(
        'refunds',
        idempotency_key=f'refund-ticket-{ticket_id}',
        charge=refund_charge_id,
        amount=amount,
        reason='requested_by_customer',
        metadata={'admin_email': user_email, 'admin_user_id': user_id},
    )


async def stripe_webhook_body(request) -> dict:
    """
    check the signature of a stripe webhook, then decode and return the body
    """
    ts, sig = '1', 'missing'
    try:
        for part in request.headers['Stripe-Signature'].split(','):
            key, value = part.split('=', 1)
            if key == 't':
                ts = value
            elif key == 'v1':
                sig = value
    except (ValueError, KeyError):
        raise JsonErrors.HTTPForbidden(message='Invalid signature')

    stripe_webhook_secret = await request['conn'].fetchval(
        'select stripe_webhook_secret from companies where id=$1', request['company_id']
    )
    if not stripe_webhook_secret:
        raise JsonErrors.HTTPBadRequest(message='stripe webhooks not configured')

    text = await request.text()
    payload = f'{ts}.{text}'.encode()
    if not secrets.compare_digest(hmac.new(stripe_webhook_secret.encode(), payload, hashlib.sha256).hexdigest(), sig):
        raise JsonErrors.HTTPForbidden(message='Invalid signature')

    age = int(time()) - int(ts)
    if age > 300:
        raise JsonErrors.HTTPBadRequest(message='webhook too old', age=age)

    return json.loads(text)


async def stripe_payment_intent(
    *,
    user_id: int,
    price_cents: int,
    description: str,
    metadata: dict,
    company_id: int,
    idempotency_key: str,
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
        user_id,
        company_id,
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
            metadata={'role': user_role, 'user_id': user_id},
        )
        stripe_customer_id = customer['id']
        await conn.execute('UPDATE users SET stripe_customer_id=$1 WHERE id=$2', stripe_customer_id, user_id)
    payment_intent = await stripe.post(
        'payment_intents',
        idempotency_key=idempotency_key,
        amount=price_cents,
        currency=currency,
        setup_future_usage='on_session',
        customer=stripe_customer_id,
        description=description,
        metadata=metadata,
    )
    return payment_intent['client_secret']
