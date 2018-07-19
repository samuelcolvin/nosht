import base64
import hashlib
import hmac
import json
import re

import pytest
from cryptography import fernet
from pytest_toolbox.comparison import AnyInt, RegexStr

from web.utils import encrypt_json
from .conftest import Factory


async def test_login_successful(cli, url, factory: Factory):
    await factory.create_company()
    await factory.create_user()

    r = await cli.get(url('event-categories'))
    assert r.status == 401, await r.text()

    assert len(cli.session.cookie_jar) == 0

    data = dict(
        email='frank@example.com',
        password='testing',
        grecaptcha_token='__ok__',
    )
    r = await cli.post(url('login'), data=json.dumps(data))
    assert r.status == 200, await r.text()
    data = await r.json()
    r = await cli.post(url('auth-token'), data=json.dumps({'token': data['auth_token']}))
    assert r.status == 200, await r.text()

    assert len(cli.session.cookie_jar) == 1

    r = await cli.get(url('event-categories'))
    assert r.status == 200, await r.text()


async def test_host_signup_email(cli, url, factory: Factory, db_conn, dummy_server, settings):
    await factory.create_company()
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    data = {
        'email': 'testing@GMAIL.com',
        'name': 'Jane Doe',
        'grecaptcha_token': '__ok__',
    }
    r = await cli.post(url('signup-host', site='email'), data=json.dumps(data))
    assert r.status == 200, await r.text()
    response_data = await r.json()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    user = await db_conn.fetchrow('SELECT id, company, first_name, last_name, email, role, status FROM users')

    assert response_data == {
        'user': {
            'id': user['id'],
            'first_name': 'Jane',
            'last_name': 'Doe',
            'email': 'testing@gmail.com',
            'role': 'host',
        },
    }
    assert dict(user) == {
        'id': AnyInt(),
        'company': factory.company_id,
        'first_name': 'Jane',
        'last_name': 'Doe',
        'email': 'testing@gmail.com',
        'role': 'host',
        'status': 'pending',
    }
    assert dummy_server.app['log'] == [
        ('grecaptcha', '__ok__'),
        (
            'email_send_endpoint',
            'Subject: "Testing Account Created (Action required)", To: "Jane Doe <testing@gmail.com>"',
        ),
    ]
    email = dummy_server.app['emails'][0]['part:text/plain']
    assert 'Confirm Email' in email
    assert 'Create &amp; Publish Events' not in email
    token = re.search('/set-password/\?sig=([^"]+)', email).group(1)
    token_data = json.loads(fernet.Fernet(settings.auth_key).decrypt(token.encode()).decode())
    assert token_data == user['id']


async def test_host_signup_google(cli, url, factory: Factory, db_conn, mocker, dummy_server):
    await factory.create_company()
    data = {
        'id_token': 'good.test.token',
        'grecaptcha_token': '__ok__',
    }
    mock_jwt_decode = mocker.patch('web.auth.google_jwt.decode', return_value={
        'iss': 'accounts.google.com',
        'email_verified': True,
        'email': 'google-auth@EXAMPLE.com',
        'given_name': 'Foo',
        'family_name': 'Bar',
    })
    r = await cli.post(url('signup-host', site='google'), data=json.dumps(data))
    assert r.status == 200, await r.text()
    response_data = await r.json()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    user_id, user_company, status = await db_conn.fetchrow('SELECT id, company, status FROM users')

    assert response_data == {
        'user': {
            'id': user_id,
            'first_name': 'Foo',
            'last_name': 'Bar',
            'email': 'google-auth@example.com',
            'role': 'host',
        },
    }
    assert user_company == factory.company_id
    assert status == 'active'
    mock_jwt_decode.assert_called_once()

    assert dummy_server.app['log'] == [
        ('grecaptcha', '__ok__'),
        ('google_siw', None),
        (
            'email_send_endpoint',
            'Subject: "Testing Account Created", To: "Foo Bar <google-auth@example.com>"',
        ),
    ]
    email = dummy_server.app['emails'][0]['part:text/plain']
    assert 'Create &amp; Publish Events' in email
    assert 'Confirm Email' not in email


@pytest.fixture(name='signed_fb_request')
def _fix_signed_fb_request(settings):
    def f(data):
        raw_data = base64.urlsafe_b64encode(json.dumps(data, separators=(',', ':')).encode())[:-1]
        sig_raw = hmac.new(settings.facebook_siw_app_secret, raw_data, hashlib.sha256).digest()
        sig = base64.urlsafe_b64encode(sig_raw).decode()
        return sig[:-1] + '.' + raw_data.decode()

    return f


async def test_host_signup_facebook(cli, url, factory: Factory, db_conn, signed_fb_request):
    await factory.create_company()
    data = {
        'signedRequest': signed_fb_request({'user_id': '123456'}),
        'accessToken': '__ok__',
        'userID': 123456,
        'grecaptcha_token': '__ok__',
    }
    r = await cli.post(url('signup-host', site='facebook'), data=json.dumps(data))
    assert r.status == 200, await r.text()
    response_data = await r.json()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    user_id, user_company = await db_conn.fetchrow('SELECT id, company FROM users')

    assert response_data == {
        'user': {
            'id': user_id,
            'first_name': None,
            'last_name': 'Book',
            'email': 'facebook-auth@example.com',
            'role': 'host',
        },
    }
    assert user_company == factory.company_id


