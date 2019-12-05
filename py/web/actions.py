import json

from shared.actions import ActionTypes

from .utils import get_ip


def actions_request_extra(request):
    return dict(url=str(request.url), ip=get_ip(request), ua=request.headers.get('User-Agent'))


async def record_action(request, user_id, action_type: ActionTypes, *, event_id=None, **extra):
    extra = json.dumps({**actions_request_extra(request), **extra})
    await request['conn'].execute(
        'INSERT INTO actions (company, user_id, event, type, extra) VALUES ($1, $2, $3, $4, $5)',
        request['company_id'],
        user_id,
        event_id and int(event_id),
        action_type.value,
        extra,
    )


async def record_action_id(request, user_id, action_type: ActionTypes, *, event_id=None, **extra):
    extra = json.dumps({**actions_request_extra(request), **extra})
    return await request['conn'].fetchval(
        'INSERT INTO actions (company, user_id, event, type, extra) VALUES ($1, $2, $3, $4, $5) RETURNING id',
        request['company_id'],
        user_id,
        event_id and int(event_id),
        action_type.value,
        extra,
    )
