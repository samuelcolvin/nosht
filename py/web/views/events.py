import logging
from datetime import datetime, timedelta
from enum import Enum
from textwrap import shorten
from time import time
from typing import List, Optional

from asyncpg import CheckViolationError
from buildpg import MultipleValues, V, Values, funcs
from buildpg.asyncpg import BuildPgConnection
from buildpg.clauses import Join, Where
from pydantic import BaseModel, EmailStr, constr, validator

from shared.utils import slugify
from web.actions import ActionTypes, record_action, record_action_id
from web.auth import check_session, is_admin_or_host, is_auth
from web.bread import Bread, UpdateView
from web.stripe import Reservation, StripePayModel, stripe_pay
from web.utils import JsonErrors, decrypt_json, encrypt_json, json_response, raw_json_response, split_name, to_json_if

logger = logging.getLogger('nosht.events')

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
           'name', e.location_name,
           'lat', e.location_lat,
           'lng', e.location_lng
         ) AS location,
         e.price,
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
         co.currency as currency
  FROM events AS e
  JOIN categories AS c ON e.category = c.id
  JOIN companies AS co ON c.company = co.id
  JOIN users AS h ON e.host = h.id
  WHERE c.company=$1 AND c.slug=$2 AND e.slug=$3 AND e.status='published'
) AS event;
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

        location: LocationModel
        ticket_limit: int = None
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
        V('c.name').as_('category'),
        'e.highlight',
        'e.start_ts',
        funcs.extract(V('epoch').from_(V('e.duration'))).cast('int').as_('duration'),
    )
    retrieve_fields = browse_fields + (
        'e.slug',
        V('c.slug').as_('cat_slug'),
        'e.public',
        'e.status',
        'e.ticket_limit',
        'e.location_name',
        'e.location_lat',
        'e.location_lng',
        'e.long_description',
    )

    async def check_permissions(self, method):
        await check_session(self.request, 'admin', 'host')

    def join(self):
        return Join(V('categories').as_('c').on(V('c.id') == V('e.category')))

    def where(self):
        logic = V('c.company') == self.request['company_id']
        session = self.request['session']
        user_role = session['user_role']
        if user_role != 'admin':
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

    def prepare_add_data(self, data):
        data = self.prepare(data)
        data.update(
            slug=slugify(data['name']),
            host=self.request['session'].get('user_id'),
        )
        return data

    def prepare_edit_data(self, data):
        return self.prepare(data)


event_ticket_sql = """
SELECT json_build_object('tickets', tickets)
FROM (
  SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') AS tickets FROM (
    SELECT t.id as ticket_id, t.extra, u.id AS user_id,
      full_name(u.first_name, u.last_name, u.email) AS user_name, a.ts AS bought_at,
      ub.id as buyer_id, full_name(ub.first_name, ub.last_name, u.email) AS buyer_name
    FROM tickets AS t
    LEFT JOIN users u on t.user_id = u.id
    JOIN actions a on t.paid_action = a.id
    JOIN users ub on a.user_id = ub.id
    WHERE t.event=$1 AND a.company=$2 AND t.status='paid'
    ORDER BY a.ts
  ) AS t
) AS tickets
"""


