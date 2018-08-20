import logging
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from textwrap import shorten
from typing import List, Optional

from asyncpg import CheckViolationError
from buildpg import Func, MultipleValues, SetValues, V, Values, funcs
from buildpg.asyncpg import BuildPgConnection
from buildpg.clauses import Join, Where
from pydantic import BaseModel, condecimal, conint, constr, validator

from shared.images import delete_image, resize_upload
from shared.utils import pseudo_random_str, slugify, ticket_id_signed
from web.actions import ActionTypes, record_action, record_action_id
from web.auth import GrecaptchaModel, check_grecaptcha, check_session, is_admin, is_admin_or_host
from web.bread import Bread, Method, UpdateView
from web.utils import (ImageModel, JsonErrors, clean_markdown, json_response, parse_request, raw_json_response,
                       request_image)
from web.views.export import export_plumbing

logger = logging.getLogger('nosht.events')

event_sql = """
SELECT json_build_object(
  'event', row_to_json(event),
  'ticket_types', ticket_types
)
FROM (
  SELECT e.id,
         e.name,
         coalesce(e.image, c.image) AS image,
         e.short_description,
         e.long_description,
         c.event_content AS category_content,
         json_build_object(
           'name', e.location_name,
           'lat', e.location_lat,
           'lng', e.location_lng
         ) AS location,
         e.start_ts,
         EXTRACT(epoch FROM e.duration)::int AS duration,
         CASE
           WHEN e.ticket_limit IS NULL THEN NULL
           WHEN e.ticket_limit - e.tickets_taken >= 10 THEN NULL
           ELSE e.ticket_limit - e.tickets_taken
         END AS tickets_available,
         h.id AS host_id,
         h.first_name || ' ' || h.last_name AS host_name,
         co.stripe_public_key AS stripe_key,
         c.ticket_extra_title,
         c.ticket_extra_help_text,
         c.booking_trust_message,
         c.cover_costs_message,
         c.cover_costs_percentage,
         c.terms_and_conditions_message,
         c.allow_marketing_message
  FROM events AS e
  JOIN categories AS c ON e.category = c.id
  JOIN companies AS co ON c.company = co.id
  JOIN users AS h ON e.host = h.id
  WHERE c.company=$1 AND c.slug=$2 AND e.slug=$3 AND e.status='published'
) AS event,
(
  SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') AS ticket_types FROM (
    SELECT tt.name, tt.price
    FROM ticket_types AS tt
    JOIN events AS e ON tt.event = e.id
    WHERE e.slug=$3 AND tt.active=TRUE
  ) AS t
) AS ticket_types;
"""


async def event_public(request):
    conn: BuildPgConnection = request['conn']
    company_id = request['company_id']
    category_slug = request.match_info['category']
    event_slug = request.match_info['event']
    json_str = await conn.fetchval(event_sql, company_id, category_slug, event_slug)
    if not json_str:
        raise JsonErrors.HTTPNotFound(message='event not found')
    return raw_json_response(json_str)


category_sql = """
SELECT json_build_object('categories', categories)
FROM (
  SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') AS categories FROM (
    SELECT id, name, host_advice, event_type, suggested_price
    FROM categories
    WHERE company=$1 AND live=TRUE
    ORDER BY sort_index
  ) AS t
) AS categories
"""


@is_admin_or_host
async def event_categories(request):
    conn: BuildPgConnection = request['conn']
    json_str = await conn.fetchval(category_sql, request['company_id'])
    return raw_json_response(json_str)


