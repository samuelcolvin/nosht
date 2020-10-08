import base64
import json
import logging
from datetime import date
from secrets import compare_digest

from aiohttp.web_exceptions import HTTPUnauthorized
from aiohttp.web_response import Response, StreamResponse

from web.utils import raw_json_response

logger = logging.getLogger('nosht.views')

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
    SELECT e.id, e.name, c.slug as cat_slug, e.slug,
      coalesce(e.image, c.image) AS image,
      e.secondary_image,
      e.short_description,
      e.allow_tickets,
      e.allow_donations,
      e.start_ts AT TIME ZONE e.timezone AS start_ts, e.location_name,
      extract(epoch FROM e.duration)::int AS duration,
      coalesce(e.ticket_limit = e.tickets_taken, FALSE) AS sold_out
    FROM events AS e
    JOIN categories as c on e.category = c.id
    WHERE c.company=$1 AND status='published' AND public=TRUE AND e.highlight IS TRUE AND e.start_ts > now()
    ORDER BY start_ts
  ) AS t
) AS highlight_events,
(
  SELECT id, name, image, currency, stripe_public_key, footer_links
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


sitemap_events_sql = """
SELECT cat.slug || '/', cat.slug || '/' || e.slug || '/', MAX(a.ts), e.highlight
FROM actions as a
JOIN events as e ON a.event = e.id
JOIN categories AS cat ON e.category = cat.id
WHERE
  (a.type = 'create-event' OR a.type = 'edit-event') AND
  cat.live = TRUE AND e.status = 'published' AND e.public = TRUE AND e.start_ts > now()
GROUP BY cat.slug, e.slug, e.highlight
"""


async def sitemap(request):
    response = StreamResponse()
    response.content_type = 'application/xml'
    await response.prepare(request)

    await response.write(
        b'<?xml version="1.0" encoding="UTF-8"?>\n' b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    )
    try:
        company_domain = await request['conn'].fetchval(
            'SELECT domain FROM companies WHERE id=$1', request['company_id']
        )

        async def write_url(uri_, latest_update_, priority):
            await response.write(
                (
                    f'<url>'
                    f'<loc>https://{company_domain}/{uri_}</loc>'
                    f'<lastmod>{latest_update_:%Y-%m-%d}</lastmod>'
                    f'<changefreq>daily</changefreq>'
                    f'<priority>{priority:0.1f}</priority>'
                    f'</url>\n'
                ).encode()
            )

        cats = {}
        async with request['conn'].transaction():
            async for (cat_uri, uri, latest_update, highlight) in request['conn'].cursor(sitemap_events_sql):
                cat_latest_update = cats.get(cat_uri)
                if cat_latest_update is None or latest_update > cat_latest_update:
                    cats[cat_uri] = latest_update

                await write_url(uri, latest_update, 0.7 if highlight else 0.5)

        for cat_uri, latest_update in cats.items():
            await write_url(cat_uri, latest_update, 0.9)

        if cats:
            await write_url('', max(cats.values()), 1)
        else:
            await write_url('', date.today(), 1)
    except Exception:  # pragma no cover
        logger.exception('error generating sitemap')

    await response.write(b'</urlset>\n')
    return response


async def ses_webhook(request):
    pw = request.app['settings'].aws_ses_webhook_auth
    expected_auth_header = f'Basic {base64.b64encode(pw).decode()}'
    actual_auth_header = request.headers.get('Authorization', '')
    if not compare_digest(expected_auth_header, actual_auth_header):
        raise HTTPUnauthorized(text='Invalid basic auth', headers={'WWW-Authenticate': 'Basic'})

    # content type is plain text for SNS, so we have to decode json manually
    data = json.loads(await request.text())
    sns_type = data['Type']
    if sns_type == 'SubscriptionConfirmation':
        logger.info('confirming aws Subscription')
        async with request.app['stripe_client'].head(data['SubscribeURL']) as r:
            assert r.status == 200, r.status
    else:
        assert sns_type == 'Notification', sns_type
        await request.app['email_actor'].record_email_event(data.get('Message'))
    return Response(status=204)
