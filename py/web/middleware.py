import logging

from aiohttp.web_exceptions import HTTPException, HTTPInternalServerError
from aiohttp.web_middlewares import middleware
from asyncpg import Connection

from .utils import JsonErrors

logger = logging.getLogger('nosht.web.mware')
IP_HEADER = 'X-Forwarded-For'


def get_ip(request):
    ips = request.headers.get(IP_HEADER)
    if ips:
        return ips.split(',', 1)[0].strip(' ')
    else:
        return request.remote


async def log_extra(request, response=None):
    return {'data': dict(
        request_url=str(request.rel_url),
        request_ip=get_ip(request),
        request_method=request.method,
        request_host=request.host,
        request_headers=dict(request.headers),
        request_text=await request.text(),
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


@middleware
async def host_middleware(request, handler):
    conn: Connection = request['conn']
    company_id = await conn.fetchval('SELECT id FROM companies WHERE domain=$1', request.host)
    if not company_id:
        return JsonErrors.HTTPNotFound(message='no company found for this host')
    request['company_id'] = company_id
    return await handler(request)
