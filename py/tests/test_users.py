import pytest
from pytest_toolbox.comparison import CloseToNow, RegexStr

from .conftest import Factory


async def test_user_list(cli, url, login, factory: Factory):
    await factory.create_company()
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
                'active_ts': CloseToNow(),
            },
        ],
        'count': 1,
    }


async def test_user_details(cli, url, login, factory: Factory):
    await factory.create_company()
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
        'active_ts': CloseToNow(),
        'status': 'active',
        'phone_number': None,
        'created_ts': CloseToNow(),
        'receive_emails': True,
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
        'tickets': [
            {
                'id': await db_conn.fetchval('SELECT id FROM actions'),
                'ts': CloseToNow(),
                'type': 'login',
                'extra': {
                    'ip': '127.0.0.1',
                    'ua': RegexStr('Python.*'),
                    'url': RegexStr('http://127.0.0.1:\d+/api/auth-token/'),
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
    assert data == {
        'status': 'ok',
        'pk': await db_conn.fetchval("SELECT id FROM users WHERE first_name='foo'")
    }
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
            'grecaptcha',
            '__ok__',
        ),
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
    r = await cli.json_put(url('user-edit', pk=factory.user_id), data={'first_name': 'foo'})
    assert r.status == 200, await r.text()
    assert 'foo' == await db_conn.fetchval('SELECT first_name FROM users')


async def test_duplicate_email(cli, url, login, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_user()
    await login()
    data = {
        'first_name': 'foo',
        'email': 'frank@example.org',
        'role_type': 'admin',
    }
    r = await cli.json_post(url('user-add'), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'Invalid Data',
        'details': [
            {
                'loc': ['email'],
                'msg': 'email address already used.',
                'type': 'value_error.conflict',
            },
        ],
    }
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')


@pytest.mark.parametrize('before,after', [
    ('pending', 'active'),
    ('active', 'suspended'),
    ('suspended', 'active'),
])
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
