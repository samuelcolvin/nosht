from pathlib import Path

from aiohttp.web_exceptions import HTTPRequestEntityTooLarge
from buildpg.asyncpg import BuildPgConnection
from pydantic import BaseModel

from shared.images import check_size_save, delete_image, list_images, resize_upload
from web.utils import JsonErrors, json_response, parse_request

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
    try:
        co_slug, cat_slug = await conn.fetchrow(CAT_IMAGE_SQL, request['company_id'], cat_id)
    except TypeError:
        raise JsonErrors.HTTPNotFound(message='category not found')
    else:
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
        check_size_save(content)
    except ValueError as e:
        raise JsonErrors.HTTPBadRequest(message=str(e))

    upload_path = await _get_cat_img_path(request)
    await resize_upload(content, upload_path, request.app['settings'])

    return json_response(status='success')


@is_admin
async def category_images(request):
    path = await _get_cat_img_path(request)
    images = await list_images(path, request.app['settings'])
    return json_response(images=sorted(images))


CAT_SET_IMAGE_SQL = """
UPDATE categories
SET image = $1
WHERE id = $2
"""


class ImageActionModel(BaseModel):
    image: str


@is_admin
async def category_default_image(request):
    m = await parse_request(request, ImageActionModel)

    path = await _get_cat_img_path(request)
    images = await list_images(path, request.app['settings'])
    if m.image not in images:
        raise JsonErrors.HTTPBadRequest(message='image does not exist')
    cat_id = int(request.match_info['cat_id'])
    await request['conn'].execute(CAT_SET_IMAGE_SQL, m.image, cat_id)
    return json_response(status='success')


@is_admin
async def category_delete_image(request):
    m = await parse_request(request, ImageActionModel)

    # _get_cat_img_path is required to check the category is on the right company
    await _get_cat_img_path(request)

    await delete_image(m.image, request.app['settings'])
    return json_response(status='success')
