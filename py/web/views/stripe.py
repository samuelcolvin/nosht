import json
import logging
from datetime import datetime, timezone
from enum import Enum

from aiohttp.web_exceptions import HTTPSuccessful
from aiohttp.web_response import Response
from buildpg import Values
from buildpg.asyncpg import BuildPgConnection, CheckViolationError
from pydantic import BaseModel, ValidationError

from shared.actions import ActionTypes
from shared.settings import Settings
from web.stripe import get_stripe_payment_method, stripe_webhook_body
from web.utils import json_response

logger = logging.getLogger('nosht.views.stripe')


class MetadataPurpose(str, Enum):
    buy_tickets = 'buy-tickets'
    donate = 'donate'
    donate_direct = 'donate-direct'


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

    company_id: int = request['company_id']

    data = webhook['data']['object']
    metadata = data['metadata']
    if 'purpose' not in metadata:
        logger.info('no "purpose" in webhook metadata, probably not a nosht payment intent')
        return Response(text='no purpose in metadata', status=240)

    try:
        metadata = MetadataModel(**metadata)
    except ValidationError as e:
        logger.warning('invalid webhook metadata: %s', e, extra={'webhook': webhook, 'error': e.errors()})
        return Response(text=f'invalid metadata: {e}', status=250)

    charge = data['charges']['data'][0]
    card = charge['payment_method_details']['card']
    action_extra = json.dumps(
        {
            'charge_id': charge['id'],
            'stripe_balance_transaction': charge['balance_transaction'],
            'brand': card['brand'],
            'card_last4': card['last4'],
            'card_expiry': f"{card['exp_month']}/{card['exp_year'] - 2000}",
            '3DS': card['three_d_secure'],
            'payment_metadata': metadata.dict(),
        }
    )

    if metadata.purpose == MetadataPurpose.buy_tickets:
        try:
            async with request['conn'].transaction():
                action_id = await _complete_purchase(request, metadata, webhook, company_id, action_extra)
        except CheckViolationError as e:
            if 'violates check constraint "ticket_limit_check"' in str(e):
                raise http_exc(text='ticket limit exceeded', status=234) from e
            else:  # pragma: no cover
                raise
    else:
        async with request['conn'].transaction():
            action_id = await _complete_donation(request, metadata, webhook, company_id, action_extra)

    if metadata.purpose == MetadataPurpose.buy_tickets:
        await request.app['donorfy_actor'].tickets_booked(action_id)
        await request.app['email_actor'].send_event_conf(action_id)
    else:
        await request.app['donorfy_actor'].donation(action_id)
        await request.app['email_actor'].send_donation_thanks(action_id)
    return Response(status=204)


async def _complete_purchase(
    request, metadata: MetadataModel, webhook: dict, company_id: int, action_extra: str
) -> int:

    conn: BuildPgConnection = request['conn']
    settings: Settings = request.app['settings']
    r = await conn.fetchrow(
        'select status, created_ts from tickets where reserve_action=$1 for update', metadata.reserve_action_id
    )
    if not r:
        logger.warning('ticket %s not found', metadata.reserve_action_id, extra={'webhook': webhook})
        raise http_exc(text='ticket not found', status=231)
    ticket_status, ticket_created = r
    if ticket_status != 'reserved':
        logger.warning('ticket not in reserved state %r', ticket_status, extra={'webhook': webhook})
        raise http_exc(text='ticket not reserved', status=232)

    charge_created = datetime.fromtimestamp(webhook['data']['object']['charges']['data'][0]['created'], timezone.utc)
    payment_delay = (charge_created - ticket_created).total_seconds()
    if payment_delay > settings.ticket_ttl:
        logger.warning('ticket bought too late: %0.2fs', payment_delay, extra={'webhook': webhook})
        raise http_exc(text='ticket bought too late', status=233)

    action_id = await conn.fetchval_b(
        'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
        values=Values(
            company=company_id,
            user_id=metadata.user_id,
            type=ActionTypes.buy_tickets,
            event=metadata.event_id,
            extra=action_extra,
        ),
    )
    await conn.execute(
        "UPDATE tickets SET status='booked', booked_action=$1 WHERE reserve_action=$2",
        action_id,
        metadata.reserve_action_id,
    )
    await conn.execute('select check_tickets_remaining($1, $2)', metadata.event_id, settings.ticket_ttl)
    await conn.execute('delete from waiting_list where event=$1 and user_id=$2', metadata.event_id, metadata.user_id)
    return action_id


async def _complete_donation(
    request, metadata: MetadataModel, webhook: dict, company_id: int, action_extra: str
) -> int:
    conn: BuildPgConnection = request['conn']

    amount_cents = webhook['data']['object']['amount']

    r = await conn.fetchrow(
        """
        select extra->'gift_aid', extra->>'donation_option_id', extra->>'ticket_type_id', extra->>'complete'
        from actions where id=$1
        for update
        """,
        metadata.reserve_action_id,
    )
    if not r:
        logger.warning('no action found for action %s', metadata.reserve_action_id, extra={'webhook': webhook})
        raise http_exc(text='action not found', status=240)

    gift_aid_info, donation_option_id, ticket_type_id, complete = r
    if complete:
        logger.warning(
            'donation already performed with action %s', metadata.reserve_action_id, extra={'webhook': webhook}
        )
        raise http_exc(text='donation already performed', status=240)

    action_id = await conn.fetchval_b(
        'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
        values=Values(
            company=company_id,
            user_id=metadata.user_id,
            type=ActionTypes.donate,
            event=metadata.event_id,
            extra=action_extra,
        ),
    )
    gift_aid = bool(gift_aid_info)
    don_values = dict(amount=amount_cents / 100, gift_aid=gift_aid, action=action_id)
    if donation_option_id:
        don_values['donation_option'] = int(donation_option_id)
    else:
        don_values['ticket_type'] = int(ticket_type_id)

    if gift_aid:
        don_values.update(json.loads(gift_aid_info))
    await conn.fetchval_b('INSERT INTO donations (:values__names) VALUES :values', values=Values(**don_values))

    await conn.execute(
        """update actions set extra=extra || '{"complete": true}' where id=$1""", metadata.reserve_action_id,
    )
    return action_id


def http_exc(*, text, status):
    class CustomHTTPSuccessful(HTTPSuccessful):
        status_code = status

    return CustomHTTPSuccessful(text=text)


async def get_payment_method_details(request):
    payment_method_id = request.match_info['payment_method']
    data = await get_stripe_payment_method(
        payment_method_id=payment_method_id,
        company_id=request['company_id'],
        user_id=request['session']['user_id'],
        app=request.app,
        conn=request['conn'],
    )
    return json_response(**data)
