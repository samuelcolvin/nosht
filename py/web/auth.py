import json
from functools import wraps
from time import time

from web.utils import JsonErrors, get_ip

record_event = """
INSERT INTO actions (company, user_id, type, extra) VALUES ($1, $2, $3, $4)
"""


async def invalidate_session(request, reason):
    session = request['session']
    extra = json.dumps({
        'ip': get_ip(request),
        'ua': request.headers.get('User-Agent'),
        'age': int(time()) - session.created,
        'reason': reason,
    })
    user_id = session['user_id']
    session.invalidate()
    await request['conn'].execute(record_event, request['company_id'], user_id, 'logout', extra)


async def check_session(request, *roles):
    session = request['session']
    user_role = session.get('user_role')
    if user_role is None:
        raise JsonErrors.HTTPUnauthorized(message='Authentication required to view this page')

    if user_role not in roles:
        raise JsonErrors.HTTPForbidden(message='role must be in: {}'.format(', '.join(roles)))

    last_active = session['last_active']
    now = int(time())
    age = now - last_active
    if age > request.app['settings'].cookie_max_age:
        await invalidate_session(request, 'expired')
        raise JsonErrors.HTTPUnauthorized(message="Session expired, you'll need to login again")
    elif age > request.app['settings'].cookie_update_age:
        session['last_active'] = now


def permission_wrapper(coro, *roles):
    @wraps(coro)
    async def roles_permissions_wrapper(request):
        await check_session(request, *roles)
        return await coro(request)

    return roles_permissions_wrapper


def is_admin(coro):
    return permission_wrapper(coro, 'admin')


def is_host(coro):
    return permission_wrapper(coro, 'host')


def is_admin_or_host(coro):
    return permission_wrapper(coro, 'admin', 'host')


def is_auth(coro):
    return permission_wrapper(coro, 'admin', 'host', 'guest')
