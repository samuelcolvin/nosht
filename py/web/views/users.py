from buildpg import V
from buildpg.clauses import RawDangerous, Where
from pydantic import BaseModel, EmailStr

from web.auth import check_session
from web.bread import Bread


class UserBread(Bread):
    class Model(BaseModel):
        status: str
        first_name: str
        last_name: str
        role: str  # TODO enum
        email: EmailStr

    browse_enabled = True
    retrieve_enabled = True

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

    async def check_permissions(self, method):
        await check_session(self.request, 'admin')

    def where(self):
        return Where(V('company') == self.request['company_id'])
