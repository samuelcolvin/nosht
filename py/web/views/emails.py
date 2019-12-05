import chevron
from buildpg import Values
from chevron import ChevronError
from pydantic import BaseModel, constr, validator

from shared.emails.defaults import EMAIL_DEFAULTS, Triggers
from web.auth import is_admin
from web.utils import JsonErrors, json_response, parse_request


@is_admin
async def email_def_browse(request):
    results = await request['conn'].fetch(
        'SELECT trigger, active FROM email_definitions WHERE company=$1', request['company_id']
    )
    lookup = {r['trigger']: r for r in results}
    return json_response(
        items=[
            {'trigger': t, 'customised': t in lookup, 'active': lookup[t]['active'] if t in lookup else True}
            for t in Triggers
        ]
    )


def get_trigger(request):
    trigger = request.match_info['trigger']
    try:
        return Triggers(trigger)
    except ValueError:
        raise JsonErrors.HTTPNotFound(message='no such trigger')


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

    @validator('body', 'title')
    def check_mustache(cls, v):
        try:
            chevron.render(v, data={})
        except (ChevronError, IndexError):
            raise ValueError('invalid mustache template')
        return v

    @validator('active', pre=True)
    def none_bool(cls, v):
        return v or False


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
        values=Values(trigger=trigger, company=request['company_id'], **m.dict()),
    )
    return json_response(status='ok')


@is_admin
async def clear_email_def(request):
    trigger = get_trigger(request)
    r = await request['conn'].execute(
        'DELETE FROM email_definitions WHERE trigger=$1 AND company=$2', trigger, request['company_id'],
    )
    if r == 'DELETE 1':
        return json_response(status='ok')
    else:
        raise JsonErrors.HTTPNotFound(message=f'email definition with trigger "{trigger}" not found')
