from pathlib import Path

from aiohttp.web_exceptions import HTTPRequestEntityTooLarge
from buildpg.asyncpg import BuildPgConnection

from shared.images import check_size_save, list_images, resize_upload
from web.utils import JsonErrors, json_response

from .auth import is_admin

CAT_IMAGE_SQL = """
SELECT co.slug, cat.slug
FROM categories AS cat
JOIN companies co on cat.company = co.id
WHERE co.id=$1 AND cat.id=$2
"""


async def _get_cat_img_path(request):
    cat_id = int(request.match_info['cat_id'])
    conn: BuildPgConnection = request['conn']
    co_slug, cat_slug = await conn.fetchrow(CAT_IMAGE_SQL, request['company_id'], cat_id)
    return Path(co_slug) / cat_slug / 'option'


@is_admin
async def category_add_image(request):
    try:
        p = await request.post()
    except ValueError:
        raise HTTPRequestEntityTooLarge
    image = p['image']
    content = image.file.read()
    try:
        file_path = check_size_save(content)
    except ValueError as e:
        raise JsonErrors.HTTPBadRequest(message=str(e))

    upload_path = await _get_cat_img_path(request)

    # TODO move to worker
    await resize_upload(Path(file_path), upload_path, request.app['settings'])
    return json_response(status='success')


@is_admin
async def category_images(request):
    path = await _get_cat_img_path(request)
    images = await list_images(path, request.app['settings'])
    return json_response(images=images)
