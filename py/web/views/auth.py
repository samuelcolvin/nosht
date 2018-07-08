import json
from time import time

import bcrypt
from aiohttp_session import new_session
from buildpg import Values
from cryptography.fernet import InvalidToken
from pydantic import BaseModel, EmailStr, constr

from web.auth import (FacebookSiwModel, GoogleSiwModel, facebook_get_details, google_get_details, invalidate_session,
                      is_auth, record_event, validate_email)
from web.utils import JsonErrors, json_response, parse_request, raw_json_response


class LoginModel(BaseModel):
    email: EmailStr
    password: constr(max_length=100)


get_user_sql = """
SELECT id, COALESCE(first_name || ' ' || last_name, email) AS name, email, role, status, password_hash
FROM users
WHERE company=$1 AND email=$2 AND status='active' AND role!='guest'
"""


def successful_login(user, app, headers_=None):
    auth_session = {'user_id': user['id'], 'user_role': user['role'], 'last_active': int(time())}
    auth_token = app['auth_fernet'].encrypt(json.dumps(auth_session).encode()).decode()
    return json_response(status='success', auth_token=auth_token, user=user, headers_=headers_)


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
            return successful_login(user, request.app, h)

    return json_response(status='invalid', message='invalid email or password', headers_=h, status_=470)


LOGIN_MODELS = {
    'facebook': (FacebookSiwModel, facebook_get_details),
    'google': (GoogleSiwModel, google_get_details),
}


async def login_with(request):
    model, siw_method = LOGIN_MODELS[request.match_info['site']]
    m = await parse_request(request, model)
    details = await siw_method(m, app=request.app)
    email = details['email']
    r = await request['conn'].fetchrow(get_user_sql, request['company_id'], email)
    if r:
        user = dict(r)
        return successful_login(user, request.app)
    return json_response(status='invalid', message=f'User with email address "{email}" not found', status_=470)


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

    await record_event(request, session['user_id'], 'login')
    return json_response(status='success')


@is_auth
async def logout(request):
    await invalidate_session(request, 'logout')
    return json_response(status='success')


class EmailModel(BaseModel):
    email: EmailStr


async def check_email(m: EmailModel, app):
    if await validate_email(m.email, app.loop):
        return m.dict()
    else:
        raise JsonErrors.HTTP470(status='invalid', message=f'"{m.email}" doesn\'t look like an active email address.')


SIGNIN_MODELS = {
    'email': (EmailModel, check_email),
    'facebook': (FacebookSiwModel, facebook_get_details),
    'google': (GoogleSiwModel, google_get_details),
}
CREATE_USER_SQL = """
INSERT INTO users (:values__names) VALUES :values
ON CONFLICT (company, email) DO UPDATE SET email=EXCLUDED.email
RETURNING id, status
"""
GET_GUEST_USER_SQL = """
SELECT json_build_object('user', row_to_json(user_data))
FROM (
  SELECT id, COALESCE(first_name || ' ' || last_name, email) AS name, email, role
  FROM users
  WHERE company=$1 AND id=$2
) AS user_data;
"""


async def guest_login(request):
    model, siw_method = SIGNIN_MODELS[request.match_info['site']]
    m = await parse_request(request, model)
    details = await siw_method(m, app=request.app)

    company_id = request['company_id']
    user_id, status = await request['conn'].fetchrow_b(
        CREATE_USER_SQL,
        values=Values(
            company=company_id,
            role='guest',
            email=details['email'],
            first_name=details.get('first_name'),
            last_name=details.get('last_name'),
        )
    )
    if status == 'suspended':
        raise JsonErrors.HTTPBadRequest(message='user suspended')

    session = await new_session(request)
    session.update({'user_id': user_id, 'user_role': 'guest', 'last_active': int(time())})

    await record_event(request, user_id, 'guest-signin')

    json_str = await request['conn'].fetchval(GET_GUEST_USER_SQL, company_id, user_id)
    return raw_json_response(json_str)
