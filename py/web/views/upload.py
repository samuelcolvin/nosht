from pathlib import Path

from buildpg.asyncpg import BuildPgConnection

from shared.images import check_size_save, resize_upload
from web.utils import JsonErrors, json_response

from .auth import is_admin


CAT_IMAGE_SQL = """
SELECT co.slug, cat.slug
FROM categories AS cat
JOIN companies co on cat.company = co.id
WHERE co.id=$1 AND cat.id=$2
"""
CAT_IMAGE_APPEND_SQL = """
UPDATE categories
SET suggested_images = suggested_images || $1
WHERE id = $2
"""


@is_admin
async def category_image(request):
    p = await request.post()
    image = p['image']
    content = image.file.read()
    try:
        file_path = check_size_save(content)
    except ValueError as e:
        raise JsonErrors.HTTPBadRequest(message=str(e))

    cat_id = int(request.match_info['cat_id'])
    conn: BuildPgConnection = request['conn']
    co_slug, cat_slug = await conn.fetchrow(CAT_IMAGE_SQL, request['company_id'], cat_id)
    upload_path = Path(co_slug) / cat_slug / 'option'

    # TODO move to worker
    image_url = await resize_upload(Path(file_path), upload_path, request.app['settings'])
    await conn.execute(CAT_IMAGE_APPEND_SQL, [image_url], cat_id)
    return json_response(status='success')
