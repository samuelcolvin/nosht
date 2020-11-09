import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from secrets import compare_digest
from textwrap import shorten
from typing import List, Optional, Tuple

import pytz
from asyncpg import CheckViolationError
from buildpg import Func, MultipleValues, SetValues, V, Values, funcs
from buildpg.asyncpg import BuildPgConnection
from buildpg.clauses import Join, Select, Where
from pydantic import BaseModel, HttpUrl, PositiveInt, condecimal, conint, constr, validator
from pytz.tzinfo import StaticTzInfo

from shared.images import delete_image, upload_background, upload_force_shape, upload_other
from shared.utils import pseudo_random_str, slugify, ticket_id_signed
from web.actions import ActionTypes, record_action, record_action_id
from web.auth import check_session, is_admin, is_admin_or_host
from web.bread import Bread, Method, UpdateView
from web.stripe import stripe_refund
from web.utils import (
    ImageModel,
    JsonErrors,
    clean_markdown,
    json_response,
    parse_request,
    prepare_search_query,
    raw_json_response,
    request_image,
)
from web.views.export import export_plumbing

logger = logging.getLogger('nosht.events')

event_id_public_sql = """
SELECT e.id, e.public
FROM events AS e
JOIN categories AS c ON e.category = c.id
WHERE c.company = $1 AND c.slug = $2 AND e.slug = $3 AND e.status = 'published'
"""
event_info_sql = """
SELECT json_build_object(
  'event', row_to_json(event),
  'ticket_types', ticket_types,
  'existing_tickets', existing_tickets,
  'on_waiting_list', on_waiting_list
)
FROM (
  SELECT e.id,
         e.name,
         coalesce(e.image, c.image) AS image,
         e.secondary_image,
         e.youtube_video_id,
         e.short_description,
         e.description_image,
         e.description_intro,
         e.long_description,
         e.external_ticket_url,
         e.external_donation_url,
         e.allow_tickets,
         e.allow_donations,
         c.event_content AS category_content,
         json_build_object(
           'name', e.location_name,
           'lat', e.location_lat,
           'lng', e.location_lng
         ) AS location,
         e.start_ts AT TIME ZONE e.timezone AS start_ts,
         tz_abbrev(e.start_ts, e.timezone) as tz,
         extract(epoch FROM e.duration)::int AS duration,
         CASE
           WHEN e.ticket_limit IS NULL THEN NULL
           WHEN e.ticket_limit - e.tickets_taken >= 10 THEN NULL
           ELSE e.ticket_limit - e.tickets_taken
         END AS tickets_available,
         h.id AS host_id,
         h.first_name || ' ' || h.last_name AS host_name,
         c.id AS category_id,
         c.ticket_extra_title,
         c.ticket_extra_help_text,
         c.booking_trust_message,
         c.cover_costs_message,
         c.cover_costs_percentage,
         c.terms_and_conditions_message,
         c.allow_marketing_message
  FROM events AS e
  JOIN categories AS c ON e.category = c.id
  JOIN users AS h ON e.host = h.id
  WHERE e.id = $1
) AS event,
(
  SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') AS ticket_types FROM (
    SELECT tt.name, tt.price, tt.mode
    FROM ticket_types AS tt
    JOIN events AS e ON tt.event = e.id
    WHERE e.id = $1 AND tt.active = TRUE AND tt.custom_amount = FALSE
    ORDER BY tt.price
  ) AS t
) AS ticket_types,
(
  SELECT count(*) AS existing_tickets
  FROM tickets t
  JOIN actions AS a ON t.reserve_action = a.id
  WHERE t.event=$1 AND t.status='booked' AND a.user_id=$2
) AS existing_tickets,
(
  SELECT count(*) > 0 AS on_waiting_list
  FROM waiting_list
  WHERE event=$1 AND user_id=$2
) AS on_waiting_list
"""


class TzInfo(StaticTzInfo):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        try:
            return pytz.timezone(v)
        except KeyError:
            raise ValueError('invalid timezone')


