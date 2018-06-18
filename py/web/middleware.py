import logging

from aiohttp.web_exceptions import HTTPException, HTTPInternalServerError
from aiohttp.web_middlewares import middleware
from aiohttp_session import get_session
from buildpg.asyncpg import BuildPgConnection

from .utils import JsonErrors, get_ip

logger = logging.getLogger('nosht.web.mware')


async def log_extra(request, response=None):
    try:
        response_text = await request.text()
    except Exception:
        # UnicodeDecodeError or HTTPRequestEntityTooLarge by maybe other things too
        response_text = None
    return {'data': dict(
        request_url=str(request.rel_url),
        request_ip=get_ip(request),
        request_method=request.method,
        request_host=request.host,
        request_headers=dict(request.headers),
        request_text=response_text,
        response_status=getattr(response, 'status', None),
        response_headers=dict(getattr(response, 'headers', {})),
        response_text=getattr(response, 'text', None)
    )}


async def log_warning(request, response):
    ip, ua = get_ip(request), request.headers.get('User-Agent')
    logger.warning('%s %d from %s ua: "%s"', request.rel_url, response.status, ip, ua, extra={
        'fingerprint': [request.rel_url, str(response.status)],
        'data': await log_extra(request, response)
    })


@middleware
async def error_middleware(request, handler):
    try:
        http_exception = getattr(request.match_info, 'http_exception', None)
        if http_exception:
            raise http_exception
        else:
            r = await handler(request)
    except HTTPException as e:
        if e.status > 310:
            await log_warning(request, e)
        raise
    except BaseException as e:
        logger.exception('%s: %s', e.__class__.__name__, e, extra={
            'fingerprint': [e.__class__.__name__, str(e)],
            'data': await log_extra(request)
        })
        raise HTTPInternalServerError()
    else:
        if r.status > 310:
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
async def host_middleware(request, handler):
    conn: BuildPgConnection = request['conn']
    request['session'] = await get_session(request)
    user_id = request['session'].get('user_id')
    if user_id:
        company_id = await conn.fetchval(USER_COMPANY_SQL, request.host, user_id)
        msg = 'company not found for this host and user'
    else:
        company_id = await conn.fetchval('SELECT id FROM companies WHERE domain=$1', request.host)
        msg = 'no company found for this host'
    if not company_id:
        return JsonErrors.HTTPNotFound(message=msg)
    request['company_id'] = company_id
    return await handler(request)
