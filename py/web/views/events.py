import logging
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from textwrap import shorten
from time import time
from typing import List, Optional

from asyncpg import CheckViolationError
from buildpg import MultipleValues, SetValues, V, Values, funcs
from buildpg.asyncpg import BuildPgConnection
from buildpg.clauses import Join, Where
from pydantic import BaseModel, EmailStr, condecimal, conint, constr, validator

from shared.images import delete_image, resize_upload
from shared.utils import pseudo_random_str, slugify
from web.actions import ActionTypes, record_action, record_action_id
from web.auth import check_session, is_admin_or_host, is_auth
from web.bread import Bread, UpdateView
from web.stripe import BookingModel, Reservation, StripePayModel, book_free, stripe_pay
from web.utils import (ImageModel, JsonErrors, decrypt_json, encrypt_json, json_response, parse_request,
                       raw_json_response, request_image, to_json_if)

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
         co.currency as currency,
         c.ticket_extra_title,
         c.ticket_extra_help_text
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
    SELECT id, name, host_advice, event_type
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
        'e.status',
        'e.ticket_limit',
        V('co.currency').as_('currency'),
        'e.location_name',
        'e.location_lat',
        'e.location_lng',
        'e.long_description',
    )

    async def check_permissions(self, method):
        await check_session(self.request, 'admin', 'host')

    def join(self):
        return (
            Join(V('categories').as_('cat').on(V('cat.id') == V('e.category'))) +
            Join(V('companies').as_('co').on(V('co.id') == V('cat.company')))
        )

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

        long_desc = data.get('long_description')
        if long_desc is not None:
            data['short_description'] = shorten(long_desc, width=140, placeholder='…')
        return data

    async def prepare_add_data(self, data):
        data = self.prepare(data)
        session = self.request['session']
        data.update(
            slug=slugify(data['name']),
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
        return pk


async def _check_event_host(request):
    event_id = int(request.match_info['id'])
    if request['session']['role'] == 'host':
        host_id = await request['conn'].fetchval(
            """
            SELECT host
            FROM events AS e
            JOIN categories AS cat ON e.category = cat.id
            WHERE e.id=$1 AND cat.company=$2
            """, event_id, request['company_id'])
        if not host_id:
            raise JsonErrors.HTTPNotFound(message='event not found')
        if host_id != request['session']['user_id']:
            raise JsonErrors.HTTPForbidden(message='use is not the host of this event')
    return event_id


event_tickets_sql = """
SELECT json_build_object('tickets', tickets)
FROM (
  SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') AS tickets FROM (
    SELECT t.id as ticket_id, t.extra, u.id AS user_id,
      full_name(u.first_name, u.last_name, u.email) AS user_name, a.ts AS bought_at, tt.name AS ticket_type,
      ub.id as buyer_id, full_name(ub.first_name, ub.last_name, u.email) AS buyer_name
    FROM tickets AS t
    LEFT JOIN users u ON t.user_id = u.id
    JOIN actions a ON t.booked_action = a.id
    JOIN users ub ON a.user_id = ub.id
    JOIN ticket_types tt ON t.ticket_type = tt.id
    WHERE t.event=$1 AND t.status='booked'
    ORDER BY a.ts
  ) AS t
) AS tickets
"""


@is_admin_or_host
async def event_tickets(request):
    event_id = await _check_event_host(request)
    json_str = await request['conn'].fetchval(event_tickets_sql, event_id)
    return raw_json_response(json_str)


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


@is_admin_or_host
async def event_ticket_types(request):
    event_id = await _check_event_host(request)
    json_str = await request['conn'].fetchval(event_ticket_types_sql, event_id)
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


GET_IMAGE_SQL = """
SELECT e.host, e.image
FROM events as e
JOIN categories AS cat ON e.category = cat.id
JOIN companies co ON cat.company = co.id
WHERE co.id=$1 AND e.id=$2
"""


async def _delete_existing_image(request):
    event_id = int(request.match_info['id'])

    try:
        host_id, image = await request['conn'].fetchrow(GET_IMAGE_SQL, request['company_id'], event_id)
    except TypeError:
        raise JsonErrors.HTTPNotFound(message='event not found')

    if request['session']['role'] != 'admin' and host_id != request['session']['user_id']:
        raise JsonErrors.HTTPForbidden(message='you may not edit this event')

    # delete the image from S3 if it's set and isn't a category image option
    if image and '/option/' not in image:
        await delete_image(image, request.app['settings'])


SLUGS_SQL = """
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
    co_slug, cat_slug, event_slug = await request['conn'].fetchrow(SLUGS_SQL, request['company_id'], event_id)

    upload_path = Path(co_slug) / cat_slug / event_slug

    image_url = await resize_upload(content, upload_path, request.app['settings'])
    await request['conn'].execute('UPDATE events SET image=$1 WHERE id=$2', image_url, event_id)
    return json_response(status='success')


@is_admin_or_host
async def set_event_image_existing(request):
    m = await parse_request(request, ImageModel)
    if not m.image.startswith(request.app['settings'].s3_domain):
        raise JsonErrors.HTTPBadRequest(message='image not allowed')

    await _delete_existing_image(request)

    await request['conn'].execute('UPDATE events SET image=$1 WHERE id=$2', m.image, int(request.match_info['id']))
    return json_response(status='success')


class StatusChoices(Enum):
    pending = 'pending'
    published = 'published'
    suspended = 'suspended'


class SetEventStatus(UpdateView):
    class Model(BaseModel):
        status: StatusChoices

    async def check_permissions(self):
        await check_session(self.request, 'admin')
        v = await self.conn.fetchval_b(
            """
            SELECT 1 FROM events AS e
            JOIN categories AS c on e.category = c.id
            WHERE e.id=:id AND c.company=:company
            """,
            id=int(self.request.match_info['id']),
            company=self.request['company_id']
        )
        if not v:
            raise JsonErrors.HTTPNotFound(message='Event not found')

    async def execute(self, m: Model):
        await self.conn.execute_b(
            'UPDATE events SET status=:status WHERE id=:id',
            status=m.status.value,
            id=int(self.request.match_info['id']),
        )


@is_auth
async def booking_info(request):
    event_id = int(request.match_info['id'])
    conn: BuildPgConnection = request['conn']
    settings = request.app['settings']
    tickets_remaining = await conn.fetchval('SELECT check_tickets_remaining($1, $2)', event_id, settings.ticket_ttl)
    existing_tickets = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM tickets
        JOIN actions AS a ON tickets.reserve_action = a.id
        WHERE event=$1 AND a.user_id=$2 AND status='booked'
        """,
        event_id,
        request['session']['user_id']
    )
    ticket_types = await conn.fetch('SELECT id, name, price::float FROM ticket_types WHERE event=$1', event_id)
    return json_response(
        tickets_remaining=tickets_remaining if (tickets_remaining and tickets_remaining < 10) else None,
        existing_tickets=existing_tickets or 0,
        ticket_types=[dict(tt) for tt in ticket_types],
    )


