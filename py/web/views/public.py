from buildpg.asyncpg import BuildPgConnection

from web.utils import JsonErrors, raw_json_response

company_sql = """
SELECT json_build_object(
  'categories', categories,
  'highlight_events', highlight_events,
  'company', row_to_json(company),
  'user', user_data
)
FROM (
  SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') AS categories FROM (
    SELECT id, name, slug, image, description
    FROM categories
    WHERE company=$1 AND live=TRUE
    ORDER BY sort_index
  ) AS t
) AS categories,
(
  SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') AS highlight_events FROM (
    SELECT e.id, e.name, c.slug as cat_slug, e.slug, e.image, e.short_description, e.location, e.start_ts,
      EXTRACT(epoch FROM e.duration)::int AS duration
    FROM events AS e
    JOIN categories as c on e.category = c.id
    WHERE c.company=$1 AND status='published' AND public=TRUE AND e.highlight IS TRUE AND e.start_ts > now()
    ORDER BY start_ts
  ) AS t
) AS highlight_events,
(
  SELECT id, name, image
  FROM companies
  WHERE id=$1
) AS company,
(
  SELECT
    CASE WHEN $2::int IS NULL THEN (
      null
    )
    ELSE (
      SELECT row_to_json(t) AS user_data FROM (
        SELECT id, COALESCE(first_name || ' ' || last_name, email) AS name, role, status
        FROM users
        WHERE id=$2
      ) AS t
    )
    END
) AS user_data;
"""


async def index(request):
    conn: BuildPgConnection = request['conn']
    company_id = request['company_id']
    user_id = request['session'].get('user_id', None)
    json_str = await conn.fetchval(company_sql, company_id, user_id)
    return raw_json_response(json_str)


category_sql = """
SELECT json_build_object('events', events)
FROM (
  SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') AS events FROM (
    SELECT e.id, e.name, c.slug as cat_slug, e.slug, e.image, e.short_description, e.location, e.start_ts,
      EXTRACT(epoch FROM e.duration)::int AS duration
    FROM events AS e
    JOIN categories as c on e.category = c.id
    WHERE c.company=$1 AND c.slug=$2 AND status='published' AND public=TRUE AND e.start_ts > now()
    ORDER BY start_ts
  ) AS t
) AS events;
"""


async def category(request):
    conn: BuildPgConnection = request['conn']
    company_id = request['company_id']
    category_slug = request.match_info['category']
    json_str = await conn.fetchval(category_sql, company_id, category_slug)
    if not json_str:
        raise JsonErrors.HTTPNotFound(message='category not found')
    return raw_json_response(json_str)


event_sql = """
SELECT json_build_object('event', row_to_json(event))
FROM (
  SELECT e.id,
         e.name,
         e.image,
         e.short_description,
         e.long_description,
         c.event_content AS category_content,
         json_build_object(
           'name', e.location,
           'lat', e.location_lat,
           'lng', e.location_lng
         ) AS location,
         e.price,
         e.start_ts,
         EXTRACT(epoch FROM e.duration)::int AS duration,
         e.ticket_limit,
         e.tickets_sold,
         h.id AS host_id,
         h.first_name || ' ' || h.last_name AS host_name
  FROM events AS e
  JOIN categories AS c ON e.category = c.id
  JOIN users AS h ON e.host = h.id
  WHERE c.company=$1 AND c.slug=$2 AND e.slug=$3 AND e.status='published'
) AS event;
"""


async def event(request):
    conn: BuildPgConnection = request['conn']
    company_id = request['company_id']
    category_slug = request.match_info['category']
    event_slug = request.match_info['event']
    json_str = await conn.fetchval(event_sql, company_id, category_slug, event_slug)
    if not json_str:
        raise JsonErrors.HTTPNotFound(message='event not found')
    return raw_json_response(json_str)
