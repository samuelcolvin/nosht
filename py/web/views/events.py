from datetime import datetime

from buildpg import V, funcs
from buildpg.asyncpg import BuildPgConnection
from buildpg.clauses import Join, Where
from pydantic import BaseModel, constr

from web.auth import check_session, is_admin_or_host
from web.bread import Bread
from web.utils import raw_json_response

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

        class DateModel(BaseModel):
            dt: datetime
            ad: bool

        date: DateModel = None

        class LocationModel(BaseModel):
            lat: float
            lng: float
            name: constr(max_length=63)

        location: LocationModel
        ticket_limit: int = None
        description: str

    browse_enabled = True
    retrieve_enabled = True
    add_enabled = True
    edit_enabled = True

    model = Model
    table = 'events'
    pk_field = 'e.id'

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
