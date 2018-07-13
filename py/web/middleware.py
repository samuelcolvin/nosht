import logging
import re
from time import time

from aiohttp.web_exceptions import HTTPException, HTTPInternalServerError
from aiohttp.web_middlewares import middleware
from aiohttp_session import get_session
from buildpg.asyncpg import BuildPgConnection

from .utils import JsonErrors, get_ip

logger = logging.getLogger('nosht.web.mware')


async def log_extra(start, request, response=None, **more):
    try:
        response_text = await request.text()
    except Exception:
        # UnicodeDecodeError or HTTPRequestEntityTooLarge maybe other things too
        response_text = None
    return dict(
        request=dict(
            url=str(request.rel_url),
            user_agent=request.headers.get('User-Agent'),
            duration=time() - start,
            ip=get_ip(request),
            method=request.method,
            host=request.host,
            headers=dict(request.headers),
            text=response_text,
        ),
        response=dict(
            status=getattr(response, 'status', None),
            headers=dict(getattr(response, 'headers', {})),
            text=getattr(response, 'text', None),
        ),
        **more
    )


async def log_warning(start, request, response):
    logger.warning('%s %d', request.rel_url, response.status, extra={
        'fingerprint': [request.rel_url, str(response.status)],
        'data': await log_extra(start, request, response)
    })


def should_warn(r):
    return r.status > 310 and r.status not in {401, 404}


def get_request_start(request):
    try:
        return float(request.headers.get('X-Request-Start', '.')) / 1000
    except ValueError:
        return time()


@middleware
async def error_middleware(request, handler):
    start = get_request_start(request)
    try:
        http_exception = getattr(request.match_info, 'http_exception', None)
        if http_exception:
            raise http_exception
        else:
            r = await handler(request)
    except HTTPException as e:
        if should_warn(e):
            await log_warning(start, request, e)
        raise
    except BaseException as e:
        exception_extra = getattr(e, 'extra', None)
        if exception_extra:
            try:
                exception_extra = exception_extra()
            except Exception:
                pass
        logger.exception('%s: %s', e.__class__.__name__, e, extra={
            'fingerprint': [e.__class__.__name__, str(e)],
            'data': await log_extra(start, request, exception_extra=exception_extra)
        })
        raise HTTPInternalServerError()
    else:
        if should_warn(r):
            await log_warning(start, request, r)
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
REMOVE_PORT = re.compile(r':\d{2,}$')


@middleware
async def host_middleware(request, handler):
    conn: BuildPgConnection = request['conn']
    request['session'] = await get_session(request)
    user_id = request['session'].get('user_id')

    # port is removed as won't matter and messes up on localhost:3000/8000
    host = REMOVE_PORT.sub('', request.host)
    if user_id:
        company_id = await conn.fetchval(USER_COMPANY_SQL, host, user_id)
        msg = 'company not found for this host and user'
    else:
        company_id = await conn.fetchval('SELECT id FROM companies WHERE domain=$1', host)
        msg = 'no company found for this host'
    if not company_id:
        return JsonErrors.HTTPBadRequest(message=msg)
    request['company_id'] = company_id
    return await handler(request)
