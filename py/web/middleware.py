import json
import logging
import re
from time import time

from aiohttp.hdrs import METH_GET, METH_OPTIONS, METH_POST
from aiohttp.web_exceptions import HTTPException, HTTPInternalServerError
from aiohttp.web_middlewares import middleware
from aiohttp.web_response import Response
from aiohttp_session import get_session

from .utils import HEADER_CROSS_ORIGIN, JSON_CONTENT_TYPE, JsonErrors, get_ip, request_root

logger = logging.getLogger('nosht.web.mware')


def lenient_json(v):
    if isinstance(v, (str, bytes)):
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            pass
    return v


async def log_extra(start, request, response=None, **more):
    try:
        request_text = await request.text()
    except Exception:
        # UnicodeDecodeError or HTTPRequestEntityTooLarge maybe other things too
        request_text = None
    return dict(
        request=dict(
            url=str(request.rel_url),
            user_agent=request.headers.get('User-Agent'),
            duration=time() - start,
            ip=get_ip(request),
            method=request.method,
            host=request.host,
            headers=dict(request.headers),
            body=lenient_json(request_text),
        ),
        response=dict(
            status=getattr(response, 'status', None),
            headers=dict(getattr(response, 'headers', {})),
            text=lenient_json(getattr(response, 'text', None)),
        ),
        **more
    )


async def log_warning(start, request, response):
    logger.warning('%s %d', request.rel_url, response.status, extra={
        'fingerprint': [request.rel_url, str(response.status)],
        'data': await log_extra(start, request, response)
    })


def should_warn(r):
    return r.status > 310 and r.status not in {401, 404, 470}


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
            'data': await log_extra(start, request, exception_extra=lenient_json(exception_extra))
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
    conn = request['conn']
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


ALLOWED_HOSTS = 'localhost', '127.0.0.1'


def origin_check(request):
    # origin and host ports differ on localhost when testing
    return request.headers.get('Origin') == f'https://{request.host}/' or request.host.startswith(ALLOWED_HOSTS)


def referrer_check(request):
    r = request.headers.get('Referer')
    return r is None or r.startswith(request_root(request) + '/')


@middleware
async def csrf_middleware(request, handler):
    h = request.headers
    if request.method == METH_OPTIONS:
        if 'Access-Control-Request-Method' in h:
            if (h.get('Access-Control-Request-Method') == METH_POST and
                    h.get('Access-Control-Request-Headers').lower() == 'content-type' and
                    origin_check(request)):
                headers = {'Access-Control-Allow-Headers': 'Content-Type', **HEADER_CROSS_ORIGIN}
                return Response(text='ok', headers=headers)
            else:
                raise JsonErrors.HTTPForbidden(error='Access-Control checks failed', headers_=HEADER_CROSS_ORIGIN)
    elif request.method != METH_GET:
        if not (h.get('Content-Type') == JSON_CONTENT_TYPE and origin_check(request) and referrer_check(request)):
            logger.warning('CSRF failure, Content-Type: "%s", Origin: "%s", Referer: "%s"',
                           h.get('Content-Type'), h.get('Origin'), h.get('Referer'))
            raise JsonErrors.HTTPForbidden(error='CSRF failure', headers_=HEADER_CROSS_ORIGIN)

    return await handler(request)
