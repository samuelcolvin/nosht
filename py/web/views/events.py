from datetime import datetime, timedelta
from enum import Enum
from textwrap import shorten
from typing import Optional

from buildpg import V, funcs
from buildpg.asyncpg import BuildPgConnection
from buildpg.clauses import Join, Where
from pydantic import BaseModel, EmailStr, constr

from shared.utils import slugify
from web.auth import check_session, is_admin_or_host
from web.bread import Bread, UpdateView
from web.utils import JsonErrors, parse_request, raw_json_response

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
    # print_queries = True

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


class EmailModel(BaseModel):
    email: EmailStr


async def _validate_email(email):
    SMTP(hostname='aspmx.l.google.com.', port=25, loop=request.app.loop)


async def check_email(request):
    m = await parse_request(request, EmailModel)
    SMTP(hostname='aspmx.l.google.com.', port=25, loop=request.app.loop)
    response_data = response_data or {}
    response_data.setdefault('status', 'ok')
    return json_response(**response_data)
