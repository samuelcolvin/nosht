import asyncio
import hashlib
import hmac
import json
import logging
import re
from functools import wraps
from secrets import compare_digest
from time import time
from urllib.parse import urlencode

import aiodns
from async_timeout import timeout
from google.auth import jwt as google_jwt
from google.auth._helpers import padded_urlsafe_b64decode
from pydantic import BaseModel

from shared.settings import Settings
from shared.utils import RequestError

from .actions import ActionTypes, record_action
from .utils import JsonErrors, get_ip

logger = logging.getLogger('nosht.auth')
REMOVE_PORT = re.compile(r':\d{2,}$')


def remove_port(url):
    return REMOVE_PORT.sub('', url)


async def invalidate_session(request, reason):
    session = request['session']
    extra = {'age': int(time()) - session.created, 'reason': reason, 'email': session.get('email')}
    user_id = session.get('user_id')
    session.invalidate()
    await record_action(request, user_id, ActionTypes.logout, **extra)


async def check_session(request, *roles):
    session = request['session']
    role = session.get('role')
    if role is None:
        raise JsonErrors.HTTPUnauthorized(message='Authentication required to view this page')

    if role not in roles:
        raise JsonErrors.HTTPForbidden(message='role must be: {}'.format(', '.join(roles)))

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


class GrecaptchaModel(BaseModel):
    grecaptcha_token: str


class GoogleSiwModel(BaseModel):
    id_token: str


async def google_get_details(m: GoogleSiwModel, app):
    settings: Settings = app['settings']
    async with app['http_client'].get(settings.google_siw_url) as r:
        if r.status != 200:
            raise RequestError(r.status, settings.google_siw_url, text=await r.text())
        certs = await r.json()
    try:
        id_info = google_jwt.decode(m.id_token, certs=certs, audience=settings.google_siw_client_key)
    except ValueError as e:
        logger.warning('google jwt decode error: %s', e)
        raise JsonErrors.HTTPBadRequest(message='google jwt decode error') from e

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
        fields = {'signed_request': 'signedRequest', 'access_token': 'accessToken', 'user_id': 'userID'}


async def facebook_get_details(m: FacebookSiwModel, app):
    try:
        sig, data = m.signed_request.split(b'.', 1)
    except ValueError:
        raise JsonErrors.HTTPBadRequest(message='"signedRequest" not correctly formed')

    settings: Settings = app['settings']
    expected_sig = hmac.new(settings.facebook_siw_app_secret, data, hashlib.sha256).digest()
    if not compare_digest(padded_urlsafe_b64decode(sig), expected_sig):
        raise JsonErrors.HTTPBadRequest(message='"signedRequest" not correctly signed')

    signed_data = json.loads(padded_urlsafe_b64decode(data).decode())

    # can add 'picture' here, but it seems to be low res.
    details_url = (
        settings.facebook_siw_url
        + '?'
        + urlencode({'access_token': m.access_token, 'fields': ['email', 'first_name', 'last_name']})
    )
    async with app['http_client'].get(details_url) as r:
        if r.status != 200:
            raise RequestError(r.status, details_url, text=await r.text())
        response_data = await r.json()

    if not (response_data['id'] == signed_data['user_id'] == m.user_id):
        raise JsonErrors.HTTPBadRequest(message='facebook userID not consistent')
    if not response_data.get('email') or not response_data.get('last_name'):
        raise JsonErrors.HTTPBadRequest(
            message='Your Facebook profile needs to have both a last name and email address associated with it.'
        )

    return {
        'email': response_data['email'].lower(),
        'first_name': response_data['first_name'],
        'last_name': response_data['last_name'],
    }


async def check_grecaptcha(m: GrecaptchaModel, request, *, error_headers=None):
    settings: Settings = request.app['settings']
    client_ip = get_ip(request)
    if not m.grecaptcha_token:
        logger.warning('grecaptcha not provided, path="%s" ip=%s', request.path, client_ip)
        raise JsonErrors.HTTPBadRequest(message='No recaptcha value', headers_=error_headers)

    post_data = {
        'secret': settings.grecaptcha_secret,
        'response': m.grecaptcha_token,
        'remoteip': client_ip,
    }
    async with request.app['http_client'].post(settings.grecaptcha_url, data=post_data) as r:
        if r.status != 200:
            raise RequestError(r.status, settings.grecaptcha_url, text=await r.text())
        data = await r.json()

    if data['success'] and remove_port(request.host) == data['hostname']:
        logger.info('grecaptcha success')
    else:
        logger.warning(
            'grecaptcha failure, path="%s" ip=%s response=%s',
            request.path,
            client_ip,
            data,
            extra={'data': {'grecaptcha_response': data}},
        )
        raise JsonErrors.HTTPBadRequest(message='Invalid recaptcha value', headers_=error_headers)