async def check_event_sig(request):
    company_id = request['company_id']
    category_slug = request.match_info['category']
    event_slug = request.match_info['event']
    r = await request['conn'].fetchrow(event_id_public_sql, company_id, category_slug, event_slug)

    # so we always do the hashing even for an event that does exist to avoid timing attack, probably over kill
    if r:
        event_id, event_is_public = r
    else:
        event_id, event_is_public = 0, False

    if not event_is_public:
        url_sig = request.match_info.get('sig')
        if not url_sig:
            raise JsonErrors.HTTPNotFound(message='event not found')
        sig = hmac.new(
            request.app['settings'].auth_key.encode(), f'/{category_slug}/{event_slug}/'.encode(), digestmod=hashlib.md5
        ).hexdigest()
        if not compare_digest(url_sig, sig):
            raise JsonErrors.HTTPNotFound(message='event not found')
    return event_id


async def event_get(request):
    event_id = await check_event_sig(request)
    user_id = request['session'].get('user_id', 0)
    json_str = await request['conn'].fetchval(event_info_sql, event_id, user_id)
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


class DateModel(BaseModel):
    dt: datetime
    dur: Optional[int]


class EventMode(Enum):
    tickets = 'tickets'
    donations = 'donations'
    both = 'both'


class EventBread(Bread):
    class Model(BaseModel):
        name: constr(max_length=150)
        category: int
        public: bool = True
        timezone: TzInfo
        date: DateModel

        mode: EventMode = EventMode.tickets

        class LocationModel(BaseModel):
            lat: float
            lng: float
            name: constr(max_length=63)

        location: LocationModel = None
        ticket_limit: PositiveInt = None
        price: condecimal(ge=1, max_digits=6, decimal_places=2) = None
        suggested_donation: condecimal(ge=1, max_digits=6, decimal_places=2) = None
        donation_target: condecimal(ge=0, max_digits=9, decimal_places=2) = None
        long_description: str
        short_description: str = None
        youtube_video_id: str = None
        description_image: str = None
        description_intro: str = None
        external_ticket_url: HttpUrl = None
        external_donation_url: HttpUrl = None

        @validator('public', pre=True)
        def none_bool(cls, v):
            return v or False

    browse_enabled = True
    retrieve_enabled = True
    add_enabled = True
    edit_enabled = True
    delete_enabled = True

    model = Model
    table = 'events'
    table_as = 'e'

    browse_fields = (
        'e.id',
        'e.name',
        V('cat.name').as_('category'),
        'e.status',
        'e.highlight',
        Func('as_time_zone', V('e.start_ts'), V('e.timezone')).as_('start_ts'),
        funcs.extract(V('epoch').from_(V('e.duration'))).cast('int').as_('duration'),
    )
    browse_order_by_fields = (V('e.start_ts').desc(),)
    retrieve_fields = browse_fields + (
        V('cat.id').as_('cat_id'),
        'e.public',
        'e.allow_tickets',
        'e.allow_donations',
        'e.image',
        'e.secondary_image',
        'e.ticket_limit',
        'e.donation_target',
        'e.location_name',
        'e.location_lat',
        'e.location_lng',
        'e.youtube_video_id',
        'e.short_description',
        'e.long_description',
        'e.description_image',
        'e.description_intro',
        'e.external_ticket_url',
        'e.external_donation_url',
        'e.host',
        'e.timezone',
        Func('full_name', V('uh.first_name'), V('uh.last_name'), V('uh.email')).as_('host_name'),
    )

    async def check_permissions(self, method):
        if method == Method.delete:
            await check_session(self.request, 'admin')
        else:
            await check_session(self.request, 'admin', 'host')

    def select(self) -> Select:
        if self.method == Method.retrieve:
            event_link = Func(
                'event_link', V('cat.slug'), V('e.slug'), V('e.public'), funcs.cast(self.settings.auth_key, 'TEXT')
            ).as_('link')
            return Select(self.retrieve_fields + (event_link,))
        return super().select()

    def join(self):
        joins = Join(V('categories').as_('cat').on(V('cat.id') == V('e.category'))) + Join(
            V('companies').as_('co').on(V('co.id') == V('cat.company'))
        )
        if self.method == Method.retrieve:
            joins += Join(V('users').as_('uh').on(V('uh.id') == V('e.host')))
        return joins

    def where(self):
        logic = V('cat.company') == self.request['company_id']
        session = self.request['session']
        if session['role'] != 'admin':
            logic &= V('e.host') == session['user_id']
            if self.method == Method.edit:
                logic &= V('e.start_ts') > funcs.now()
        return Where(logic)

    def prepare(self, data):
        if self.request['session']['role'] != 'admin':
            if data.get('external_ticket_url'):
                raise JsonErrors.HTTPForbidden(message='external_ticket_url may only be set by admins')
            elif data.get('external_donation_url'):
                raise JsonErrors.HTTPForbidden(message='external_donation_url may only be set by admins')

        timezone: TzInfo = data.pop('timezone', None)
        if timezone:
            data['timezone'] = str(timezone)
        date = data.pop('date', None)
        if date:
            dt, duration = prepare_event_start(date['dt'], date['dur'], timezone)
            data.update(
                start_ts=dt, duration=duration,
            )

        loc = data.pop('location', None)
        if loc:
            data.update(
                location_name=loc['name'], location_lat=loc['lat'], location_lng=loc['lng'],
            )

        return data

    async def prepare_add_data(self, data):
        data = self.prepare(data)

        session = self.request['session']
        mode: EventMode = data.pop('mode', EventMode.tickets)
        data.update(
            slug=slugify(data['name'], 63),
            short_description=shorten(clean_markdown(data['long_description']), width=140, placeholder='…'),
            host=session['user_id'],
            allow_tickets=mode in (EventMode.tickets, EventMode.both),
            allow_donations=mode in (EventMode.donations, EventMode.both),
        )

        q = 'SELECT status FROM users WHERE id=$1'
        if session['role'] == 'admin' or 'active' == await self.conn.fetchval(q, session['user_id']):
            data['status'] = 'published'
        return data

    async def prepare_edit_data(self, pk, data):
        timezone: TzInfo = data.get('timezone')
        if not timezone and 'date' in data:
            # timezone is needed when date is being updated
            tz = await self.conn.fetchval('SELECT timezone FROM events WHERE id=$1', pk)
            data['timezone'] = pytz.timezone(tz)

        data = self.prepare(data)

        if timezone and 'start_ts' not in data:
            # timezone has changed but not start_ts, need to update start_ts to account for timezone change
            dt = await self.conn.fetchval("SELECT start_ts AT TIME ZONE timezone FROM events WHERE id=$1", pk)
            data['start_ts'] = timezone.localize(dt)

        mode: EventMode = data.pop('mode', None)
        if mode is not None:
            data.update(
                allow_tickets=mode in (EventMode.tickets, EventMode.both),
                allow_donations=mode in (EventMode.donations, EventMode.both),
            )
        return data

    add_sql = """
    INSERT INTO :table (:values__names) VALUES :values
    ON CONFLICT (category, slug) DO NOTHING
    RETURNING :pk_field
    """

    async def add_execute(self, *, slug, **data):
        price = data.pop('price', None)
        # we always create a suggested donation and the amount cannot be blank
        suggested_donation = data.pop('suggested_donation', price or 10)

        async with self.conn.transaction():
            pk = await super().add_execute(slug=slug, **data)
            while pk is None:
                # event with this slug already exists
                pk = await super().add_execute(slug=slug + '-' + pseudo_random_str(4), **data)

            # always create both a ticket type and a suggested donation in case the mode of the event changes in future
            await self.conn.execute_b(
                'INSERT INTO ticket_types (:values__names) VALUES :values',
                values=MultipleValues(
                    Values(event=pk, name='Standard', price=price, mode='ticket', custom_amount=False),
                    Values(event=pk, name='Standard', price=suggested_donation, mode='donation', custom_amount=False),
                    Values(event=pk, name='Custom Amount', price=None, mode='donation', custom_amount=True),
                ),
            )
            action_id = await record_action_id(
                self.request, self.request['session']['user_id'], ActionTypes.create_event, event_id=pk
            )
        await self.app['email_actor'].send_event_created(action_id)
        await self.app['donorfy_actor'].event_created(pk)
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
                ],
            )
        else:
            await record_action(
                self.request,
                self.request['session']['user_id'],
                ActionTypes.edit_event,
                event_id=pk,
                subtype='edit-event',
            )
            await self.app['email_actor'].send_tickets_available(pk)