async def test_host_signup_grecaptcha_invalid(cli, url, factory: Factory, db_conn):
    await factory.create_company()
    data = {
        'email': 'testing@gmail.com',
        'name': 'Jane Doe',
        'grecaptcha_token': '__low_score__',
    }
    r = await cli.post(url('signup-host', site='email'), data=json.dumps(data))
    assert r.status == 400, await r.text()
    response_data = await r.json()
    assert response_data == {
        'message': 'Invalid recaptcha value',
    }
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM users')


async def test_guest_signup_email(cli, url, factory: Factory, db_conn):
    await factory.create_company()
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    data = {
        'email': 'testing@gmail.com',
        'grecaptcha_token': '__ok__',
    }
    r = await cli.post(url('signup-guest', site='email'), data=json.dumps(data))
    assert r.status == 200, await r.text()
    response_data = await r.json()
    assert response_data == {
        'user': {
            'id': await db_conn.fetchval('SELECT id FROM users'),
            'first_name': None,
            'last_name': None,
            'email': 'testing@gmail.com',
            'role': 'guest',
        },
    }
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    user = dict(await db_conn.fetchrow('SELECT first_name, last_name, email, role, status, company FROM users'))
    assert user == {
        'first_name': None,
        'last_name': None,
        'email': 'testing@gmail.com',
        'role': 'guest',
        'status': 'pending',
        'company': factory.company_id,
    }


async def test_guest_signup_google(cli, url, factory: Factory, db_conn, mocker):
    await factory.create_company()
    data = {
        'id_token': 'good.test.token',
        'grecaptcha_token': '__ok__',
    }
    mock_jwt_decode = mocker.patch('web.auth.google_jwt.decode', return_value={
        'iss': 'accounts.google.com',
        'email_verified': True,
        'email': 'google-auth@EXAMPLE.com',
        'given_name': 'Foo',
        'family_name': 'Bar',
    })
    r = await cli.post(url('signup-guest', site='google'), data=json.dumps(data))
    assert r.status == 200, await r.text()
    response_data = await r.json()
    assert response_data == {
        'user': {
            'id': await db_conn.fetchval('SELECT id FROM users'),
            'first_name': 'Foo',
            'last_name': 'Bar',
            'email': 'google-auth@example.com',
            'role': 'guest',
        },
    }
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    user = dict(await db_conn.fetchrow('SELECT first_name, last_name, email, role, status, company FROM users'))
    assert user == {
        'first_name': 'Foo',
        'last_name': 'Bar',
        'email': 'google-auth@example.com',
        'role': 'guest',
        'status': 'active',
        'company': factory.company_id,
    }
    mock_jwt_decode.assert_called_once()


async def test_set_password(cli, url, factory: Factory, db_conn, login):
    await factory.create_company()
    await factory.create_user()

    pw_before = await db_conn.fetchval('SELECT password_hash FROM users WHERE id=$1', factory.user_id)

    with pytest.raises(AssertionError):
        await login(password='testing-new-password')

    data = {
        'password1': 'testing-new-password',
        'password2': 'testing-new-password',
        'token': encrypt_json(cli.app['main_app'], factory.user_id),
    }
    r = await cli.post(url('set-password'), data=json.dumps(data))
    assert r.status == 200, await r.text()
    pw_after = await db_conn.fetchval('SELECT password_hash FROM users WHERE id=$1', factory.user_id)
    assert pw_after != pw_before
    await login(password='testing-new-password')


async def test_set_password_reuse_token(cli, url, factory: Factory):
    await factory.create_company()
    await factory.create_user()

    data = {
        'password1': 'testing-new-password',
        'password2': 'testing-new-password',
        'token': encrypt_json(cli.app['main_app'], factory.user_id),
    }
    r = await cli.post(url('set-password'), data=json.dumps(data))
    assert r.status == 200, await r.text()

    r = await cli.post(url('set-password'), data=json.dumps(data))
    assert r.status == 470, await r.text()
    data = await r.json()
    assert data == {
        'message': 'This password reset link has already been used.',
    }


async def test_set_password_mismatch(cli, url, factory: Factory):
    await factory.create_company()
    await factory.create_user()

    data = {
        'password1': 'testing-new-password',
        'password2': 'testing-new-password2',
        'token': encrypt_json(cli.app['main_app'], factory.user_id),
    }
    r = await cli.post(url('set-password'), data=json.dumps(data))
    assert r.status == 400, await r.text()

    data = await r.json()
    assert data == {
        'message': 'Invalid Data',
        'details': [
            {
                'loc': [
                    'password2',
                ],
                'msg': 'passwords do not match',
                'type': 'value_error',
            },
        ],
    }
