import json
from time import time

import bcrypt
from aiohttp_session import new_session
from cryptography.fernet import InvalidToken
from pydantic import BaseModel, EmailStr, constr

from web.auth import invalidate_session, is_auth, record_event
from web.utils import JsonErrors, get_ip, json_response, parse_request


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