async def _check_event_permissions(request, check_upcoming=False):
    event_id = int(request.match_info['id'])
    r = await request['conn'].fetchrow(
        """
        SELECT host, start_ts
        FROM events AS e
        JOIN categories AS cat ON e.category = cat.id
        WHERE e.id=$1 AND cat.company=$2
        """,
        event_id,
        request['company_id'],
    )
    if not r:
        raise JsonErrors.HTTPNotFound(message='event not found')
    host_id, start_ts = r
    if request['session']['role'] != 'admin':
        if host_id != request['session']['user_id']:
            raise JsonErrors.HTTPForbidden(message='user is not the host of this event')
        if check_upcoming and start_ts < datetime.utcnow().replace(tzinfo=timezone.utc):
            raise JsonErrors.HTTPForbidden(message="you can't modify past events")
    return event_id


event_tickets_sql = """
SELECT DISTINCT ON (t.id)
  t.id, t.price::float AS price, t.extra_donated::float AS extra_donated, t.extra_info,
  iso_ts(a.ts, co.display_timezone) AS booked_at,
  t.status as ticket_status,
  t.user_id AS guest_user_id, full_name(t.first_name, t.last_name) AS guest_name, ug.email AS guest_email,
  a.user_id as buyer_user_id,
  a.type as booking_type,
  coalesce(full_name(tb.first_name, tb.last_name), full_name(ub.first_name, ub.last_name)) AS buyer_name,
  ub.email AS buyer_email,
  tt.name AS ticket_type_name, tt.id AS ticket_type_id
FROM tickets AS t
LEFT JOIN users AS ug ON t.user_id = ug.id
JOIN actions AS a ON t.booked_action = a.id
JOIN companies AS co ON a.company = co.id
LEFT JOIN tickets AS tb ON (a.user_id = tb.user_id AND a.id = tb.booked_action)
JOIN users AS ub ON a.user_id = ub.id
JOIN ticket_types AS tt ON t.ticket_type = tt.id
WHERE t.event=$1 AND t.status!='reserved'
ORDER BY t.id
"""
event_waiting_list_sql = """
select full_name(u.first_name, u.last_name) as name, u.email, iso_ts(w.added_ts, 'Europe/London') added_ts
from waiting_list w
join users u on w.user_id = u.id
where w.event=$1
"""
event_donations_sql = """
select don.id, don.amount::float, don.ticket_type ticket_type_id, a.user_id, u.email AS user_email,
  don.donation_option, don.gift_aid,
  full_name(u.first_name, u.last_name) as name,
  iso_ts(a.ts, 'Europe/London') as timestamp
from donations don
join actions a on don.action = a.id
join users u on a.user_id = u.id
where a.event=$1
order by id desc
"""