class EventBread(Bread):
    class Model(BaseModel):
        name: constr(max_length=63)
        category: int
        public: bool = True

        class DateModel(BaseModel):
            dt: datetime
            dur: Optional[int]

        date: DateModel

        class LocationModel(BaseModel):
            lat: float
            lng: float
            name: constr(max_length=63)

        location: LocationModel = None
        ticket_limit: int = None
        price: condecimal(ge=1, max_digits=6, decimal_places=2) = None
        long_description: str
        short_description: str = None

    browse_enabled = True
    retrieve_enabled = True
    add_enabled = True
    edit_enabled = True

    model = Model
    table = 'events'
    table_as = 'e'

    browse_fields = (
        'e.id',
        'e.name',
        V('cat.name').as_('category'),
        'e.status',
        'e.highlight',
        'e.start_ts',
        funcs.extract(V('epoch').from_(V('e.duration'))).cast('int').as_('duration'),
    )
    retrieve_fields = browse_fields + (
        'e.slug',
        V('cat.slug').as_('cat_slug'),
        V('cat.id').as_('cat_id'),
        'e.public',
        'e.image',
        'e.ticket_limit',
        'e.location_name',
        'e.location_lat',
        'e.location_lng',
        'e.short_description',
        'e.long_description',
        'e.host',
        Func('full_name', V('uh.first_name'), V('uh.last_name'), V('uh.email')).as_('host_name'),
    )

    async def check_permissions(self, method):
        await check_session(self.request, 'admin', 'host')

    def join(self):
        joins = (
            Join(V('categories').as_('cat').on(V('cat.id') == V('e.category'))) +
            Join(V('companies').as_('co').on(V('co.id') == V('cat.company')))
        )
        if self.method == Method.retrieve:
            joins += Join(V('users').as_('uh').on(V('uh.id') == V('e.host')))
        return joins

    def where(self):
        logic = V('cat.company') == self.request['company_id']
        session = self.request['session']
        if session['role'] != 'admin':
            logic &= V('e.host') == session['user_id']
        return Where(logic)

    def prepare(self, data):
        date = data.pop('date', None)
        if date:
            dt: datetime = date['dt']
            duration: Optional[int] = date['dur']
            data.update(
                start_ts=datetime(dt.year, dt.month, dt.day) if duration is None else dt.replace(tzinfo=None),
                duration=duration and timedelta(seconds=duration),
            )

        loc = data.pop('location', None)
        if loc:
            data.update(
                location_name=loc['name'],
                location_lat=loc['lat'],
                location_lng=loc['lng'],
            )

        return data

    async def prepare_add_data(self, data):
        data = self.prepare(data)

        session = self.request['session']
        data.update(
            slug=slugify(data['name']),
            short_description=shorten(clean_markdown(data['long_description']), width=140, placeholder='…'),
            host=session['user_id'],
        )
        q = 'SELECT status FROM users WHERE id=$1'
        if session['role'] == 'admin' or 'active' == await self.conn.fetchval(q, session['user_id']):
            data['status'] = 'published'
        return data

    async def prepare_edit_data(self, data):
        return self.prepare(data)

    add_sql = """
    INSERT INTO :table (:values__names) VALUES :values
    ON CONFLICT (category, slug) DO NOTHING
    RETURNING :pk_field
    """

    async def add_execute(self, *, slug, **data):
        price = data.pop('price', None)
        async with self.conn.transaction():
            pk = await super().add_execute(slug=slug, **data)
            while pk is None:
                # event with this slug already exists
                pk = await super().add_execute(slug=slug + '-' + pseudo_random_str(4), **data)
            await self.conn.execute_b(
                'INSERT INTO ticket_types (:values__names) VALUES :values',
                values=Values(event=pk, name='Standard', price=price)
            )
            action_id = await record_action_id(self.request, self.request['session']['user_id'],
                                               ActionTypes.create_event, event_id=pk)
            await self.app['email_actor'].send_event_created(action_id)
        return pk

    async def edit_execute(self, pk, **data):
        try:
            await super().edit_execute(pk, **data)
        except CheckViolationError as exc:
            if exc.constraint_name != 'ticket_limit_check':  # pragma: no branch
                raise  # pragma: no cover
            raise JsonErrors.HTTPBadRequest(
                message='Invalid Ticket Limit',
                details=[
                    {
                        'loc': ['ticket_limit'],
                        'msg': f'May not be less than the number of tickets already booked.',
                        'type': 'value_error.too_low',
                    }
                ]
            )
        else:
            await record_action(self.request, self.request['session']['user_id'], ActionTypes.edit_event,
                                event_id=pk, subtype='edit-event')


async def _check_event_host(request):
    event_id = int(request.match_info['id'])
    host_id = await request['conn'].fetchval(
        """
        SELECT host
        FROM events AS e
        JOIN categories AS cat ON e.category = cat.id
        WHERE e.id=$1 AND cat.company=$2
        """, event_id, request['company_id'])
    if not host_id:
        raise JsonErrors.HTTPNotFound(message='event not found')
    if request['session']['role'] != 'admin' and host_id != request['session']['user_id']:
        raise JsonErrors.HTTPForbidden(message='user is not the host of this event')
    return event_id


event_tickets_sql = """
SELECT t.id, iso_ts(a.ts) AS booked_at, t.price::float AS price, t.extra_donated::float AS extra_donated, t.extra_info,
  t.user_id AS guest_user_id, full_name(t.first_name, t.last_name) AS guest_name, ug.email AS guest_email,
  a.user_id as buyer_user_id,
  coalesce(full_name(tb.first_name, tb.last_name), full_name(ub.first_name, ub.last_name)) AS buyer_name,
  ub.email AS buyer_email,
  tt.name AS ticket_type_name, tt.id AS ticket_type_id
FROM tickets AS t
LEFT JOIN users AS ug ON t.user_id = ug.id
JOIN actions AS a ON t.booked_action = a.id
LEFT JOIN tickets AS tb ON (a.user_id = tb.user_id AND a.id = tb.booked_action)
JOIN users AS ub ON a.user_id = ub.id
JOIN ticket_types AS tt ON t.ticket_type = tt.id
WHERE t.event=$1 AND t.status='booked'
ORDER BY a.ts
"""


