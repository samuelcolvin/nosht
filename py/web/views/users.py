from enum import Enum

from buildpg import Func, V
from buildpg.clauses import Where
from pydantic import BaseModel, EmailStr

from web.auth import check_session, is_admin
from web.bread import Bread
from web.utils import JsonErrors, get_offset, raw_json_response


class UserRoles(str, Enum):
    guest = 'guest'
    host = 'host'
    admin = 'admin'


class UserBread(Bread):
    class Model(BaseModel):
        first_name: str = None
        last_name: str = None
        email: EmailStr
        role_type: UserRoles
        phone_number: str = None
        receive_emails: bool = True

    browse_enabled = True
    retrieve_enabled = True
    edit_enabled = True
    add_enabled = True

    model = Model
    table = 'users'
    browse_order_by_fields = V('active_ts').desc(),
    browse_fields = (
        'id',
        Func('full_name', V('first_name'), V('last_name'), V('email')).as_('name'),
        V('role').as_('role_type'),
        'email',
        'active_ts',
    )
    retrieve_fields = browse_fields + (
        'status',
        'phone_number',
        'created_ts',
        'active_ts',
        'receive_emails',
        'first_name',
        'last_name',
    )

    async def check_permissions(self, method):
        await check_session(self.request, 'admin')

    def where(self):
        return Where(V('company') == self.request['company_id'])

    async def prepare_add_data(self, data):
        role_type = data.pop('role_type')
        if role_type not in {UserRoles.host, UserRoles.admin}:
            raise JsonErrors.HTTPBadRequest(message='role must be either "host" or "admin".')
        data.update(
            role=role_type,
            company=self.request['company_id']
        )
        return data

    add_sql = """
    INSERT INTO :table (:values__names) VALUES :values
    ON CONFLICT (company, email) DO NOTHING
    RETURNING :pk_field
    """

    async def add_execute(self, **data):
        pk = await super().add_execute(**data)
        while pk is None:
            raise JsonErrors.HTTPBadRequest(
                message='Invalid Data',
                details=[
                    {
                        'loc': ['email'],
                        'msg': 'email address already used.',
                        'type': 'value_error.conflict',
                    }
                ]
            )
        else:
            await self.app['email_actor'].send_account_created(pk, created_by_admin=True)
            return pk


@is_admin
async def user_actions(request):
    json_str = await request['conn'].fetchval(
        """
        SELECT json_build_object('tickets', tickets)
        FROM (
          SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') AS tickets FROM (
            SELECT id, ts, type, extra
            FROM actions
            WHERE user_id=$1 AND company=$2
            LIMIT 100
            OFFSET $3
          ) AS t
        ) AS tickets
        """,
        int(request.match_info['pk']),
        request['company_id'],
        get_offset(request),
    )
    return raw_json_response(json_str)


# TODO allow admins to suspend users.
