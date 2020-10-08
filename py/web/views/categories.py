from pathlib import Path

from buildpg import V
from buildpg.asyncpg import BuildPgConnection
from buildpg.clauses import Where
from pydantic import BaseModel, condecimal, constr, validator

from shared.images import delete_image, list_images, upload_background
from shared.utils import slugify
from web.auth import check_session, is_admin, is_admin_or_host
from web.bread import Bread
from web.utils import ImageModel, JsonErrors, json_response, parse_request, raw_json_response, request_image

category_public_sql = """
SELECT json_build_object('events', events)
FROM (
  SELECT coalesce(array_to_json(array_agg(json_strip_nulls(row_to_json(t)))), '[]') AS events FROM (
    SELECT e.id, e.name, c.slug as cat_slug, e.slug,
      coalesce(e.image, c.image) AS image,
      e.secondary_image,
      e.short_description,
      e.location_name,
      e.allow_tickets,
      e.allow_donations,
      e.start_ts AT TIME ZONE e.timezone AS start_ts,
      extract(epoch FROM e.duration)::int AS duration,
      coalesce(e.ticket_limit = e.tickets_taken, FALSE) AS sold_out
    FROM events AS e
    JOIN categories as c on e.category = c.id
    WHERE c.company=$1 AND c.slug=$2 AND status='published' AND public=TRUE AND e.start_ts > now()
    ORDER BY start_ts
  ) AS t
) AS events;
"""


async def category_public(request):
    company_id = request['company_id']
    category_slug = request.match_info['category']
    json_str = await request['conn'].fetchval(category_public_sql, company_id, category_slug)
    return raw_json_response(json_str)


cat_image_sql = """
SELECT co.slug, cat.slug
FROM categories AS cat
JOIN companies co ON cat.company = co.id
WHERE co.id=$1 AND cat.id=$2
"""


async def _get_cat_img_path(request):
    cat_id = int(request.match_info['cat_id'])
    conn: BuildPgConnection = request['conn']
    try:
        co_slug, cat_slug = await conn.fetchrow(cat_image_sql, request['company_id'], cat_id)
    except TypeError:
        raise JsonErrors.HTTPNotFound(message='category not found')
    else:
        return Path(co_slug) / cat_slug / 'option'


@is_admin
async def category_add_image(request):
    content = await request_image(request)
    upload_path = await _get_cat_img_path(request)
    await upload_background(content, upload_path, request.app['settings'])
    return json_response(status='success')


@is_admin_or_host
async def category_images(request):
    path = await _get_cat_img_path(request)
    images = await list_images(path, request.app['settings'])
    return json_response(images=sorted(images))


async def _check_image_exists(request, m: ImageModel):
    path = await _get_cat_img_path(request)
    images = await list_images(path, request.app['settings'])
    if m.image not in images:
        raise JsonErrors.HTTPBadRequest(message='image does not exist')


@is_admin
async def category_set_image(request):
    m = await parse_request(request, ImageModel)
    await _check_image_exists(request, m)

    cat_id = int(request.match_info['cat_id'])
    await request['conn'].execute('UPDATE categories SET image = $1 WHERE id = $2', m.image, cat_id)
    return json_response(status='success')


@is_admin
async def category_delete_image(request):
    m = await parse_request(request, ImageModel)
    await _check_image_exists(request, m)
    cat_id = int(request.match_info['cat_id'])

    dft_image = await request['conn'].fetchval('SELECT image FROM categories WHERE id=$1', cat_id)
    if dft_image == m.image:
        raise JsonErrors.HTTPBadRequest(message='default image may not be be deleted')

    await delete_image(m.image, request.app['settings'])
    return json_response(status='success')


class CategoryBread(Bread):
    class Model(BaseModel):
        name: str
        live: bool = True
        description: constr(max_length=140) = None
        sort_index: int = 1
        suggested_price: condecimal(ge=1, max_digits=6, decimal_places=2) = None
        event_content: str = None
        host_advice: str = None
        booking_trust_message: str = None
        cover_costs_message: str = None
        cover_costs_percentage: condecimal(ge=0, le=100, max_digits=5, decimal_places=2) = None
        terms_and_conditions_message: str = None
        allow_marketing_message: str = None
        post_booking_message: str = None
        ticket_extra_title: constr(max_length=140) = None
        ticket_extra_help_text: str = None

        @validator('live', pre=True)
        def none_bool(cls, v):
            return v or False

    browse_enabled = True
    retrieve_enabled = True
    add_enabled = True
    edit_enabled = True
    delete_enabled = True

    model = Model
    table = 'categories'
    browse_order_by_fields = ('sort_index',)

    browse_fields = (
        'id',
        'name',
        'live',
        'description',
    )
    retrieve_fields = browse_fields + (
        'sort_index',
        'suggested_price',
        'event_content',
        'host_advice',
        'booking_trust_message',
        'cover_costs_message',
        'cover_costs_percentage',
        'terms_and_conditions_message',
        'allow_marketing_message',
        'post_booking_message',
        'ticket_extra_title',
        'ticket_extra_help_text',
        'image',
    )

    async def check_permissions(self, method):
        await check_session(self.request, 'admin')

    def where(self):
        return Where(V('company') == self.request['company_id'])

    async def prepare_add_data(self, data):
        data.update(company=self.request['company_id'], slug=slugify(data['name']))
        return data