@is_admin_or_host
async def event_tickets(request):
    event_id = await _check_event_host(request)
    not_admin = request['session']['role'] != 'admin'
    tickets = []
    settings = request.app['settings']
    for t in await request['conn'].fetch(event_tickets_sql, event_id):
        ticket = {
            'ticket_id': ticket_id_signed(t['id'], settings),
            **t,
        }
        if not_admin:
            ticket.pop('guest_email')
            ticket.pop('buyer_email')
        tickets.append(ticket)
    return json_response(tickets=tickets)


@is_admin_or_host
async def event_tickets_export(request):
    event_id = await _check_event_host(request)
    not_admin = request['session']['role'] != 'admin'
    event_slug = await request['conn'].fetchval('SELECT slug FROM events WHERE id=$1', event_id)
    settings = request.app['settings']

    def modify(record):
        data = {
            'ticket_id': ticket_id_signed(record['id'], settings),
            **record,
        }
        data.pop('id')
        data.pop('ticket_type_id')
        if not_admin:
            data.pop('guest_email')
            data.pop('guest_user_id')
            data.pop('buyer_email')
            data.pop('buyer_user_id')
        return data

    return await export_plumbing(
        request,
        event_tickets_sql,
        event_id,
        filename=f'{event_slug}-tickets',
        none_message='no tickets booked',
        modify_records=modify,
    )


event_ticket_types_sql = """
SELECT json_build_object('ticket_types', tickets)
FROM (
  SELECT array_to_json(array_agg(row_to_json(t))) AS tickets FROM (
    SELECT tt.id, tt.name, tt.price, tt.slots_used, tt.active, COUNT(t.id) > 0 AS has_tickets
    FROM ticket_types AS tt
    LEFT JOIN tickets AS t ON tt.id = t.ticket_type
    WHERE tt.event=$1
    GROUP BY tt.id
    ORDER BY tt.id
  ) AS t
) AS tickets
"""
# TODO could add user here
event_updates_sent_sql = """
SELECT json_build_object('event_updates', event_updates)
FROM (
  SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') AS event_updates FROM (
    SELECT ts, extra->>'subject' AS subject, extra->>'message' AS message
    FROM actions
    WHERE type='event-update' AND event=$1
  ) AS t
) AS event_updates
"""


@is_admin_or_host
async def event_ticket_types(request):
    event_id = await _check_event_host(request)
    json_str = await request['conn'].fetchval(event_ticket_types_sql, event_id)
    return raw_json_response(json_str)


@is_admin_or_host
async def event_updates_sent(request):
    event_id = await _check_event_host(request)
    json_str = await request['conn'].fetchval(event_updates_sent_sql, event_id)
    return raw_json_response(json_str)


class SetTicketTypes(UpdateView):
    class Model(BaseModel):
        class TicketType(BaseModel):
            name: str
            id: int = None
            slots_used: conint(ge=1)
            active: bool
            price: condecimal(ge=1, max_digits=6, decimal_places=2) = None

        ticket_types: List[TicketType]

        @validator('ticket_types', whole=True)
        def check_ticket_types(cls, v):
            if sum(tt.active for tt in v) < 1:
                raise ValueError('at least 1 ticket type must be active')
            return v

    async def check_permissions(self):
        await check_session(self.request, 'admin', 'host')

    async def execute(self, m: Model):
        event_id = await _check_event_host(self.request)
        existing = [tt for tt in m.ticket_types if tt.id]
        deleted_with_tickets = await self.conn.fetchval(
            """
            SELECT 1
            FROM ticket_types AS tt
            JOIN tickets AS t ON tt.id = t.ticket_type
            WHERE tt.event=$1 AND NOT (tt.id=ANY($2))
            GROUP BY tt.id
            """, event_id, [tt.id for tt in existing]
        )
        if deleted_with_tickets:
            raise JsonErrors.HTTPBadRequest(message='ticket types deleted which have ticket associated with them')

        async with self.conn.transaction():
            await self.conn.fetchval(
                """
                DELETE FROM ticket_types
                WHERE ticket_types.event=$1 AND NOT (ticket_types.id=ANY($2))
                """, event_id, [tt.id for tt in existing]
            )

            for tt in existing:
                v = await self.conn.execute_b(
                    'UPDATE ticket_types SET :values WHERE id=:id AND event=:event',
                    values=SetValues(**tt.dict(exclude={'id'})),
                    id=tt.id,
                    event=event_id,
                )
                if v != 'UPDATE 1':
                    raise JsonErrors.HTTPBadRequest(message='wrong ticket updated')

            new = [tt for tt in m.ticket_types if not tt.id]
            if new:
                await self.conn.execute_b(
                    """
                    INSERT INTO ticket_types (:values__names) VALUES :values
                    """,
                    values=MultipleValues(*(Values(event=event_id, **tt.dict(exclude={'id'})) for tt in new))
                )
            await record_action(self.request, self.request['session']['user_id'], ActionTypes.edit_event,
                                event_id=event_id, subtype='edit-ticket-types')


