import json
import logging
from enum import Enum

from aiohttp.web_response import Response
from buildpg import Values
from buildpg.asyncpg import BuildPgConnection
from pydantic import BaseModel

from shared.actions import ActionTypes
from shared.settings import Settings
from web.stripe import (StripeClient, catch_stripe_errors, get_stripe_payment_method, payment_intent_key,
                        stripe_webhook_body)
from web.utils import json_response
from web.views.booking import UpdateViewAuth

logger = logging.getLogger('nosht.views.stripe')


class MetadataPurpose(str, Enum):
    buy_tickets = 'buy-tickets'
    donate = 'donate'


class MetadataModel(BaseModel):
    purpose: MetadataPurpose
    user_id: int
    event_id: int
    reserve_action_id: int


async def stripe_webhook(request):
    webhook = await stripe_webhook_body(request)
    hook_type = webhook['type']
    if hook_type == 'payment_intent.payment_failed':
        ...
    elif hook_type != 'payment_intent.succeeded':
        logger.warning('unknown webhook %r', hook_type, extra={'webhook': webhook})
        return

    settings: Settings = request.app['settings']
    conn: BuildPgConnection = request['conn']
    company_id: int = request['company_id']

    data = webhook['data']['object']
    # amount_cents = data['amount']
    payment_method_id = data['payment_method']
    metadata = MetadataModel(**data['metadata'])

    charge = data['charges']['data'][0]
    card = charge['payment_method_details']['card']
    action_extra = json.dumps({
        'charge_id': charge['id'],
        'brand': card['brand'],
        'card_last4': card['last4'],
        'card_expiry': f"{card['exp_month']}/{card['exp_year'] - 2000}",
        '3DS': card['three_d_secure'],
    })

    async with conn.transaction():
        # mark the tickets paid in DB, then create charge in stripe, then finish transaction
        if metadata.purpose == MetadataPurpose.buy_tickets:
            action_id = await conn.fetchval_b(
                'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
                values=Values(
                    company=company_id,
                    user_id=metadata.user_id,
                    type=ActionTypes.buy_tickets,
                    event=metadata.event_id,
                    extra=action_extra
                )
            )
            await conn.execute(
                "UPDATE tickets SET status='booked', booked_action=$1 WHERE reserve_action=$2",
                action_id, int(metadata.reserve_action_id),
            )
            await conn.execute('SELECT check_tickets_remaining($1, $2)', metadata.event_id, settings.ticket_ttl)
        else:
            action_id = await conn.fetchval_b(
                'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
                values=Values(
                    company=company_id,
                    user_id=metadata.user_id,
                    type=ActionTypes.donate,
                    event=metadata.event_id,
                    extra=action_extra,
                )
            )
            # gift_aid = metadata['gift_aid'].lower() == 'true'
            # don_values = dict(
            #     donation_option=int(metadata['donation_option_id']),
            #     amount=amount_cents / 100,
            #     gift_aid=gift_aid,
            #     action=action_id,
            # )
            # if gift_aid:
            #     don_values.update(
            #         first_name=metadata['don_first_name'],
            #         last_name=metadata['don_last_name'],
            #         title=metadata['don_title'],
            #         address=metadata['don_address'],
            #         city=metadata['don_city'],
            #         postcode=metadata['don_postcode'],
            #     )
            # await conn.fetchval_b(
            #     'INSERT INTO donations (:values__names) VALUES :values',
            #     values=Values(**don_values)
            # )
    if metadata.purpose == MetadataPurpose.buy_tickets:
        await request.app['donorfy_actor'].tickets_booked(action_id)
        await request.app['email_actor'].send_event_conf(action_id)

    stripe_customer_id, stripe_secret_key = await conn.fetchrow(
        """
        SELECT stripe_customer_id, stripe_secret_key
        FROM users AS u
        JOIN companies c on u.company = c.id
        WHERE u.id=$1 AND c.id=$2
        """,
        metadata.user_id, company_id
    )
    with catch_stripe_errors():
        stripe = StripeClient(request.app, stripe_secret_key)
        await stripe.post(
            f'payment_methods/{payment_method_id}/attach',
            customer=stripe_customer_id,
        )
    return Response(status=204)


async def get_payment_method_details(request):
    payment_method_id = request.match_info['payment_method']
    data = await get_stripe_payment_method(
        payment_method_id=payment_method_id,
        company_id=request['company_id'],
        user_id=request['session']['user_id'],
        app=request.app,
        conn=request['conn']
    )
    return json_response(**data)


class UpdatePaymentIntent(UpdateViewAuth):
    class Model(BaseModel):
        payment_method: str

    async def execute(self, m: Model):
        stripe_customer_id, stripe_secret_key = await self.conn.fetchrow(
            """
            SELECT stripe_customer_id, stripe_secret_key
            FROM users AS u
            JOIN companies c on u.company = c.id
            WHERE u.id=$1 AND c.id=$2
            """,
            self.session['user_id'], self.request['company_id']
        )
        payment_intent_id = await self.app['redis'].get(payment_intent_key(self.request.match_info['client_secret']))
        # debug(self.request.match_info, payment_intent_id)
        with catch_stripe_errors():
            stripe = StripeClient(self.app, stripe_secret_key)
            await stripe.post(
                f'payment_intents/{payment_intent_id}',
                payment_method=m.payment_method,
            )
