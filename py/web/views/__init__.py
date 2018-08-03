from web.utils import raw_json_response

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
    SELECT e.id, e.name, c.slug as cat_slug, e.slug, coalesce(e.image, c.image) AS image, e.short_description,
      e.start_ts, e.location_name, EXTRACT(epoch FROM e.duration)::int AS duration
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
        SELECT id, first_name, last_name, email, role, status
        FROM users
        WHERE id=$2
      ) AS t
    )
    END
) AS user_data;
"""


async def index(request):
    company_id = request['company_id']
    user_id = request['session'].get('user_id', None)
    # TODO could cache this in redis as it's called A LOT
    json_str = await request['conn'].fetchval(company_sql, company_id, user_id)
    return raw_json_response(json_str)
