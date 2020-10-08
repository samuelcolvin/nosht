import pytest
from buildpg import MultipleValues, Values
from pytest_toolbox.comparison import CloseToNow, RegexStr

from shared.utils import mk_password

from .conftest import Factory


async def test_user_list(cli, url, login, factory: Factory):
    await factory.create_company(display_timezone='utc')
    await factory.create_user()
    await login()

    r = await cli.get(url('user-browse'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'items': [
            {
                'id': factory.user_id,
                'name': 'Frank Spencer',
                'role_type': 'admin',
                'status': 'active',
                'email': 'frank@example.org',
                'active_ts': CloseToNow(delta=3),
            },
        ],
        'count': 1,
        'pages': 1,
    }


async def test_user_details(cli, url, login, factory: Factory):
    await factory.create_company(display_timezone='utc')
    await factory.create_user()
    await login()

    r = await cli.get(url('user-retrieve', pk=factory.user_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'id': factory.user_id,
        'name': 'Frank Spencer',
        'role_type': 'admin',
        'email': 'frank@example.org',
        'active_ts': CloseToNow(delta=3),
        'status': 'active',
        'phone_number': None,
        'created_ts': CloseToNow(delta=3),
        'receive_emails': True,
        'allow_marketing': False,
        'first_name': 'Frank',
        'last_name': 'Spencer',
    }


async def test_user_actions(cli, url, login, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_user()
    await login()

    r = await cli.get(url('user-actions', pk=factory.user_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'actions': [
            {
                'id': await db_conn.fetchval('SELECT id FROM actions'),
                'ts': CloseToNow(delta=3),
                'type': 'login',
                'extra': {
                    'ip': '127.0.0.1',
                    'ua': RegexStr(r'Python.*'),
                    'url': RegexStr(r'http://127.0.0.1:\d+/api/auth-token/'),
                },
            },
        ],
    }


async def test_create_user(cli, url, login, factory: Factory, db_conn, dummy_server):
    await factory.create_company()
    await factory.create_user()
    await login()
    data = {
        'first_name': 'foo',
        'email': 'foobar@example.org',
        'role_type': 'admin',
    }
    r = await cli.json_post(url('user-add'), data=data)
    assert r.status == 201, await r.text()
    data = await r.json()
    assert data == {'status': 'ok', 'pk': await db_conn.fetchval("SELECT id FROM users WHERE first_name='foo'")}
    user = await db_conn.fetchrow(
        """
        SELECT company, role, status, first_name, last_name, email
        FROM users WHERE first_name='foo'
        """
    )
    assert dict(user) == {
        'company': factory.company_id,
        'role': 'admin',
        'status': 'pending',
        'first_name': 'foo',
        'last_name': None,
        'email': 'foobar@example.org',
    }
    assert dummy_server.app['log'] == [
        (
            'email_send_endpoint',
            'Subject: "Testing Account Created (Action required)", To: "foo <foobar@example.org>"',
        ),
    ]

    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    assert email['part:text/plain'].startswith(
        'Hi foo,\n'
        '\n'
        'An account has been created for you with Testing.\n'
        '\n'
        "You've been created as an administrator.\n"
        '\n'
        'You need to confirm your email address before you can administer the system.\n'
        '\n'
        '<div class="button">\n'
        '  <a href="https://127.0.0.1/set-password/?sig='
    )


async def test_edit_user(cli, url, login, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_user()
    await login()
    r = await cli.json_post(url('user-edit', pk=factory.user_id), data={'first_name': 'foo'})
    assert r.status == 200, await r.text()
    assert 'foo' == await db_conn.fetchval('SELECT first_name FROM users')


async def test_add_user_wrong_role_type(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_user()
    await login()
    data = {
        'first_name': 'foo',
        'email': 'foobar@example.org',
        'role_type': 'guest',
    }
    r = await cli.json_post(url('user-add'), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'role must be either "host" or "admin".'}


async def test_edit_user_role(cli, url, login, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_user()
    await login()
    r = await cli.json_post(url('user-edit', pk=factory.user_id), data={'role_type': 'guest'})
    assert r.status == 200, await r.text()
    assert 'guest' == await db_conn.fetchval('SELECT role FROM users')


async def test_duplicate_email(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_user()
    await login()
    data = {
        'first_name': 'foo',
        'email': 'frank@example.org',
        'role_type': 'admin',
    }
    r = await cli.json_post(url('user-add'), data=data)
    assert r.status == 409, await r.text()
    data = await r.json()
    assert data == {
        'message': 'Conflict',
        'details': [
            {
                'loc': ['email'],
                'msg': 'This value conflicts with an existing "email", try something else.',
                'type': 'value_error.conflict',
            },
        ],
    }


@pytest.mark.parametrize('before,after', [('pending', 'active'), ('active', 'suspended'), ('suspended', 'active')])
async def test_switch_status(before, after, cli, url, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_user()
    await login()

    user_id = await factory.create_user(email='test@example.com', status=before)
    assert before == await db_conn.fetchval('SELECT status FROM users WHERE id=$1', user_id)

    r = await cli.json_post(url('user-switch-status', pk=user_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {'new_status': after}
    assert after == await db_conn.fetchval('SELECT status FROM users WHERE id=$1', user_id)


async def test_switch_status_not_found(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await login()

    r = await cli.json_post(url('user-switch-status', pk=999))
    assert r.status == 404, await r.text()


async def test_account_view(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_user()
    await login()

    r = await cli.get(url('account-retrieve', pk=factory.user_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'name': 'Frank Spencer',
        'email': 'frank@example.org',
        'role_type': 'admin',
        'status': 'active',
        'phone_number': None,
        'created_ts': CloseToNow(delta=3),
        'receive_emails': True,
        'allow_marketing': False,
        'first_name': 'Frank',
        'last_name': 'Spencer',
    }


async def test_account_edit(cli, url, login, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_user()
    await login()

    r = await cli.json_post(url('account-edit', pk=factory.user_id), data={'first_name': 'xxx'})
    assert r.status == 200, await r.text()
    assert 'xxx' == await db_conn.fetchval('SELECT first_name FROM users')


async def test_account_view_wrong_user(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_user()
    await login()
    user_id2 = await factory.create_user(email='different@example.org')

    r = await cli.get(url('account-retrieve', pk=user_id2))
    assert r.status == 403, await r.text()


async def test_account_edit_wrong_user(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_user()
    await login()
    user_id2 = await factory.create_user(email='different@example.org')

    r = await cli.json_post(url('account-edit', pk=user_id2), data={'first_name': 'xxx'})
    assert r.status == 403, await r.text()


async def test_user_tickets(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=123)
    await login()

    r = await cli.get(url('user-tickets', pk=factory.user_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {'tickets': []}

    res = await factory.create_reservation(factory.user_id)
    await factory.buy_tickets(res)

    r = await cli.get(url('user-tickets', pk=factory.user_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'tickets': [
            {
                'event_name': 'The Event Name',
                'extra_info': None,
                'price': 123.0,
                'event_start': '2032-06-28T19:00:00',
                'guest_name': 'Frank Spencer',
                'buyer_name': 'Frank Spencer',
            },
        ],
    }


async def test_user_tickets_wrong_user(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await factory.create_event(price=123)
    await login()

    user_id2 = await factory.create_user(email='different@example.org')

    r = await cli.get(url('user-tickets', pk=user_id2))
    assert r.status == 403, await r.text()


async def test_pagination(cli, url, login, factory: Factory, db_conn, settings):
    await factory.create_company()

    pw = mk_password('testing', settings)
    await db_conn.execute_b(
        'INSERT INTO users (:values__names) VALUES :values RETURNING id',
        values=MultipleValues(
            *(
                Values(
                    company=factory.company_id,
                    password_hash=pw,
                    email=f'user+{i + 1}@example.org',
                    role='admin',
                    status='active',
                )
                for i in range(120)
            )
        ),
    )
    await login('user+1@example.org')

    r = await cli.get(url('user-browse'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data['count'] == 120
    assert data['pages'] == 3
    assert len(data['items']) == 50
    assert data['items'][0]['email'] == 'user+1@example.org'

    r = await cli.get(url('user-browse', query={'page': '2'}))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data['count'] == 120
    assert data['pages'] == 3
    assert len(data['items']) == 50
    assert data['items'][0]['email'] == 'user+51@example.org'

    r = await cli.get(url('user-browse', query={'page': '3'}))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data['count'] == 120
    assert data['pages'] == 3
    assert len(data['items']) == 20
    assert data['items'][0]['email'] == 'user+101@example.org'
