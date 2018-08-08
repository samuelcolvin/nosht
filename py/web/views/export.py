from csv import DictWriter
from datetime import datetime

from aiohttp.web_response import StreamResponse

from web.auth import is_admin

EXPORTS = {
    'events': """
SELECT
  e.id, e.name, e.slug, e.status,
  to_char(e.start_ts, 'YYYY-MM-DD"T"HH24:MI:SS') AS start_time,
  to_char(extract(epoch from e.duration)/3600, 'FM9999990.00') AS duration_hours,
  e.short_description, e.long_description, boolstr(e.public) AS is_public, e.location_name,
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
WHERE cat.company=$1
GROUP BY e.id, cat.id
""",
    'categories': """
SELECT
  id, name, slug, boolstr(live) AS live, description, sort_index, event_content, host_advice,
  ticket_extra_title, ticket_extra_help_text,
  suggested_price, image
FROM categories AS c
WHERE company=$1
""",
    'users': """
SELECT
  u.id, u.role, u.status, u.first_name, u.last_name, u.email, u.phone_number, u.stripe_customer_id,
  boolstr(u.receive_emails) AS receive_emails,
  to_char(u.created_ts, 'YYYY-MM-DD"T"HH24:MI:SS') AS created_ts,
  to_char(u.active_ts, 'YYYY-MM-DD"T"HH24:MI:SS') AS active_ts,
  count(t.id) AS tickets
FROM users AS u
LEFT JOIN tickets AS t ON u.id = t.user_id
WHERE u.company=$1
GROUP BY u.id
""",
    'tickets': """
SELECT
  t.id, t.first_name AS ticket_first_name, t.last_name AS ticket_last_name, t.status,
  to_char(t.price, 'FM9999990.00') AS price,
  to_char(t.created_ts, 'YYYY-MM-DD"T"HH24:MI:SS') AS created_ts,
  t.extra->>'extra_info' AS extra_info,
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
"""
}


class ResponsePseudoFile:
    def __init__(self, response):
        self.r = response
        self.buffer = ''

    def write(self, v):
        self.buffer += v

    async def write_response(self):
        await self.r.write(self.buffer.encode())
        self.buffer = ''


@is_admin
async def export(request):
    export_type = request.match_info['type']
    export_sql = EXPORTS[export_type]
    conn = request['conn']
    async with conn.transaction():
        response = StreamResponse(headers={
            'Content-Disposition': f'attachment;filename=nosht_{export_type}_{datetime.now().isoformat()}.csv'
        })
        response.content_type = 'text/csv'
        await response.prepare(request)

        response_file = ResponsePseudoFile(response)
        r = await conn.fetchrow(export_sql + ' LIMIT 1', request['company_id'])
        if not r:
            writer = DictWriter(response_file, fieldnames=['message'])
            writer.writeheader()
            writer.writerow({'message': f'no {export_type} found'})
            await response_file.write_response()
            return response

        writer = DictWriter(response_file, fieldnames=list(r.keys()))
        writer.writeheader()

        async for record in conn.cursor(export_sql, request['company_id']):
            writer.writerow({k: str('' if v is None else v) for k, v in record.items()})
            await response_file.write_response()
    return response