@is_admin_or_host
async def event_tickets(request):
    event_id = await _check_event_permissions(request)
    not_admin = request['session']['role'] != 'admin'
    tickets = []
    settings = request.app['settings']
    conn: BuildPgConnection = request['conn']
    for t in await conn.fetch(event_tickets_sql, event_id):
        ticket = {
            'ticket_id': ticket_id_signed(t['id'], settings),
            **t,
        }
        if not_admin:
            ticket.pop('guest_email')
            ticket.pop('buyer_email')
        tickets.append(ticket)

    waiting_list = [dict(r) for r in await conn.fetch(event_waiting_list_sql, event_id)]
    if not_admin:
        [r.pop('email') for r in waiting_list]

    donations = [dict(r) for r in await conn.fetch(event_donations_sql, event_id)]
    if not_admin:
        [r.pop('user_email') for r in donations]
    return json_response(tickets=tickets, waiting_list=waiting_list, donations=donations)


class CancelTickets(UpdateView):
    class Model(BaseModel):
        refund_amount: condecimal(ge=1, max_digits=6, decimal_places=2) = None

    async def check_permissions(self):
        await check_session(self.request, 'admin')

    async def execute(self, m: Model):
        event_id = await _check_event_permissions(self.request)
        ticket_id = int(self.request.match_info['tid'])
        r = await self.conn.fetchrow(
            """
            select a.type, t.price, a.extra->>'charge_id'
            from tickets as t
            join actions as a on t.booked_action = a.id
            where t.event = $1 and t.id = $2 and t.status = 'booked'
            """,
            event_id,
            ticket_id,
        )
        if not r:
            raise JsonErrors.HTTPNotFound(message='Ticket not found')
        booking_type, price, charge_id = r
        if m.refund_amount is not None:
            if booking_type != ActionTypes.buy_tickets:
                raise JsonErrors.HTTPBadRequest(message='Refund not possible unless ticket was bought through stripe.')
            if m.refund_amount > price:
                raise JsonErrors.HTTPBadRequest(message=f'Refund amount must not exceed {price:0.2f}.')

        async with self.conn.transaction():
            action_id = await record_action_id(self.request, self.session['user_id'], ActionTypes.cancel_booked_tickets)
            await self.conn.execute(
                "update tickets set status='cancelled', cancel_action=$1 where id=$2", action_id, ticket_id
            )
            await self.conn.execute('SELECT check_tickets_remaining($1, $2)', event_id, self.settings.ticket_ttl)
            if m.refund_amount is not None:
                await stripe_refund(
                    refund_charge_id=charge_id,
                    ticket_id=ticket_id,
                    amount=int(m.refund_amount * 100),
                    user_id=self.session['user_id'],
                    company_id=self.request['company_id'],
                    app=self.app,
                    conn=self.conn,
                )
        await self.app['email_actor'].send_tickets_available(event_id)


