import logging
from csv import DictWriter
from datetime import datetime

from aiohttp.web_response import StreamResponse

from web.auth import is_admin

logger = logging.getLogger('nosht.export')

EXPORTS = {
    'events': """
SELECT
  e.id, e.name, e.slug, e.status,
  iso_ts(e.start_ts, e.timezone) AS start_time, e.timezone,
  to_char(extract(epoch from e.duration)/3600, 'FM9999990.00') AS duration_hours,
  e.youtube_video_id, e.short_description, e.long_description, boolstr(e.public) AS is_public, e.location_name,
  e.description_image, e.description_intro,
  to_char(e.location_lat, 'FM990.0000000') AS location_lat,
  to_char(e.location_lng, 'FM990.0000000') AS location_lng,
  e.ticket_limit, e.image,
  string_agg(to_char(coalesce(tt.price, 0), 'FM9999990.00'), ',') AS ticket_price,
  count(t.id) AS tickets_booked, to_char(sum(t.price), 'FM9999990.00') AS total_raised,
  cat.id AS category_id, cat.slug AS category_slug
FROM events AS e
JOIN categories AS cat ON e.category = cat.id
JOIN users AS u ON e.host = u.id
JOIN ticket_types AS tt ON e.id = tt.event
LEFT JOIN tickets AS t ON (e.id = t.event AND t.status='booked')
WHERE cat.company=$1 AND tt.mode = 'ticket'
GROUP BY e.id, cat.id
ORDER BY e.id, cat.id
""",
    'categories': """
SELECT
  id, name, slug, boolstr(live) AS live, description, sort_index, event_content, host_advice,
  ticket_extra_title, ticket_extra_help_text,
  suggested_price, image
FROM categories AS c
WHERE company=$1
ORDER BY id
""",
    'users': """
SELECT
  u.id, u.role, u.status, u.first_name, u.last_name, u.email, u.phone_number, u.stripe_customer_id,
  boolstr(u.receive_emails) AS receive_emails, boolstr(u.allow_marketing) AS allow_marketing,
  iso_ts(u.created_ts, 'UTC') AS created_ts,
  iso_ts(u.active_ts, 'UTC') AS active_ts,
  count(t.id) AS tickets
FROM users AS u
LEFT JOIN tickets AS t ON u.id = t.user_id
WHERE u.company=$1
GROUP BY u.id
ORDER BY u.id
""",
    'tickets': """
SELECT
  t.id, t.first_name AS ticket_first_name, t.last_name AS ticket_last_name, t.status, a.type AS booking_action,
  to_char(t.price, 'FM9999990.00') AS price, to_char(t.extra_donated, 'FM9999990.00') AS extra_donated,
  iso_ts(t.created_ts, 'UTC') AS created_ts, t.extra_info,
  tt.id AS ticket_type_id, tt.name AS ticket_type_name,
  e.id AS event_id, e.slug AS event_slug,
  t.user_id AS guest_user_id, u.first_name AS guest_first_name, u.last_name AS guest_last_name,
  ub.id AS buyer_user_id, ub.first_name AS buyer_first_name, ub.last_name AS buyer_last_name
FROM tickets AS t
JOIN events AS e ON t.event = e.id
LEFT JOIN users AS u ON t.user_id = u.id
JOIN ticket_types AS tt on t.ticket_type = tt.id
JOIN actions a ON t.booked_action = a.id
JOIN users ub ON a.user_id = ub.id
WHERE a.company=$1 AND t.status!='reserved'
ORDER BY t.id
""",
    'donations': """
SELECT
  d.id, to_char(d.amount, 'FM9999990.00') AS amount,
  d.first_name, d.last_name, d.address, d.city, d.postcode, boolstr(d.gift_aid) AS gift_aid,
  u.email AS user_email, u.first_name AS user_first_name, u.last_name AS user_last_name,
  iso_ts(a.ts, 'UTC') AS timestamp, a.event,
  opts.id AS donation_option_id, opts.name AS donation_option_name,
  cat.id AS category_id, cat.name AS category_name
FROM donations AS d
JOIN actions AS a ON d.action = a.id
JOIN users AS u ON a.user_id = u.id
JOIN donation_options AS opts ON d.donation_option = opts.id
JOIN categories AS cat ON opts.category = cat.id
JOIN companies AS co ON cat.company = co.id
WHERE cat.company=$1
ORDER BY d.id
    """,
}


@is_admin
async def export(request):
    export_type = request.match_info['type']
    export_sql = EXPORTS[export_type]
    return await export_plumbing(
        request,
        export_sql,
        request['company_id'],
        filename=f'nosht_{export_type}_{datetime.utcnow().isoformat()}',
        none_message=f'no {export_type} found',
    )


class ResponsePseudoFile:
    def __init__(self, response):
        self.r = response
        self.buffer = ''

    def write(self, v):
        self.buffer += v

    async def write_response(self):
        # WARNING: this is not safe to all asynchronously, it needs to be fully awaited before write can be called again
        await self.r.write(self.buffer.encode())
        self.buffer = ''


async def export_plumbing(request, sql, *sql_args, filename, none_message, modify_records=None):
    response = StreamResponse(headers={'Content-Disposition': f'attachment;filename={filename}.csv'})
    response.content_type = 'text/csv'
    await response.prepare(request)
    try:
        response_file = ResponsePseudoFile(response)

        writer = None
        async with request['conn'].transaction():
            async for record in request['conn'].cursor(sql, *sql_args):
                if modify_records:
                    data = modify_records(record)
                else:
                    data = record
                if writer is None:
                    writer = DictWriter(response_file, fieldnames=list(data.keys()))
                    writer.writeheader()
                writer.writerow({k: '' if v is None else str(v) for k, v in data.items()})
                await response_file.write_response()

        if writer is None:
            writer = DictWriter(response_file, fieldnames=['message'])
            writer.writeheader()
            writer.writerow({'message': none_message})
            await response_file.write_response()
    except Exception:  # pragma no cover
        logger.exception('error generating export, filename: %s', filename)
    return response
