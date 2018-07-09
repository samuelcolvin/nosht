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
from pydantic import BaseModel, EmailStr, constr

from shared.utils import slugify
from web.auth import check_session, is_admin_or_host, is_auth
from web.bread import Bread, UpdateView
from web.utils import JsonErrors, encrypt_json, raw_json_response

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
           'name', e.location,
           'lat', e.location_lat,
           'lng', e.location_lng
         ) AS location,
         e.price,
         e.start_ts,
         EXTRACT(epoch FROM e.duration)::int AS duration,
         e.ticket_limit,
         h.id AS host_id,
         h.first_name || ' ' || h.last_name AS host_name,
         co.stripe_public_key AS stripe_key
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
        'e.location',
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
                location=loc['name'],
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


EVENT_BOOKING_INFO_SQL = """
SELECT json_build_object('event', row_to_json(event_data))
FROM (
  SELECT check_tickets_remaining(e.id) AS tickets_remaining
  FROM events AS e
  JOIN categories cat on e.category = cat.id
  WHERE cat.company=$1 AND e.id=$2 AND e.status='published'
) AS event_data;
"""


@is_auth
async def booking_info(request):
    # TODO more info, eg information require from cat
    event_id = int(request.match_info['id'])
    json_str = await request['conn'].fetchval(EVENT_BOOKING_INFO_SQL, request['company_id'], event_id)
    return raw_json_response(json_str)


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


def split_name(raw_name):
    if not raw_name:
        return None, None
    if ' ' not in raw_name:
        # assume just last_name
        return None, raw_name.strip(' ')
    else:
        return [n.strip(' ') for n in raw_name.split(' ', 1)]


class ReserveTickets(UpdateView):
    class Model(BaseModel):
        tickets: List[TicketModel]

    def _get_event_id(self):
        return int(self.request.match_info['id'])

    async def check_permissions(self):
        await check_session(self.request, 'admin', 'host', 'guest')

    async def execute(self, m: Model):
        event_id = self._get_event_id()
        ticket_count = len(m.tickets)
        if ticket_count < 1:
            raise JsonErrors.HTTPBadRequest(message='at least one ticket must be purchased')

        status, event_price = await self.conn.fetchrow(
            """
            SELECT e.status, price
            FROM events AS e
            JOIN categories c on e.category = c.id
            WHERE c.company=$1 AND e.id=$2
            """,
            self.request['company_id'], event_id
        )
        if status != 'published':
            raise JsonErrors.HTTPBadRequest(message='Event not published')

        tickets_remaining = await self.conn.fetchval('SELECT check_tickets_remaining($1)', event_id)
        if tickets_remaining is not None and ticket_count > tickets_remaining:
            raise JsonErrors.HTTPBadRequest(message=f'only {tickets_remaining} tickets remaining')

        try:
            async with self.conn.transaction():
                user_lookup = await self.create_users(m.tickets)

                action_id = await self.conn.fetchval_b(
                    'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
                    values=Values(
                        company=self.request['company_id'],
                        user_id=self.session['user_id'],
                        type='reserve_tickets'
                    )
                )
                values = [
                    Values(
                        event=event_id,
                        user_id=user_lookup[t.email.lower()] if t.email else None,
                        reserve_action=action_id,
                        extra=m.json(include={'dietary_req', 'extra_info'})
                    )
                    for t in m.tickets
                ]
                await self.conn.execute_b(
                    'INSERT INTO tickets (:values__names) VALUES :values',
                    values=MultipleValues(*values)
                )
        except CheckViolationError as e:
            logger.warning('CheckViolationError: %s', e)
            raise JsonErrors.HTTPBadRequest(message='insufficient tickets remaining')

        price_cent = int(event_price * ticket_count * 100)
        data = {
            'action_id': action_id,
            'price_cent': price_cent,
            'event_id': event_id,
        }
        return {
            'booking_token': encrypt_json(self.app, data),
            'price_cent': price_cent,
            'reserve_time': int(time()),
            'ticket_count': ticket_count,
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