get_image_sql = """
SELECT e.host, e.image
FROM events as e
JOIN categories AS cat ON e.category = cat.id
JOIN companies co ON cat.company = co.id
WHERE co.id=$1 AND e.id=$2
"""


async def _delete_existing_image(request):
    event_id = int(request.match_info['id'])

    try:
        host_id, image = await request['conn'].fetchrow(get_image_sql, request['company_id'], event_id)
    except TypeError:
        raise JsonErrors.HTTPNotFound(message='event not found')

    if request['session']['role'] != 'admin' and host_id != request['session']['user_id']:
        raise JsonErrors.HTTPForbidden(message='you may not edit this event')

    # delete the image from S3 if it's set and isn't a category image option
    if image and '/option/' not in image:
        await delete_image(image, request.app['settings'])
    await record_action(request, request['session']['user_id'], ActionTypes.edit_event,
                        event_id=event_id, subtype='delete-image')


slugs_sql = """
SELECT co.slug, cat.slug, e.slug
FROM events AS e
JOIN categories AS cat ON e.category = cat.id
JOIN companies co ON cat.company = co.id
WHERE co.id=$1 AND e.id=$2
"""


@is_admin_or_host
async def set_event_image_new(request):
    content = await request_image(request)

    await _delete_existing_image(request)

    event_id = int(request.match_info['id'])
    co_slug, cat_slug, event_slug = await request['conn'].fetchrow(slugs_sql, request['company_id'], event_id)

    upload_path = Path(co_slug) / cat_slug / event_slug

    image_url = await resize_upload(content, upload_path, request.app['settings'])
    await request['conn'].execute('UPDATE events SET image=$1 WHERE id=$2', image_url, event_id)
    await record_action(request, request['session']['user_id'], ActionTypes.edit_event,
                        event_id=event_id, subtype='set-image-new')
    return json_response(status='success')


@is_admin_or_host
async def set_event_image_existing(request):
    m = await parse_request(request, ImageModel)
    if not m.image.startswith(request.app['settings'].s3_domain):
        raise JsonErrors.HTTPBadRequest(message='image not allowed')

    await _delete_existing_image(request)

    event_id = int(request.match_info['id'])
    await request['conn'].execute('UPDATE events SET image=$1 WHERE id=$2', m.image, event_id)
    await record_action(request, request['session']['user_id'], ActionTypes.edit_event,
                        event_id=event_id, subtype='set-image-existing')
    return json_response(status='success')


class StatusChoices(Enum):
    pending = 'pending'
    published = 'published'
    suspended = 'suspended'


class SetEventStatus(UpdateView):
    class Model(BaseModel):
        status: StatusChoices

    async def check_permissions(self):
        await check_session(self.request, 'admin', 'host')
        await _check_event_host(self.request)
        user_status = await self.conn.fetchrow('SELECT status FROM users WHERE id=$1', self.session['user_id'])
        if self.session['role'] != 'admin' and user_status != 'active':
            raise JsonErrors.HTTPForbidden(message='Host not active')

    async def execute(self, m: Model):
        event_id = int(self.request.match_info['id'])
        await self.conn.execute_b(
            'UPDATE events SET status=:status WHERE id=:id',
            status=m.status.value,
            id=event_id,
        )
        await record_action(self.request, self.request['session']['user_id'], ActionTypes.edit_event,
                            event_id=event_id, subtype='change-status')


class EventUpdate(UpdateView):
    class Model(GrecaptchaModel):
        subject: constr(max_length=200)
        message: str

    async def check_permissions(self):
        await check_session(self.request, 'admin', 'host')

    async def execute(self, m: Model):
        await check_grecaptcha(m, self.request)
        event_id = await _check_event_host(self.request)
        action_id = await record_action_id(self.request, self.session['user_id'], ActionTypes.event_update,
                                           event_id=event_id, **m.dict(include={'subject', 'message'}))
        await self.app['email_actor'].send_event_update(action_id)


@is_admin
async def switch_highlight(request):
    event_id = await _check_event_host(request)
    await request['conn'].execute('UPDATE events SET highlight=NOT highlight WHERE id=$1', event_id)
    await record_action(request, request['session']['user_id'], ActionTypes.edit_event,
                        event_id=event_id, subtype='switch-highlight')
    return json_response(status='ok')
