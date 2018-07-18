import json
import logging
from functools import partial
from typing import Optional

from aiohttp import BasicAuth, ClientSession
from buildpg import Values
from buildpg.asyncpg import BuildPgConnection
from pydantic import BaseModel

from shared.settings import Settings
from shared.utils import RequestError

from .actions import ActionTypes
from .utils import JsonErrors, decrypt_json

logger = logging.getLogger('nosht.stripe')


class Reservation(BaseModel):
    user_id: int
    action_id: int
    event_id: int
    price_cent: int
    ticket_count: int
    event_name: str


class StripePayModel(BaseModel):
    stripe_token: str
    stripe_client_ip: str
    stripe_card_ref: str
    booking_token: bytes


async def stripe_pay(m: StripePayModel, company_id: int, user_id: Optional[int], app, conn: BuildPgConnection) -> int:
    ticket_ttl = app['settings'].ticket_ttl
    res = Reservation(**decrypt_json(app, m.booking_token, ttl=ticket_ttl - 10))
    assert user_id in {None, res.user_id}, "user ids don't match"

    user_name, user_email, user_role, stripe_customer_id, stripe_secret_key, currency = await conn.fetchrow(
        """
        SELECT
          first_name || ' ' || last_name AS name, email, role, stripe_customer_id, stripe_secret_key, currency
        FROM users AS u
        JOIN companies c on u.company = c.id
        WHERE u.id=$1 AND c.id=$2
        """,
        res.user_id, company_id
    )
    reserved_tickets = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM tickets
        WHERE event=$1 AND reserve_action=$2 AND status='reserved' AND paid_action IS NULL
        """,
        res.event_id, res.action_id,
    )
    if res.ticket_count != reserved_tickets:
        # reservation could have already been used or event id could be wrong
        logger.warning('res ticket count %d, db reserved tickets %d', res.ticket_count, reserved_tickets)
        raise JsonErrors.HTTPBadRequest(message='invalid reservation')

    source_id = None
    new_customer, new_card = True, True
    auth = BasicAuth(stripe_secret_key)
    stripe_get = partial(stripe_request, app, auth, 'get')
    stripe_post = partial(stripe_request, app, auth, 'post')
    if stripe_customer_id:
        try:
            cards = await stripe_get(f'customers/{stripe_customer_id}/sources?object=card')
        except RequestError as e:
            # 404 is ok, it happens when the customer has been deleted, we create a new customer below
            if e.status != 404:
                raise
        else:
            new_customer = False
            try:
                source_id = next(c['id'] for c in cards['data'] if _card_ref(c) == m.stripe_card_ref)
            except StopIteration:
                # cad not found on customer, create a new source
                source = await stripe_post(
                    f'customers/{stripe_customer_id}/sources',
                    source=m.stripe_token,
                )
                source_id = source['id']
            else:
                new_card = False

    if new_customer:
        customer = await stripe_post(
            'customers',
            source=m.stripe_token,
            email=f'{user_name} <{user_email}>' if user_name else user_email,
            description=f'{user_name or user_email} ({user_role})',
            metadata={
                'role': user_role,
                'user_id': res.user_id,
            }
        )
        stripe_customer_id = customer['id']
        source_id = customer['sources']['data'][0]['id']

    async with conn.transaction():
        # make the tickets paid in DB then, then create charge in stripe, then finish transaction
        paid_action_id = await conn.fetchval_b(
            'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
            values=Values(company=company_id, user_id=res.user_id, type=ActionTypes.buy_tickets.value)
        )
        await conn.execute(
            "UPDATE tickets SET status='paid', paid_action=$1 WHERE reserve_action=$2",
            paid_action_id, res.action_id,
        )
        await conn.execute('SELECT check_tickets_remaining($1, $2)', res.event_id, ticket_ttl)

        charge = await stripe_post(
            'charges',
            idempotency_key=f'charge-{res.action_id}',
            amount=res.price_cent,
            currency=currency,
            customer=stripe_customer_id,
            source=source_id,
            description=f'{res.ticket_count} tickets for {res.event_name} ({res.event_id})',
            metadata={
                'event': res.event_id,
                'tickets_bought': res.ticket_count,
                'paid_action': paid_action_id,
                'reserve_action': res.action_id,
            }
        )
    await conn.execute(
        'UPDATE actions SET extra=$1 WHERE id=$2',
        json.dumps({
            'new_customer': new_customer,
            'new_card': new_card,
            'charge_id': charge['id'],
            'card_last4': charge['source']['last4'],
            'card_expiry': f"{charge['source']['exp_month']}/{charge['source']['exp_year'] - 2000}",
        }),
        paid_action_id,
    )
    if new_customer:
        await conn.execute('UPDATE users SET stripe_customer_id=$1 WHERE id=$2', stripe_customer_id, res.user_id)
    return paid_action_id


def _card_ref(c):
    return '{last4}-{exp_year}-{exp_month}'.format(**c)


async def stripe_request(app, auth, method, path, *, idempotency_key=None, **data):
    client: ClientSession = app['stripe_client']
    settings: Settings = app['settings']
    metadata = data.pop('metadata', None)
    if metadata:
        data.update({f'metadata[{k}]': v for k, v in metadata.items()})
    headers = {}
    if idempotency_key:
        headers['Idempotency-Key'] = idempotency_key + settings.stripe_idempotency_extra
    full_path = settings.stripe_root_url + path
    async with client.request(method, full_path, data=data or None, auth=auth, headers=headers) as r:
        if r.status == 200:
            return await r.json()
        else:
            # check stripe > developer > logs for more info
            text = await r.text()
            raise RequestError(r.status, full_path, info=text)
