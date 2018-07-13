import json

from shared.db import ActionTypes

from .utils import get_ip


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
    return await request['conn'].fetchval(
        'INSERT INTO actions (company, user_id, type, extra) VALUES ($1, $2, $3, $4) RETURNING id',
        request['company_id'], user_id, action_type.value, extra
    )
