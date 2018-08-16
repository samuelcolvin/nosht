from enum import Enum

from buildpg import Func, V
from buildpg.clauses import Where
from pydantic import BaseModel, EmailStr

from web.actions import ActionTypes, record_action
from web.auth import check_session, is_admin, is_admin_or_host
from web.bread import Bread
from web.utils import JsonErrors, get_offset, json_response, raw_json_response


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
        allow_marketing: bool = False

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
        'status',
        'email',
        'active_ts',
    )
    retrieve_fields = browse_fields + (
        'status',
        'phone_number',
        'created_ts',
        'active_ts',
        'receive_emails',
        'allow_marketing',
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

    async def prepare_edit_data(self, data):
        role_type = data.pop('role_type', None)
        if role_type:
            data['role'] = role_type
        return data

    async def add_execute(self, **data):
        pk = await super().add_execute(**data)
        await self.app['email_actor'].send_account_created(pk, created_by_admin=True)
        return pk


class UserSelfBread(Bread):
    class Model(BaseModel):
        first_name: str = None
        last_name: str = None
        email: EmailStr
        phone_number: str = None
        receive_emails: bool = None
        allow_marketing: bool = None

    retrieve_enabled = True
    edit_enabled = True

    model = Model
    table = 'users'
    browse_order_by_fields = V('active_ts').desc(),
    retrieve_fields = (
        Func('full_name', V('first_name'), V('last_name'), V('email')).as_('name'),
        'email',
        V('role').as_('role_type'),
        'status',
        'phone_number',
        'created_ts',
        'receive_emails',
        'allow_marketing',
        'first_name',
        'last_name',
    )

    async def check_permissions(self, method):
        await check_session(self.request, 'host', 'admin')
        if int(self.request.match_info['pk']) != self.request['session']['user_id']:
            raise JsonErrors.HTTPForbidden(message='wrong user')

    async def edit_execute(self, pk, **data):
        await super().edit_execute(pk, **data)
        await record_action(self.request, self.request['session']['user_id'], ActionTypes.edit_profile, changes=data)


user_actions_sql = """
SELECT json_build_object('actions', tickets)
FROM (
  SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') AS tickets FROM (
    SELECT id, ts, type, extra
    FROM actions
    WHERE user_id=$1 AND company=$2
    ORDER BY ts DESC
    LIMIT 100
    OFFSET $3
  ) AS t
) AS tickets
"""


@is_admin_or_host
async def user_actions(request):
    json_str = await request['conn'].fetchval(
        user_actions_sql,
        int(request.match_info['pk']),
        request['company_id'],
        get_offset(request),
    )
    return raw_json_response(json_str)


user_tickets_sql = """
SELECT json_build_object('tickets', tickets)
FROM (
  SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') AS tickets FROM (
    SELECT e.name AS event_name, t.extra_info, t.price, e.start_ts AS event_start,
      full_name(u.first_name, u.last_name, u.email) AS guest_name,
      full_name(ub.first_name, ub.last_name, u.email) AS buyer_name
    FROM tickets AS t
    LEFT JOIN users u ON t.user_id = u.id
    JOIN actions a ON t.booked_action = a.id
    JOIN users ub ON a.user_id = ub.id
    JOIN events AS e ON t.event = e.id
    WHERE t.status='booked' AND (t.user_id=$1 OR ub.id=$1)
    ORDER BY a.ts DESC
  ) AS t
) AS tickets
"""


@is_admin_or_host
async def user_tickets(request):
    user_id = int(request.match_info['pk'])
    if request['session']['role'] != 'admin' and user_id != request['session']['user_id']:
        raise JsonErrors.HTTPForbidden(message='wrong user')

    json_str = await request['conn'].fetchval(user_tickets_sql, user_id)
    return raw_json_response(json_str)


@is_admin
async def switch_user_status(request):
    user_id = int(request.match_info['pk'])
    status = await request['conn'].fetchval(
        'SELECT status FROM users WHERE id=$1 AND company=$2',
        user_id,
        request['company_id'],
    )
    if not status:
        raise JsonErrors.HTTPNotFound(message='user not found')
    new_status = 'suspended' if status == 'active' else 'active'
    await request['conn'].execute('UPDATE users SET status=$1 WHERE id=$2', new_status, user_id)
    return json_response(new_status=new_status)