@is_admin_or_host
async def event_tickets_export(request):
    event_id = await _check_event_permissions(request)
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


@is_admin_or_host
async def event_donations_export(request):
    event_id = await _check_event_permissions(request)
    not_admin = request['session']['role'] != 'admin'
    event_slug = await request['conn'].fetchval('SELECT slug FROM events WHERE id=$1', event_id)
    settings = request.app['settings']

    def modify(record):
        data = {
            'donation_id': ticket_id_signed(record['id'], settings),
            **record,
        }
        data.pop('id')
        data.pop('ticket_type_id')
        if not_admin:
            data.pop('user_id')
            data.pop('user_email')
        return data

    return await export_plumbing(
        request,
        event_donations_sql,
        event_id,
        filename=f'{event_slug}-donations',
        none_message='no donations booked',
        modify_records=modify,
    )


event_ticket_types_sql = """
SELECT json_build_object('ticket_types', ticket_types)
FROM (
  SELECT array_to_json(array_agg(row_to_json(t))) AS ticket_types FROM (
    SELECT tt.id, tt.name, tt.price, tt.slots_used, tt.active, COUNT(t.id) > 0 AS has_tickets, tt.mode, tt.custom_amount
    FROM ticket_types AS tt
    LEFT JOIN tickets AS t ON tt.id = t.ticket_type
    WHERE tt.event=$1
    GROUP BY tt.custom_amount, tt.id
    ORDER BY tt.id
  ) AS t
) AS ticket_types
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
    event_id = await _check_event_permissions(request)
    json_str = await request['conn'].fetchval(event_ticket_types_sql, event_id)
    return raw_json_response(json_str)


@is_admin_or_host
async def event_updates_sent(request):
    event_id = await _check_event_permissions(request)
    json_str = await request['conn'].fetchval(event_updates_sent_sql, event_id)
    return raw_json_response(json_str)


class TicketTypeMode(Enum):
    ticket = 'ticket'
    donation = 'donation'


class SetTicketTypes(UpdateView):
    class Model(BaseModel):
        class TicketType(BaseModel):
            name: str
            id: int = None
            slots_used: conint(ge=1)
            mode: TicketTypeMode = TicketTypeMode.ticket
            active: bool
            price: condecimal(ge=1, max_digits=6, decimal_places=2) = None

            @validator('active', pre=True)
            def none_bool(cls, v):
                return v or False

            def dict(self, *args, **kwargs):
                d = super().dict(*args, **kwargs)
                mode = d.get('mode')
                if mode is not None:
                    d['mode'] = mode.value
                return d

        ticket_types: List[TicketType]

        @validator('ticket_types', whole=True)
        def check_ticket_types(cls, v):
            if sum(tt.active for tt in v) < 1:
                raise ValueError('at least 1 ticket type must be active')
            return v

    async def check_permissions(self):
        await check_session(self.request, 'admin', 'host')

    async def execute(self, m: Model):
        event_id = await _check_event_permissions(self.request, check_upcoming=True)
        existing = [tt for tt in m.ticket_types if tt.id]
        mode = m.ticket_types[0].mode

        if not all(tt.mode == mode for tt in m.ticket_types):
            raise JsonErrors.HTTPBadRequest(message='all ticket types must have the same mode')

        existing_ids = [tt.id for tt in existing]
        deleted_with_tickets = await self.conn.fetchval(
            """
            SELECT 1
            FROM ticket_types AS tt
            JOIN tickets AS t ON tt.id = t.ticket_type
            WHERE tt.event=$1 AND mode=$2 AND NOT (tt.id=ANY($3))
            GROUP BY tt.id
            """,
            event_id,
            mode.value,
            existing_ids,
        )
        if deleted_with_tickets:
            raise JsonErrors.HTTPBadRequest(message='ticket types deleted which have ticket associated with them')

        changed_type = await self.conn.fetchval(
            'select 1 from ticket_types tt where tt.event=$1 and mode!=$2 and tt.id=ANY($3)',
            event_id,
            mode.value,
            existing_ids,
        )
        if changed_type:
            raise JsonErrors.HTTPBadRequest(message='ticket type modes should not change')

        async with self.conn.transaction():
            await self.conn.fetchval(
                """
                DELETE FROM ticket_types
                WHERE ticket_types.event=$1
                      AND ticket_types.mode=$2
                      AND NOT ticket_types.custom_amount
                      AND NOT (ticket_types.id=ANY($3))
                """,
                event_id,
                mode.value,
                [tt.id for tt in existing],
            )

            for tt in existing:
                v = await self.conn.execute_b(
                    'UPDATE ticket_types SET :values WHERE id=:id AND event=:event AND NOT ticket_types.custom_amount',
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
                    values=MultipleValues(*(Values(event=event_id, **tt.dict(exclude={'id'})) for tt in new)),
                )
            await record_action(
                self.request,
                self.request['session']['user_id'],
                ActionTypes.edit_event,
                event_id=event_id,
                subtype='edit-ticket-types',
            )


get_image_sql = """
SELECT e.host, e.image
FROM events as e
JOIN categories AS cat ON e.category = cat.id
JOIN companies co ON cat.company = co.id
WHERE co.id=$1 AND e.id=$2
"""


async def _delete_existing_image(request):
    event_id = await _check_event_permissions(request, check_upcoming=True)
    image = await request['conn'].fetchval('SELECT image from events WHERE id=$1', event_id)
    # delete the image from S3 if it's set and isn't a category image option
    if image and '/option/' not in image:
        await delete_image(image, request.app['settings'])


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

    image_url = await upload_background(content, upload_path, request.app['settings'])
    await request['conn'].execute('UPDATE events SET image=$1 WHERE id=$2', image_url, event_id)
    await record_action(
        request, request['session']['user_id'], ActionTypes.edit_event, event_id=event_id, subtype='set-image-new'
    )
    return json_response(status='success')


@is_admin_or_host
async def set_event_image_existing(request):
    m = await parse_request(request, ImageModel)
    if not m.image.startswith(request.app['settings'].s3_domain):
        raise JsonErrors.HTTPBadRequest(message='image not allowed')

    await _delete_existing_image(request)

    event_id = int(request.match_info['id'])
    await request['conn'].execute('UPDATE events SET image=$1 WHERE id=$2', m.image, event_id)
    await record_action(
        request, request['session']['user_id'], ActionTypes.edit_event, event_id=event_id, subtype='set-image-existing'
    )
    return json_response(status='success')


secondary_image_size = 300, 300


@is_admin_or_host
async def set_event_secondary_image(request):
    event_id = await _check_event_permissions(request, check_upcoming=True)
    content = await request_image(request, expected_size=secondary_image_size)

    image = await request['conn'].fetchval('SELECT secondary_image from events WHERE id=$1', event_id)
    if image:
        await delete_image(image, request.app['settings'])

    co_slug, cat_slug, event_slug = await request['conn'].fetchrow(slugs_sql, request['company_id'], event_id)
    upload_path = Path(co_slug) / cat_slug / event_slug / 'secondary'

    image_url = await upload_force_shape(
        content, upload_path=upload_path, settings=request.app['settings'], req_size=secondary_image_size,
    )
    async with request['conn'].transaction():
        await request['conn'].execute('UPDATE events SET secondary_image=$1 WHERE id=$2', image_url, event_id)
        await record_action(
            request,
            request['session']['user_id'],
            ActionTypes.edit_event,
            event_id=event_id,
            subtype='set-image-secondary',
        )
    return json_response(status='success')


@is_admin_or_host
async def remove_event_secondary_image(request):
    event_id = await _check_event_permissions(request, check_upcoming=True)

    image = await request['conn'].fetchval('select secondary_image from events where id=$1', event_id)
    if image:
        await delete_image(image, request.app['settings'])

    async with request['conn'].transaction():
        await request['conn'].execute('update events set secondary_image=null where id=$1', event_id)
        await record_action(
            request,
            request['session']['user_id'],
            ActionTypes.edit_event,
            event_id=event_id,
            subtype='remove-image-secondary',
        )
    return json_response(status='success')


description_image_size = 300, 300


@is_admin_or_host
async def set_event_description_image(request):
    event_id = await _check_event_permissions(request, check_upcoming=True)
    content = await request_image(request, expected_size=description_image_size)

    image = await request['conn'].fetchval('SELECT description_image from events WHERE id=$1', event_id)
    if image:
        await delete_image(image, request.app['settings'])

    co_slug, cat_slug, event_slug = await request['conn'].fetchrow(slugs_sql, request['company_id'], event_id)
    upload_path = Path(co_slug) / cat_slug / event_slug / 'description'

    image_url = await upload_other(
        content, upload_path=upload_path, settings=request.app['settings'], req_size=description_image_size, thumb=True,
    )
    async with request['conn'].transaction():
        await request['conn'].execute('UPDATE events SET description_image=$1 WHERE id=$2', image_url, event_id)
        await record_action(
            request,
            request['session']['user_id'],
            ActionTypes.edit_event,
            event_id=event_id,
            subtype='set-image-description',
        )
    return json_response(status='success')


@is_admin_or_host
async def remove_event_description_image(request):
    event_id = await _check_event_permissions(request, check_upcoming=True)

    image = await request['conn'].fetchval('select description_image from events where id=$1', event_id)
    if image:
        await delete_image(image, request.app['settings'])

    async with request['conn'].transaction():
        await request['conn'].execute('update events set description_image=null where id=$1', event_id)
        await record_action(
            request,
            request['session']['user_id'],
            ActionTypes.edit_event,
            event_id=event_id,
            subtype='remove-image-description',
        )
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
        await _check_event_permissions(self.request, check_upcoming=True)
        user_status = await self.conn.fetchrow('SELECT status FROM users WHERE id=$1', self.session['user_id'])
        if self.session['role'] != 'admin' and user_status != 'active':
            raise JsonErrors.HTTPForbidden(message='Host not active')

    async def execute(self, m: Model):
        event_id = int(self.request.match_info['id'])
        await self.conn.execute_b(
            'UPDATE events SET status=:status WHERE id=:id', status=m.status.value, id=event_id,
        )
        await record_action(
            self.request,
            self.request['session']['user_id'],
            ActionTypes.edit_event,
            event_id=event_id,
            subtype='change-status',
        )


class EventUpdate(UpdateView):
    class Model(BaseModel):
        subject: constr(max_length=200)
        message: str

    async def check_permissions(self):
        await check_session(self.request, 'admin', 'host')

    async def execute(self, m: Model):
        event_id = await _check_event_permissions(self.request, check_upcoming=True)
        action_id = await record_action_id(
            self.request,
            self.session['user_id'],
            ActionTypes.event_update,
            event_id=event_id,
            **m.dict(include={'subject', 'message'}),
        )
        await self.app['email_actor'].send_event_update(action_id)


@is_admin
async def switch_highlight(request):
    event_id = await _check_event_permissions(request)
    await request['conn'].execute('UPDATE events SET highlight=NOT highlight WHERE id=$1', event_id)
    await record_action(
        request, request['session']['user_id'], ActionTypes.edit_event, event_id=event_id, subtype='switch-highlight'
    )
    return json_response(status='ok')


search_sql = """
SELECT json_build_object(
  'items', coalesce(array_to_json(array_agg(json_strip_nulls(row_to_json(t)))), '[]')
) FROM (
  SELECT e.id, e.name, c.name category, e.status, e.highlight, e.start_ts, extract(epoch from e.duration) duration
  FROM search s
  JOIN events e ON s.event = e.id
  JOIN categories c on e.category = c.id
  WHERE s.company=:company AND s.vector @@ to_tsquery(:query)
  ORDER BY s.active_ts DESC
  LIMIT 30
) t
"""


@is_admin
async def event_search(request):
    query = prepare_search_query(request)
    if query is None:
        return raw_json_response('{"items": []}')

    json_str = await request['conn'].fetchval_b(search_sql, company=request['company_id'], query=query)
    return raw_json_response(json_str)


class EventClone(UpdateView):
    class Model(BaseModel):
        name: constr(max_length=150)
        date: DateModel
        status: StatusChoices

    async def check_permissions(self):
        await check_session(self.request, 'admin')

    clone_event_sql = """
    INSERT INTO events (
      category, host, name, slug, status,
      highlight, external_ticket_url, external_donation_url,
      start_ts, timezone, duration,
      youtube_video_id, short_description, long_description,
      description_image, description_intro,
      public, location_name, location_lat, location_lng,
      ticket_limit, image, secondary_image
    )
    SELECT
      e.category, e.host, :name, :slug, :status,
      e.highlight, e.external_ticket_url, e.external_donation_url,
      :start, e.timezone, :duration,
      e.youtube_video_id, e.short_description, e.long_description,
      e.description_image, e.description_intro,
      e.public, e.location_name, e.location_lat, e.location_lng,
      e.ticket_limit, e.image, e.secondary_image
    FROM events e WHERE e.id=:old_event_id
    ON CONFLICT (category, slug) DO NOTHING
    RETURNING id
    """
    duplicate_ticket_types_sql = """
    INSERT INTO ticket_types (event, name, price, slots_used, active, mode, custom_amount)
    SELECT $2, name, price, slots_used, active, mode, custom_amount FROM ticket_types where event=$1
    """

    async def execute(self, m: Model):
        old_event_id = int(self.request.match_info['id'])
        slug = slugify(m.name)

        tz = await self.conn.fetchval(
            """
            SELECT timezone FROM events e
            JOIN categories c ON e.category = c.id
            WHERE e.id=$1 AND c.company=$2
            """,
            old_event_id,
            self.request['company_id'],
        )
        if not tz:
            raise JsonErrors.HTTPNotFound(message='Event not found')

        start, duration = prepare_event_start(m.date.dt, m.date.dur, pytz.timezone(tz))
        kwargs = dict(
            slug=slug, old_event_id=old_event_id, name=m.name, start=start, duration=duration, status=m.status.value
        )

        async with self.conn.transaction():
            new_event_id = await self.conn.fetchval_b(self.clone_event_sql, **kwargs)
            while new_event_id is None:
                # event with this slug already exists
                kwargs['slug'] = slug + '-' + pseudo_random_str(4)
                new_event_id = await self.conn.fetchval_b(self.clone_event_sql, **kwargs)

            await self.conn.execute(self.duplicate_ticket_types_sql, old_event_id, new_event_id)

        return {'id': new_event_id, 'status_': 201}


def prepare_event_start(dt: datetime, duration: Optional[int], tz: TzInfo) -> Tuple[datetime, Optional[timedelta]]:
    dt: datetime = tz.localize(dt.replace(tzinfo=None))
    if duration:
        return dt, timedelta(seconds=duration)
    else:
        return datetime(dt.year, dt.month, dt.day), None
