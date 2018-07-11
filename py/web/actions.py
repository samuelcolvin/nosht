import json
from enum import Enum

from web.utils import get_ip


class ActionTypes(str, Enum):
    login = 'login'
    guest_signin = 'guest-signin'
    logout = 'logout'
    reserve_tickets = 'reserve-tickets'
    buy_tickets = 'buy-tickets'
    edit_event = 'edit-event'
    edit_other = 'edit-other'
    unsubscribe = 'unsubscribe'


def actions_request_extra(request):
    return dict(
        url=str(request.url),
        ip=get_ip(request),
        ua=request.headers.get('User-Agent')
    )


async def record_action(request, user_id, action_type: ActionTypes, **extra):
    extra = json.dumps({**actions_request_extra(request), **extra})
    await request['conn'].execute(
        'INSERT INTO actions (company, user_id, type, extra) VALUES ($1, $2, $3, $4)',
        request['company_id'], user_id, action_type.value, extra)


async def record_action_id(request, user_id, action_type: ActionTypes, **extra):
    extra = json.dumps({**actions_request_extra(request), **extra})
    await request['conn'].fetchval(
        'INSERT INTO actions (company, user_id, type, extra) VALUES ($1, $2, $3, $4) RETURNING id',
        request['company_id'], user_id, action_type.value, extra)
