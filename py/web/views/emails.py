from buildpg import V, Values
from buildpg.clauses import Where
from pydantic import BaseModel, constr

from shared.emails.defaults import EMAIL_DEFAULTS, Triggers
from web.auth import check_session, is_admin
from web.bread import Bread
from web.utils import JsonErrors, json_response, parse_request


class EmailDefBread(Bread):
    class Model(BaseModel):
        trigger: Triggers
        subject: constr(max_length=255)
        title: constr(max_length=127)
        body: str
        active: bool = True

    browse_enabled = True
    retrieve_enabled = True
    add_enabled = True
    edit_enabled = True
    delete_enabled = True

    model = Model
    table = 'email_definitions'
    browse_order_by_fields = 'trigger',

    browse_fields = (
        'trigger',
        'active',
    )
    retrieve_fields = browse_fields + (
        'subject',
        'title',
        'body',
    )

    browse_sql = ':items_query'

    def get_pk(self):
        return self.request.match_info['trigger']

    async def check_permissions(self, method):
        await check_session(self.request, 'admin')

    def where(self):
        return Where(V('company') == self.request['company_id'])

    async def prepare_add_data(self, data):
        data['company'] = self.request['company_id']
        return data


@is_admin
async def email_def_browse(request):
    results = await request['conn'].fetch(
        'SELECT trigger, active FROM email_definitions WHERE company=$1',
        request['company_id']
    )
    lookup = {r['trigger']: r for r in results}
    return json_response(items=[
        {
            'trigger': t,
            'customised': t in lookup,
            'active': lookup[t]['active'] if t in lookup else True,
        }
        for t in Triggers
    ])


def get_trigger(request):
    trigger = request.match_info['trigger']
    try:
        Triggers(trigger)
    except ValueError:
        raise JsonErrors.HTTPNotFound(message=f'trigger "{trigger}" not found')
    return trigger


@is_admin
async def email_def_retrieve(request):
    trigger = get_trigger(request)
    email_def = await request['conn'].fetchrow(
        'SELECT active, subject, title, body FROM email_definitions WHERE trigger=$1 and company=$2',
        trigger,
        request['company_id'],
    )
    if email_def:
        data = {
            'trigger': trigger,
            'customised': True,
            'active': email_def['active'],
            'subject': email_def['subject'],
            'title': email_def['title'],
            'body': email_def['body'],
        }
    else:
        defaults = EMAIL_DEFAULTS[Triggers(trigger)]
        data = {
            'trigger': trigger,
            'customised': False,
            'active': True,
            'subject': defaults['subject'],
            'title': defaults['title'],
            'body': defaults['body'].strip('\n '),
        }
    return json_response(**data)


class EmailDefModel(BaseModel):
    subject: constr(max_length=255)
    title: constr(max_length=127) = None
    body: str
    active: bool


@is_admin
async def email_def_edit(request):
    m = await parse_request(request, EmailDefModel)
    trigger = get_trigger(request)
    await request['conn'].execute_b(
        """
        INSERT INTO email_definitions AS ed (:values__names) VALUES :values
        ON CONFLICT (company, trigger) DO UPDATE SET
          subject=EXCLUDED.subject,
          title=EXCLUDED.title,
          body=EXCLUDED.body,
          active=EXCLUDED.active
        """,
        values=Values(
            trigger=trigger,
            company=request['company_id'],
            **m.dict()
        )
    )
    return json_response(status='ok')


@is_admin
async def clear_email_def(request):
    trigger = get_trigger(request)
    r = await request['conn'].execute(
        'DELETE FROM email_definitions WHERE trigger=$1 AND company=$2',
        trigger,
        request['company_id'],
    )
    if r == 'DELETE 1':
        return json_response(status='ok')
    else:
        raise JsonErrors.HTTPNotFound(message=f'email definition with trigger "{trigger}" not found')
