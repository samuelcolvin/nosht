from buildpg import V, funcs
from buildpg.clauses import Join, RawDangerous, Where
from pydantic import BaseModel, EmailStr

from shared.utils import slugify
from web.bread import Bread
from web.utils import JsonErrors

from .auth import check_session


class NoshtBread(Bread):
    async def check_permissions(self, method):
        await check_session(self.request, 'admin')
        user_role = self.request['session'].get('user_role')
        if user_role is None:
            raise JsonErrors.HTTPUnauthorized(message='Authentication required to view this page')
        elif user_role != 'admin':
            raise JsonErrors.HTTPForbidden(message='permission denied')


class CategoryBread(NoshtBread):
    class Model(BaseModel):
        name: str
        live: bool = True
        description: str = None
        sort_index: int = 1
        event_content: str = None
        host_advice: str = None

    model = Model
    table = 'categories'
    browse_order_by_fields = 'sort_index',

    browse_fields = (
        'id',
        'name',
        'live',
        'description',
    )
    retrieve_fields = browse_fields + (
        'sort_index',
        'event_content',
        'host_advice',
    )

    def where(self):
        return Where(V('company') == self.request['company_id'])

    def add_modify_data(self, data):
        data.update(
            company=self.request['company_id'],
            slug=slugify(data['name'])
        )
        return data


class EventBread(NoshtBread):
    class Model(BaseModel):
        category: int
        name: str

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

    def join(self):
        return Join(V('categories').as_('c').on(V('c.id') == V('e.category')))

    def where(self):
        return Where(V('c.company') == self.request['company_id'])


class UserBread(NoshtBread):
    class Model(BaseModel):
        status: str
        first_name: str
        last_name: str
        role: str  # TODO enum
        email: EmailStr

    model = Model
    table = 'users'
    browse_order_by_fields = V('active_ts').desc(),
    browse_fields = (
        'id',
        V('first_name').cat(RawDangerous("' '")).cat(V('last_name')).as_('name'),
        V('role').as_('role_type'),
        'email'
    )
    retrieve_fields = browse_fields + (
        'phone_number',
        'created_ts',
        'active_ts',
    )

    def where(self):
        return Where(V('company') == self.request['company_id'])