class TicketModel(BaseModel):
    t: bool
    first_name: constr(max_length=255) = None
    last_name: constr(max_length=255) = None
    email: EmailStr = None
    extra_info: str = None


class ReserveTickets(UpdateView):
    class Model(BaseModel):
        tickets: List[TicketModel]
        ticket_type: int

        @validator('tickets', whole=True)
        def check_ticket_count(cls, v):
            if not v:
                raise ValueError('at least one ticket must be purchased')
            return v

    async def check_permissions(self):
        await check_session(self.request, 'admin', 'host', 'guest')

    async def execute(self, m: Model):
        event_id = int(self.request.match_info['id'])
        ticket_count = len(m.tickets)
        user_id = self.session['user_id']

        status, event_name = await self.conn.fetchrow(
            """
            SELECT e.status, e.name
            FROM events AS e
            JOIN categories c on e.category = c.id
            WHERE c.company=$1 AND e.id=$2
            """,
            self.request['company_id'], event_id
        )

        if status != 'published':
            raise JsonErrors.HTTPBadRequest(message='Event not published')

        r = await self.conn.fetchrow('SELECT price FROM ticket_types WHERE event=$1 AND id=$2',
                                     event_id, m.ticket_type)
        if not r:
            raise JsonErrors.HTTPBadRequest(message='Ticket type not found')
        price, *_ = r

        if self.settings.ticket_reservation_precheck:  # should only be false during CheckViolationError tests
            tickets_remaining = await self.conn.fetchval(
                'SELECT check_tickets_remaining($1, $2)', event_id, self.settings.ticket_ttl
            )
            if tickets_remaining is not None and ticket_count > tickets_remaining:
                raise JsonErrors.HTTP470(message=f'only {tickets_remaining} tickets remaining',
                                         tickets_remaining=tickets_remaining)

        try:
            async with self.conn.transaction():
                await self.create_users(m.tickets)

                action_id = await record_action_id(self.request, user_id, ActionTypes.reserve_tickets)
                ticket_values = [
                    Values(
                        email=t.email and t.email.lower(),
                        first_name=t.first_name,
                        last_name=t.last_name,
                        extra=funcs.cast(to_json_if(t.dict(include={'extra_info'})), 'jsonb'),
                    )
                    for t in m.tickets
                ]

                await self.conn.execute_b(
                    """
                    WITH v (email, first_name, last_name, extra) AS (VALUES :values)
                    INSERT INTO tickets (event, reserve_action, ticket_type, price, user_id,
                      first_name, last_name, extra)
                    SELECT :event, :reserve_action, :ticket_type, :price, u.id,
                      v.first_name, v.last_name, v.extra FROM v
                    LEFT JOIN users AS u ON v.email=u.email AND u.company=:company_id
                    """,
                    event=event_id,
                    reserve_action=action_id,
                    ticket_type=m.ticket_type,
                    price=price,
                    company_id=self.request['company_id'],
                    values=MultipleValues(*ticket_values),
                )
                await self.conn.execute('SELECT check_tickets_remaining($1, $2)', event_id, self.settings.ticket_ttl)
        except CheckViolationError as e:
            logger.warning('CheckViolationError: %s', e)
            raise JsonErrors.HTTPBadRequest(message='insufficient tickets remaining')

        price_cent = price and int(price * ticket_count * 100)
        res = Reservation(
            user_id=user_id,
            action_id=action_id,
            price_cent=price_cent,
            event_id=event_id,
            ticket_count=ticket_count,
            event_name=event_name,
        )
        return {
            'booking_token': encrypt_json(self.app, res.dict()),
            'ticket_count': ticket_count,
            'item_price_cent': price and int(price * 100),
            'total_price_cent': price_cent,
            'timeout': int(time()) + self.settings.ticket_ttl,
        }

    async def create_users(self, tickets: List[TicketModel]):
        user_values = [
            Values(
                company=self.request['company_id'],
                role='guest',
                email=t.email.lower(),
            )
            for t in tickets if t.email
        ]

        await self.conn.execute_b(
            """
            INSERT INTO users AS u (:values__names) VALUES :values
            ON CONFLICT (company, email) DO NOTHING
            """,
            values=MultipleValues(*user_values)
        )


