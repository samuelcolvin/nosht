import json
import logging
from enum import Enum

from aiohttp.web_response import Response
from buildpg import Values
from buildpg.asyncpg import BuildPgConnection
from pydantic import BaseModel

from shared.actions import ActionTypes
from shared.settings import Settings
from web.stripe import get_stripe_payment_method, stripe_webhook_body
from web.utils import json_response

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

    if hook_type != 'payment_intent.succeeded':
        logger.warning('unknown webhook %r', hook_type, extra={'webhook': webhook})
        return Response(text='unknown webhook type', status=230)

    settings: Settings = request.app['settings']
    conn: BuildPgConnection = request['conn']
    company_id: int = request['company_id']

    data = webhook['data']['object']
    amount_cents = data['amount']
    metadata = MetadataModel(**data['metadata'])

    charge = data['charges']['data'][0]
    card = charge['payment_method_details']['card']
    action_extra = json.dumps({
        'charge_id': charge['id'],
        'brand': card['brand'],
        'card_last4': card['last4'],
        'card_expiry': f"{card['exp_month']}/{card['exp_year'] - 2000}",
        '3DS': card['three_d_secure'],
        'payment_metadata': metadata.dict(),
    })

    async with conn.transaction():
        # mark the tickets paid in DB, then create charge in stripe, then finish transaction
        if metadata.purpose == MetadataPurpose.buy_tickets:
            ticket_status = await conn.fetchval(
                'select status from tickets where reserve_action=$1 for update', metadata.reserve_action_id
            )
            if ticket_status != 'reserved':
                logger.warning('ticket not in reserved state %r', ticket_status, extra={'webhook': webhook})
                return Response(text='ticket not reserved', status=231)

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
            await conn.execute('SELECT check_tickets_remaining($1, $2)', metadata.event_id, settings.ticket_ttl)
            await conn.execute(
                "UPDATE tickets SET status='booked', booked_action=$1 WHERE reserve_action=$2",
                action_id, metadata.reserve_action_id,
            )
        else:
            gift_aid_info, donation_option_id, complete = await conn.fetchrow(
                """
                select extra->'gift_aid', extra->>'donation_option_id', extra->>'complete'
                from actions where id=$1
                for update
                """,
                metadata.reserve_action_id
            )
            if complete:
                logger.warning('donation already performed with action %s', metadata.reserve_action_id,
                               extra={'webhook': webhook})
                return Response(text='donation already performed', status=232)

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
            gift_aid = bool(gift_aid_info)
            don_values = dict(
                donation_option=int(donation_option_id),
                amount=amount_cents / 100,
                gift_aid=gift_aid,
                action=action_id,
            )
            if gift_aid:
                don_values.update(json.loads(gift_aid_info))
            await conn.fetchval_b(
                'INSERT INTO donations (:values__names) VALUES :values',
                values=Values(**don_values)
            )
            await conn.execute(
                """update actions set extra=extra || '{"complete": true}' where id=$1""",
                metadata.reserve_action_id,
            )

    if metadata.purpose == MetadataPurpose.buy_tickets:
        await request.app['donorfy_actor'].tickets_booked(action_id)
        await request.app['email_actor'].send_event_conf(action_id)
    else:
        await request.app['donorfy_actor'].donation(action_id)
        await request.app['email_actor'].send_donation_thanks(action_id)
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
