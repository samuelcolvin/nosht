import logging
import os
import re
from copy import deepcopy
from pathlib import Path

from aiohttp.web import Response
from aiohttp.web_exceptions import HTTPMovedPermanently, HTTPNotFound
from aiohttp.web_fileresponse import FileResponse

from shared.settings import Settings
from web.utils import request_root

logger = logging.getLogger('nosht.web.static')

CSP = {
    'default-src': ["'self'"],
    'script-src': [
        "'self'",
        'www.google-analytics.com',
        'maps.googleapis.com',
        '*.google.com',
        '*.gstatic.com',
        'connect.facebook.net',
        'js.stripe.com',
        'browser-update.org',
        "'sha256-0ni4JEtxxn/uHl32Dvj0iyke8H1kqdpZkoPzdam0nl8='",
    ],
    'font-src': ["'self'", 'data:', 'fonts.gstatic.com'],
    'style-src': ["'self'", "'unsafe-inline'", '*.googleapis.com'],
    'frame-src': [
        "'self'",
        '*.google.com',
        'staticxx.facebook.com',
        'js.stripe.com',
        'youtube.com',
        '*.youtube.com',
        '*.facebook.com',
    ],
    'img-src': [
        "'self'",
        'blob:',
        'data:',
        'www.google-analytics.com',
        '*.googleapis.com',
        '*.gstatic.com',
        '*.google.com',
        '*.google.co.uk',
        '*.google.de',
        '*.google.pt',
        '*.doubleclick.net',
        'browser-update.org',
    ],
    'media-src': ["'self'"],
    'connect-src': ["'self'", '*.google-analytics.com', '*.doubleclick.net', 'https://sentry.io', '*.facebook.com'],
}


def get_csp_headers(settings: Settings):
    csp = deepcopy(CSP)
    csp['img-src'].append(settings.csp_image_source)

    raven_dsn = os.getenv('RAVEN_DSN_CSP', None) or os.getenv('RAVEN_DSN', None)
    if raven_dsn:
        m = re.search(r'^https://(.+)@sentry\.io/(.+)', raven_dsn)
        if m:
            key, app = m.groups()
            csp['report-uri'] = [f'https://sentry.io/api/{app}/security/?sentry_key={key}']
        else:
            logger.warning('app and key not found in raven dsn %r', raven_dsn)
    return {'Content-Security-Policy': ' '.join(f'{k} {" ".join(v)};' for k, v in csp.items())}


async def static_handler(request):
    # modified from aiohttp_web_urldispatcher.StaticResource_handle
    request_path = request.match_info['path'].lstrip('/')

    directory = request.app['static_dir']
    csp_headers = request.app['csp_headers']
    if request_path == '':
        return FileResponse(directory / 'index.html', headers=csp_headers)
    elif request_path == 'sitemap.xml':
        raise HTTPMovedPermanently(location=f'https://{request.host}/api/sitemap.xml')

    try:
        filename = Path(request_path)
        if filename.anchor:  # pragma: no cover
            # windows only I think, but keep it just in case
            # request_path is an absolute name like
            # /static/\\machine_name\c$ or /static/D:\path
            # where the static dir is totally different
            raise HTTPNotFound()
        filepath = directory.joinpath(filename).resolve()
        filepath.relative_to(directory)
    except Exception as exc:
        # perm error or other kind!
        logger.warning('error resolving path %r', request_path, exc_info=True)
        raise HTTPNotFound() from exc

    is_file = filepath.is_file()
    if request_path.startswith('iframes/') and request_path.endswith('.html') and is_file:
        new_root = request_root(request)
        content = filepath.read_text().replace('http://localhost:3000', new_root)
        # no csp header here, it's defined in the page as a http-equiv header
        return Response(text=content, content_type='text/html')
    elif is_file:
        return FileResponse(filepath, headers=csp_headers)
    elif request_path.startswith('pvt/'):
        return FileResponse(directory / 'index.html', headers={**csp_headers, **{'X-Robots-Tag': 'noindex'}})
    else:
        return FileResponse(directory / 'index.html', headers=csp_headers)
