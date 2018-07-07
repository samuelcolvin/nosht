import asyncio
import json
import hashlib
import hmac
import logging
import secrets
from functools import wraps
from time import time
from urllib.parse import urlencode

import aiodns
from async_timeout import timeout
from google.auth import jwt as google_jwt
from google.auth._helpers import padded_urlsafe_b64decode
from google.oauth2.id_token import _GOOGLE_OAUTH2_CERTS_URL
from pydantic import BaseModel, constr

from shared.settings import Settings
from web.utils import JsonErrors, get_ip

logger = logging.getLogger('nosht.auth')
record_event_sql = """
INSERT INTO actions (company, user_id, type, extra) VALUES ($1, $2, $3, $4)
"""


async def record_event(request, user_id, event, **extra):
    extra.update(
        ip=get_ip(request),
        ua=request.headers.get('User-Agent')
    )
    extra = json.dumps(extra)
    await request['conn'].execute(record_event_sql, request['company_id'], user_id, event, extra)


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
    await request['conn'].execute(record_event_sql, request['company_id'], user_id, 'logout', extra)


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


async def validate_email(email, loop):
    """
    check an email is likely to exist

    could do SMTP looks ups: https://gist.github.com/samuelcolvin/3652427c07fac775d0cdc8af127c0ed1
    but not really worth it
    """
    domain = email.split('@', 1)[1]
    resolver = aiodns.DNSResolver(loop=loop)
    try:
        with timeout(2, loop=loop):
            await resolver.query(domain, 'MX')
    except (aiodns.error.DNSError, ValueError, asyncio.TimeoutError) as e:
        logger.info('looking up "%s": error %s %s', email, e.__class__.__name__, e)
        return False
    else:
        return True


class GoogleSiwModel(BaseModel):
    id_token: constr(min_length=200, max_length=2000)


async def google_get_details(m: GoogleSiwModel, app):
    settings: Settings = app['settings']
    async with app['session'].get(_GOOGLE_OAUTH2_CERTS_URL) as r:
        assert r.status == 200, r.status
        certs = await r.json()
    id_info = google_jwt.decode(m.id_token, certs=certs, audience=settings.google_siw_client_key)

    # this should happen very rarely, if it does someone is doing something nefarious or things have gone very wrong
    assert id_info['iss'] in {'accounts.google.com', 'https://accounts.google.com'}, 'wrong google iss'
    assert id_info['email_verified'], 'google email not verified'

    # TODO image
    return {
        'email': id_info['email'].lower(),
        'first_name': id_info.get('given_name'),
        'last_name': id_info.get('family_name'),
    }


class FacebookSiwModel(BaseModel):
    signed_request: bytes
    access_token: str
    user_id: str

    class Config:
        fields = {
            'signed_request': 'signedRequest',
            'access_token': 'accessToken',
            'user_id': 'userID'
        }


async def facebook_get_details(m: FacebookSiwModel, app):
    try:
        sig, data = m.signed_request.split(b'.', 1)
    except ValueError:
        raise JsonErrors.HTTPBadRequest(message='"signedRequest" not correctly formed')

    settings: Settings = app['settings']
    expected_sig = hmac.new(settings.facebook_siw_app_secret, data, hashlib.sha256).digest()
    if not secrets.compare_digest(padded_urlsafe_b64decode(sig), expected_sig):
        raise JsonErrors.HTTPBadRequest(message='"signedRequest" not correctly signed')

    signed_data = json.loads(padded_urlsafe_b64decode(data).decode())

    # can add 'picture' here, but it seems to be low res.
    details_url = f'https://graph.facebook.com/v3.0/me?' + urlencode({
        'access_token': m.access_token,
        'fields': ['email', 'first_name', 'last_name']
    })
    async with app['session'].get(details_url) as r:
        assert r.status == 200, r.status
        response_data = await r.json()

    if not (response_data['id'] == signed_data['user_id'] == m.user_id):
        raise JsonErrors.HTTPBadRequest(message='facebook userID not consistent')
    if not response_data.get('email') or not response_data.get('last_name'):
        raise JsonErrors.HTTPBadRequest(message='Your Facebook profile needs to have both a last name and '
                                                'email address associated with it.')

    return {
        'email': response_data['email'].lower(),
        'first_name': response_data['first_name'],
        'last_name': response_data['last_name'],
    }
