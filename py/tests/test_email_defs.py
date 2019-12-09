from buildpg import Values
from pytest_toolbox.comparison import AnyInt, RegexStr

from shared.emails import Triggers

from .conftest import Factory


async def test_browse_email_defs(cli, url, login, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_user()

    await login()

    await db_conn.execute_b(
        'INSERT INTO email_definitions (:values__names) VALUES :values',
        values=Values(company=factory.company_id, trigger=Triggers.password_reset, subject='testing', body='xxx'),
    )

    r = await cli.get(url('email-defs-browse'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert len(data['items']) == 13
    assert sum(i['customised'] for i in data['items']) == 1
    assert next(i for i in data['items'] if i['customised']) == {
        'active': True,
        'customised': True,
        'trigger': 'password-reset',
    }
    assert sum(i['active'] for i in data['items']) == 13


async def test_retrieve_missing_email_defs(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_user()

    await login()

    r = await cli.get(url('email-defs-retrieve', trigger=Triggers.event_reminder.value))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'trigger': 'event-reminder',
        'customised': False,
        'active': True,
        'subject': '{{{ event_name }}} Upcoming',
        'title': '{{ company_name }}',
        'body': RegexStr(r'.*'),
    }


async def test_retrieve_invalid_email_defs(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_user()

    await login()

    r = await cli.get(url('email-defs-retrieve', trigger='xxx'))
    assert r.status == 404, await r.text()
    data = await r.json()
    assert data == {'message': 'no such trigger'}


async def test_retrieve_existing_email_defs(cli, url, login, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_user()

    await login()

    await db_conn.execute_b(
        'INSERT INTO email_definitions (:values__names) VALUES :values',
        values=Values(company=factory.company_id, trigger=Triggers.password_reset, subject='testing', body='xxx'),
    )

    r = await cli.get(url('email-defs-retrieve', trigger=Triggers.password_reset.value))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'trigger': 'password-reset',
        'customised': True,
        'active': True,
        'subject': 'testing',
        'title': None,
        'body': 'xxx',
    }


async def test_edit_email_defs(cli, url, login, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_user()
    await login()

    data = dict(subject='foobar', active=False, body='the body')
    r = await cli.json_post(url('email-defs-edit', trigger=Triggers.event_reminder.value), data=data)
    assert r.status == 200, await r.text()

    email_def = await db_conn.fetchrow('SELECT * FROM email_definitions')
    assert dict(email_def) == {
        'id': AnyInt(),
        'company': factory.company_id,
        'trigger': 'event-reminder',
        'active': False,
        'subject': 'foobar',
        'title': None,
        'body': 'the body',
    }


async def test_edit_email_defs_invalid(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_user()
    await login()

    data = dict(subject='foobar', active=False, body='the body {{ broken')
    r = await cli.json_post(url('email-defs-edit', trigger=Triggers.event_reminder.value), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'Invalid Data',
        'details': [{'loc': ['body'], 'msg': 'invalid mustache template', 'type': 'value_error'}],
    }


async def test_edit_update_email_defs(cli, url, login, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_user()

    await login()

    await db_conn.execute_b(
        'INSERT INTO email_definitions (:values__names) VALUES :values',
        values=Values(
            company=factory.company_id,
            trigger=Triggers.event_reminder,
            subject='testing',
            body='xxx',
            title='the title',
        ),
    )

    data = dict(subject='foobar', body='the body', active=False, title='different')
    r = await cli.json_post(url('email-defs-edit', trigger=Triggers.event_reminder.value), data=data)
    assert r.status == 200, await r.text()

    email_def = await db_conn.fetchrow('SELECT * FROM email_definitions')
    assert dict(email_def) == {
        'id': AnyInt(),
        'company': factory.company_id,
        'trigger': 'event-reminder',
        'active': False,
        'subject': 'foobar',
        'title': 'different',
        'body': 'the body',
    }


async def test_clear_email_defs(cli, url, login, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_user()

    await login()

    await db_conn.execute_b(
        'INSERT INTO email_definitions (:values__names) VALUES :values',
        values=Values(company=factory.company_id, trigger=Triggers.event_reminder, subject='testing', body='xxx'),
    )
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM email_definitions')
    r = await cli.json_post(url('email-defs-clear', trigger=Triggers.event_reminder.value))
    assert r.status == 200, await r.text()
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM email_definitions')


async def test_clear_missing_email_defs(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_user()

    await login()

    r = await cli.json_post(url('email-defs-clear', trigger=Triggers.event_reminder.value))
    assert r.status == 404, await r.text()
    data = await r.json()
    assert data == {'message': 'email definition with trigger "event-reminder" not found'}
