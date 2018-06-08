from buildpg import V, funcs
from buildpg.clauses import Join, Where
from pydantic import BaseModel, EmailStr

from web.bread import Bread


class CategoryBread(Bread):
    class Model(BaseModel):
        name: str
        live: bool
        description: str
        sort_index: int
        event_content: str
        host_advice: str

    model = Model
    table = 'categories'
    browse_order_by_fields = 'sort_index',

    browse_fields = (
        'id',
        'name',
        'slug',
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


class EventBread(Bread):
    class Model(BaseModel):
        category: int
        name: str

    model = Model
    table = 'events'
    pk_field = 'e.id'

    browse_fields = (
        'e.id',
        V('c.name').as_('category'),
        'e.name',
        'e.slug',
        'e.highlight',
        'e.start_ts',
        funcs.extract(V('epoch').from_(V('e.duration'))).cast('int').as_('duration'),
    )
    retrieve_fields = browse_fields

    def join(self):
        return Join(V('categories').as_('c').on(V('c.id') == V('e.category')))

    def where(self):
        return Where(V('c.company') == self.request['company_id'])


class UserBread(Bread):
    class Model(BaseModel):
        role: str  # TODO enum
        status: str
        first_name: str
        last_name: str
        email: EmailStr

    model = Model
    table = 'users'
    browse_order_by_fields = V('active_ts').desc(),

    def where(self):
        return Where(V('company') == self.request['company_id'])