@is_admin_or_host
async def event_tickets(request):
    event_id = int(request.match_info['id'])
    if request['session']['user_role'] == 'host':
        host_id = await request['conn'].fetchval('SELECT host FROM events WHERE id=$1', event_id)
        if host_id != request['session']['user_id']:
            raise JsonErrors.HTTPForbidden(message='use is not the host of this event')

    json_str = await request['conn'].fetchval(event_ticket_sql, event_id, request['company_id'])
    return raw_json_response(json_str)


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
        JOIN actions a on tickets.reserve_action = a.id
        WHERE event=$1 AND a.user_id=$2 AND status='paid'
        """,
        event_id,
        request['session']['user_id']
    )
    return json_response(
        tickets_remaining=tickets_remaining if (tickets_remaining and tickets_remaining < 10) else None,
        existing_tickets=existing_tickets or 0,
    )


class DietaryReqEnum(Enum):
    thing_1 = 'thing_1'
    thing_2 = 'thing_2'
    thing_3 = 'thing_3'


class TicketModel(BaseModel):
    t: bool
    name: constr(max_length=255) = None
    email: EmailStr = None
    dietary_req: DietaryReqEnum = None
    extra_info: str = None


class ReserveTickets(UpdateView):
    class Model(BaseModel):
        tickets: List[TicketModel]

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

        status, event_price, event_name = await self.conn.fetchrow(
            """
            SELECT e.status, e.price, e.name
            FROM events AS e
            JOIN categories c on e.category = c.id
            WHERE c.company=$1 AND e.id=$2
            """,
            self.request['company_id'], event_id
        )
        if status != 'published':
            raise JsonErrors.HTTPBadRequest(message='Event not published')

        if self.settings.ticket_reservation_precheck:  # should only be false during CheckViolationError tests
            tickets_remaining = await self.conn.fetchval(
                'SELECT check_tickets_remaining($1, $2)', event_id, self.settings.ticket_ttl
            )
            if tickets_remaining is not None and ticket_count > tickets_remaining:
                raise JsonErrors.HTTP470(message=f'only {tickets_remaining} tickets remaining',
                                         tickets_remaining=tickets_remaining)

        try:
            async with self.conn.transaction():
                user_lookup = await self.create_users(m.tickets)

                action_id = await record_action_id(self.request, self.session['user_id'], ActionTypes.reserve_tickets)
                await self.conn.execute_b(
                    'INSERT INTO tickets (:values__names) VALUES :values',
                    values=MultipleValues(*[
                        Values(
                            event=event_id,
                            user_id=user_lookup[t.email.lower()] if t.email else None,
                            reserve_action=action_id,
                            extra=to_json_if(t.dict(include={'dietary_req', 'extra_info'})),
                        )
                        for t in m.tickets
                    ])
                )
                await self.conn.execute('SELECT check_tickets_remaining($1, $2)', event_id, self.settings.ticket_ttl)
        except CheckViolationError as e:
            logger.warning('CheckViolationError: %s', e)
            raise JsonErrors.HTTPBadRequest(message='insufficient tickets remaining')

        user = await self.conn.fetchrow(
            """
            SELECT id, full_name(first_name, last_name, email) AS name, email, role
            FROM users
            WHERE id=$1
            """,
            self.session['user_id']
        )
        # TODO needs to work when the event is free
        price_cent = int(event_price * ticket_count * 100)
        res = Reservation(
            user_id=self.session['user_id'],
            action_id=action_id,
            price_cent=price_cent,
            event_id=event_id,
            ticket_count=ticket_count,
            event_name=event_name,
        )
        return {
            'booking_token': encrypt_json(self.app, res.dict()),
            'ticket_count': ticket_count,
            'item_price_cent': int(event_price * 100),
            'total_price_cent': price_cent,
            'user': dict(user),
            'timeout': int(time()) + self.settings.ticket_ttl,
        }

    async def create_users(self, tickets: List[TicketModel]):
        user_values = []

        for t in tickets:
            if t.name or t.email:
                first_name, last_name = split_name(t.name)
                user_values.append(
                    Values(
                        company=self.request['company_id'],
                        role='guest',
                        first_name=first_name,
                        last_name=last_name,
                        email=t.email and t.email.lower(),
                    )
                )
        rows = await self.conn.fetch_b(
            """
            INSERT INTO users AS u (:values__names) VALUES :values
            ON CONFLICT (company, email) DO UPDATE SET
              first_name=coalesce(u.first_name, EXCLUDED.first_name),
              last_name=coalesce(u.last_name, EXCLUDED.last_name)
            RETURNING id, email
            """,
            values=MultipleValues(*user_values)
        )
        return {r['email']: r['id'] for r in rows}


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
        paid_action_id = await stripe_pay(m, self.request['company_id'], self.session.get('user_id'),
                                          self.app, self.conn)
        await self.app['email_actor'].send_event_conf(paid_action_id)
