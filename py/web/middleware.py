import contextlib
import logging
import re
from time import time

from aiohttp.hdrs import METH_GET, METH_OPTIONS, METH_POST
from aiohttp.web_exceptions import HTTPException, HTTPInternalServerError
from aiohttp.web_middlewares import middleware
from aiohttp.web_response import Response
from aiohttp_session import get_session
from asyncpg import PostgresError

from shared.utils import lenient_json

from .auth import remove_port
from .utils import HEADER_CROSS_ORIGIN, JSON_CONTENT_TYPE, JsonErrors, get_ip, request_root

logger = logging.getLogger('nosht.middleware')


def exc_extra(exc):
    exception_extra = getattr(exc, 'extra', None)
    if exception_extra:
        try:
            v = exception_extra()
        except Exception:
            pass
        else:
            return lenient_json(v)


async def log_extra(request, response=None, **more):
    request_text = response_text = None
    with contextlib.suppress(Exception):  # UnicodeDecodeError or HTTPRequestEntityTooLarge maybe other things too
        request_text = await request.text()
    with contextlib.suppress(Exception):  # UnicodeDecodeError
        response_text = lenient_json(getattr(response, 'text', None))
    start = request.get('start_time') or time()
    data = dict(
        request_duration=f'{(time() - start) * 1000:0.2f}ms',
        request=dict(
            url=str(request.rel_url),
            user_agent=request.headers.get('User-Agent'),
            method=request.method,
            host=request.host,
            headers=dict(request.headers),
            text=lenient_json(request_text),
        ),
        response=dict(
            status=getattr(response, 'status', None),
            headers=dict(getattr(response, 'headers', {})),
            text=response_text,
        ),
        **more,
    )

    tags = dict()
    user = dict(ip_address=get_ip(request))
    session = await get_session(request)
    user_id = session.get('user_id')
    if user_id:
        with contextlib.suppress(PostgresError):  # eg. InFailedSQLTransactionError
            async with request.app['main_app']['pg'].acquire() as conn:
                user_info = await conn.fetchrow(
                    """
                    SELECT u.email, c.name AS company_name, c.id AS company_id, role, status,
                    full_name(u.first_name, u.last_name) as username
                    FROM users AS u
                    JOIN companies AS c ON u.company = c.id
                    WHERE u.id=$1
                    """,
                    user_id,
                )
                if user_info:
                    tags.update(
                        user_status=user_info['status'], user_role=user_info['role'], company=user_info['company_id'],
                    )
                    user.update(user_info)
    return dict(data=data, user=user, tags=tags)


async def log_warning(request, response):
    logger.warning(
        '%s %d',
        request.rel_url,
        response.status,
        extra={'fingerprint': [request.rel_url, str(response.status)], **await log_extra(request, response)},
    )


def should_warn(r):
    return r.status > 310 and r.status not in {401, 402, 404, 470}


def get_request_start(request):
    try:
        return float(request.headers.get('X-Request-Start', '.')) / 1000
    except ValueError:
        return time()


@middleware
async def error_middleware(request, handler):
    request['start_time'] = get_request_start(request)
    try:
        r = await handler(request)
    except HTTPException as e:
        if should_warn(e):
            await log_warning(request, e)
        raise
    except Exception as exc:
        logger.exception(
            '%s: %s',
            exc.__class__.__name__,
            exc,
            extra={
                'fingerprint': [exc.__class__.__name__, str(exc)],
                **await log_extra(request, exception_extra=exc_extra(exc)),
            },
        )
        raise HTTPInternalServerError()
    else:
        if should_warn(r):
            await log_warning(request, r)
    return r


@middleware
async def pg_middleware(request, handler):
    async with request.app['pg'].acquire() as conn:
        request['conn'] = conn
        return await handler(request)


USER_COMPANY_SQL = """
SELECT c.id
FROM users
JOIN companies AS c ON c.id=company
WHERE c.domain=$1 AND users.id=$2
"""


@middleware
async def user_middleware(request, handler):
    conn = request['conn']
    request['session'] = await get_session(request)
    user_id = request['session'].get('user_id')

    # port is removed as won't matter and messes up on localhost:3000/8000
    host = remove_port(request.host)
    company_id = None
    if user_id:
        company_id = await conn.fetchval(USER_COMPANY_SQL, host, user_id)
        if not company_id:
            request['session'].invalidate()

    if not company_id:
        company_id = await conn.fetchval('SELECT id FROM companies WHERE domain=$1', host)
        if not company_id:
            raise JsonErrors.HTTPBadRequest(message='no company found for this host')
    request['company_id'] = company_id
    return await handler(request)


NO_CHECKS = {
    '/api/ses-webhook/',
    '/api/stripe/webhook/',
}
UPLOAD_PATHS = (
    re.compile(r'/api/companies/upload/(?:image|logo)/'),
    re.compile(r'/api/categories/\d+/add-image/'),
    re.compile(r'/api/events/\d+/set-image/(new|secondary|description)/'),
    re.compile(r'/api/donation-options/\d+/upload-image/'),
)
CROSS_ORIGIN_URLS = {
    '/api/login/',
    '/api/set-password/',
}


def csrf_checks(request):
    """
    content-type, origin and referrer checks for CSRF
    """
    if request.path in NO_CHECKS:
        yield True
        return

    ct = request.headers.get('Content-Type')
    if any(p.fullmatch(request.path) for p in UPLOAD_PATHS):
        yield ct.startswith('multipart/form-data; boundary')
    else:
        yield ct == JSON_CONTENT_TYPE

    origin = request.headers.get('Origin')
    path_root = request_root(request)
    if request.path in CROSS_ORIGIN_URLS:
        yield origin == 'null' or origin is None or request.host.startswith('localhost')
    else:
        # origin and host ports differ on localhost when testing, so ignore this case
        yield origin == path_root or origin is None or request.host.startswith('localhost')

        # iframe requests don't include a referrer, thus this isn't checked for cross origin urls
        r = request.headers.get('Referer', '')
        yield r.startswith(path_root + '/')


@middleware
async def csrf_middleware(request, handler):
    if request.method == METH_OPTIONS:
        if 'Access-Control-Request-Method' in request.headers:
            if (
                request.headers.get('Access-Control-Request-Method') == METH_POST
                and request.path in CROSS_ORIGIN_URLS
                and request.headers.get('Access-Control-Request-Headers').lower() == 'content-type'
            ):
                # can't check origin here as it's null since the iframe's requests are "cross-origin"
                headers = {'Access-Control-Allow-Headers': 'Content-Type', **HEADER_CROSS_ORIGIN}
                return Response(text='ok', headers=headers)
            else:
                raise JsonErrors.HTTPForbidden(error='Access-Control checks failed', headers_=HEADER_CROSS_ORIGIN)
    elif request.method != METH_GET and not all(csrf_checks(request)):
        raise JsonErrors.HTTPForbidden(error='CSRF failure', headers_=HEADER_CROSS_ORIGIN)

    return await handler(request)
