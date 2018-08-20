import logging
from pathlib import Path

from aiohttp.web import Response
from aiohttp.web_exceptions import HTTPMovedPermanently, HTTPNotFound
from aiohttp.web_fileresponse import FileResponse

from web.utils import request_root

logger = logging.getLogger('nosht.web.static')


async def static_handler(request):
    # modified from aiohttp_web_urldispatcher.StaticResource_handle
    request_path = request.match_info['path'].lstrip('/')

    directory = request.app['static_dir']
    if request_path == '':
        return FileResponse(directory / 'index.html')
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
        return Response(text=content, content_type='text/html')
    elif is_file:
        return FileResponse(filepath)
    elif request_path.startswith('pvt/'):
        return FileResponse(directory / 'index.html', headers={'X-Robots-Tag': 'noindex'})
    else:
        return FileResponse(directory / 'index.html')
