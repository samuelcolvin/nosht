import json
from functools import wraps
from time import time

import bcrypt
from aiohttp_session import new_session
from cryptography.fernet import InvalidToken
from pydantic import BaseModel, EmailStr, constr

from web.utils import JsonErrors, get_ip, json_response, parse_request


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


async def check_session(request, roles):
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
        await check_session(request, roles)
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


class LoginModel(BaseModel):
    email: EmailStr
    password: constr(max_length=100)


get_user_sql = """
SELECT id, first_name || ' ' || last_name AS name, role, status, password_hash
FROM users
WHERE company=$1 AND email=$2 AND status='active'
"""


async def login(request):
    h = {'Access-Control-Allow-Origin': 'null'}
    m = await parse_request(request, LoginModel, error_headers=h)
    if m.password != request.app['settings'].dummy_password:
        r = await request['conn'].fetchrow(get_user_sql, request['company_id'], m.email)
        if r:
            user = dict(r)
            password_hash = user.pop('password_hash')
        else:
            # still try hashing to avoid timing attack
            user = dict()
            password_hash = None

        password_hash = password_hash or request.app['dummy_password_hash']

        if bcrypt.checkpw(m.password.encode(), password_hash.encode()):
            auth_session = {'user_id': user['id'], 'user_role': user['role'], 'last_active': int(time())}
            auth_token = request.app['auth_fernet'].encrypt(json.dumps(auth_session).encode()).decode()
            return json_response(status='success', auth_token=auth_token, user=user, headers_=h)

    return json_response(status='invalid', message='invalid email or password', headers_=h, status_=470)


class AuthTokenModel(BaseModel):
    token: bytes


record_event = """
INSERT INTO actions (company, user_id, type, extra) VALUES ($1, $2, $3, $4)
"""


async def authenticate_token(request):
    m = await parse_request(request, AuthTokenModel)
    try:
        auth_session = json.loads(request.app['auth_fernet'].decrypt(m.token, ttl=10).decode())
    except InvalidToken:
        raise JsonErrors.HTTPBadRequest(message='invalid auth token')
    session = await new_session(request)
    session.update(auth_session)
    extra = json.dumps({
        'ip': get_ip(request),
        'ua': request.headers.get('User-Agent')
    })
    await request['conn'].execute(record_event, request['company_id'], session['user_id'], 'login', extra)
    return json_response(status='success')


@is_auth
async def logout(request):
    await invalidate_session(request, 'logout')
    return json_response(status='success')
