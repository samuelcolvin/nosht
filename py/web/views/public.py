import logging
from asyncpg import Connection

from web.utils import raw_json_response

logger = logging.getLogger('nosht.web')


categories_sql = """
SELECT json_build_object(
  'categories', categories,
  'highlight_events', highlight_events,
  'company', row_to_json(company)
)
FROM (
  SELECT array_to_json(array_agg(row_to_json(t))) AS categories FROM (
    SELECT id, name, slug, image_thumb 
    FROM categories 
    WHERE company=$1 AND live=TRUE
    ORDER BY sort_index
  ) AS t
) AS categories,
(
  SELECT array_to_json(array_agg(row_to_json(t))) AS highlight_events FROM (
    SELECT id, name, slug, image_thumb 
    FROM events 
    WHERE company=$1 AND highlight IS TRUE AND start_ts > now()
    ORDER BY start_ts
  ) AS t
) AS highlight_events,
(
  SELECT id, name, image
  FROM companies 
  WHERE id=$1
) AS company;
"""


async def index(request):
    conn: Connection = request['conn']
    company_id = request['company_id']
    json_str = await conn.fetchval(categories_sql, company_id)
    return raw_json_response(json_str)