class CancelReservedTickets(UpdateView):
    class Model(BaseModel):
        booking_token: bytes

    async def execute(self, m: Model):
        res = Reservation(**decrypt_json(self.app, m.booking_token, ttl=self.settings.ticket_ttl))
        async with self.conn.transaction():
            user_id = await self.conn.fetchval('SELECT user_id FROM actions WHERE id=$1', res.action_id)
            await self.conn.execute('DELETE FROM tickets WHERE reserve_action=$1', res.action_id)
            await self.conn.execute('SELECT check_tickets_remaining($1, $2)', res.event_id, self.settings.ticket_ttl)
            await record_action(self.request, user_id, ActionTypes.cancel_reserved_tickets)


class BuyTickets(UpdateView):
    Model = StripePayModel

    async def execute(self, m: StripePayModel):
        booked_action_id = await stripe_pay(m, self.request['company_id'], self.session.get('user_id'),
                                            self.app, self.conn)
        await self.app['email_actor'].send_event_conf(booked_action_id)


class BookFreeTickets(UpdateView):
    Model = BookingModel

    async def execute(self, m: BookingModel):
        booked_action_id = await book_free(m, self.request['company_id'], self.session.get('user_id'),
                                           self.app, self.conn)
        await self.app['email_actor'].send_event_conf(booked_action_id)
