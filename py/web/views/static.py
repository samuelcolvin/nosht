import logging
from pathlib import Path

from aiohttp.web_exceptions import HTTPForbidden, HTTPNotFound
from aiohttp.web_fileresponse import FileResponse

logger = logging.getLogger('nosht.web.static')


async def static_handler(request):
    # modified from aiohttp_web_urldispatcher.StaticResource_handle
    request_path = request.match_info['path'].lstrip('/')

    directory = request.app['static_dir']
    if request_path == '':
        return FileResponse(directory / 'index.html')

    try:
        filename = Path(request_path)
        if filename.anchor:
            # request_path is an absolute name like
            # /static/\\machine_name\c$ or /static/D:\path
            # where the static dir is totally different
            raise HTTPNotFound()
        filepath = directory.joinpath(filename).resolve()
        filepath.relative_to(directory)
    except HTTPForbidden:
        raise
    except Exception as exc:
        # perm error or other kind!
        logger.warning('error resolving path %r', request_path, exc_info=True)
        raise HTTPNotFound() from exc

    if filepath.is_file():
        return FileResponse(filepath)
    else:
        return FileResponse(directory / 'index.html')
