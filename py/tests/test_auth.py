import json
import re
from time import time

import pytest
from cryptography import fernet
from pytest_toolbox.comparison import AnyInt, RegexStr

from web.utils import encrypt_json

from .conftest import Factory, if_online


async def test_login_successful(cli, url, factory: Factory):
    await factory.create_company()
    await factory.create_user()

    r = await cli.get(url('event-categories'))
    assert r.status == 401, await r.text()

    assert len(cli.session.cookie_jar) == 0

    data = dict(email='frank@example.org', password='testing')
    r = await cli.json_post(url('login'), data=data, origin_null=True)
    assert r.status == 200, await r.text()
    data = await r.json()
    r = await cli.json_post(url('auth-token'), data={'token': data['auth_token']})
    assert r.status == 200, await r.text()

    assert len(cli.session.cookie_jar) == 1

    r = await cli.get(url('event-categories'))
    assert r.status == 200, await r.text()


async def test_login_invalid_token(cli, url, factory: Factory):
    await factory.create_company()
    await factory.create_user()

    r = await cli.json_post(url('auth-token'), data={'token': 'foobar'})
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'invalid token',
    }


async def test_login_not_json(cli, url, factory: Factory):
    await factory.create_company()
    await factory.create_user()

    r = await cli.json_post(url('auth-token'), data='xxx')
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'Error decoding JSON',
        'details': None,
    }


@pytest.mark.parametrize(
    'post_data',
    [
        dict(email='not-frank@example.org', password='testing', grecaptcha_token='__ok__'),
        dict(email='frank@example.org', password='testing1', grecaptcha_token='__ok__'),
        dict(email='not-frank@example.org', password='testing1', grecaptcha_token='__ok__'),
        dict(email='frank@example.org', password='_dummy_password_', grecaptcha_token='__ok__'),
    ],
)
async def test_login_unsuccessful(post_data, cli, url, factory: Factory):
    await factory.create_company()
    await factory.create_user()

    assert len(cli.session.cookie_jar) == 0

    r = await cli.json_post(url('login'), data=post_data, origin_null=True)
    assert r.status == 470, await r.text()
    data = await r.json()
    assert data == {
        'status': 'invalid',
        'message': 'invalid email or password',
    }

    assert len(cli.session.cookie_jar) == 0
    r = await cli.get(url('event-categories'))
    assert r.status == 401, await r.text()


async def test_login_with(cli, url, factory: Factory, signed_fb_request):
    await factory.create_company()
    await factory.create_user(email='facebook-auth@example.org')

    data = {
        'signedRequest': signed_fb_request({'user_id': '123456'}),
        'accessToken': '__ok__',
        'userID': 123456,
    }

    r = await cli.json_post(url('login-google-facebook', site='facebook'), data=data)
    assert r.status == 200, await r.text()
    data = await r.json()
    r = await cli.json_post(url('auth-token'), data={'token': data['auth_token']})
    assert r.status == 200, await r.text()

    assert len(cli.session.cookie_jar) == 1

    r = await cli.get(url('event-categories'))
    assert r.status == 200, await r.text()


async def test_login_with_missing(cli, url, factory: Factory, signed_fb_request):
    await factory.create_company()
    await factory.create_user()

    data = {
        'signedRequest': signed_fb_request({'user_id': '123456'}),
        'accessToken': '__ok__',
        'userID': 123456,
    }
    r = await cli.json_post(url('login-google-facebook', site='facebook'), data=data)
    assert r.status == 470, await r.text()
    data = await r.json()
    assert data == {
        'status': 'invalid',
        'message': 'User with email address "facebook-auth@example.org" not found',
    }

    assert len(cli.session.cookie_jar) == 0
    r = await cli.get(url('event-categories'))
    assert r.status == 401, await r.text()


async def test_facebook_bad_request(cli, url, factory: Factory):
    await factory.create_company()
    await factory.create_user(email='facebook-auth@example.org')

    data = {
        'signedRequest': 'xxx',
        'accessToken': '__ok__',
        'userID': 123456,
    }

    r = await cli.json_post(url('login-google-facebook', site='facebook'), data=data)
    assert r.status == 400, await r.text()
    assert {'message': '"signedRequest" not correctly formed'} == await r.json()


async def test_facebook_bad_signature(cli, url, factory: Factory):
    await factory.create_company()
    await factory.create_user(email='facebook-auth@example.org')

    data = {
        'signedRequest': 'xxx.yyy',
        'accessToken': '__ok__',
        'userID': 123456,
    }

    r = await cli.json_post(url('login-google-facebook', site='facebook'), data=data)
    assert r.status == 400, await r.text()
    assert {'message': '"signedRequest" not correctly signed'} == await r.json()


async def test_facebook_bad_fb_response(cli, url, factory: Factory, signed_fb_request):
    await factory.create_company()
    await factory.create_user(email='facebook-auth@example.org')

    data = {
        'signedRequest': signed_fb_request({'user_id': '123456'}),
        'accessToken': '__400__',
        'userID': 123456,
    }

    r = await cli.json_post(url('login-google-facebook', site='facebook'), data=data)
    assert r.status == 500, await r.text()


async def test_facebook_wrong_user(cli, url, factory: Factory, signed_fb_request):
    await factory.create_company()
    await factory.create_user(email='facebook-auth@example.org')

    data = {
        'signedRequest': signed_fb_request({'user_id': '123456'}),
        'accessToken': '__ok__',
        'userID': 666,
    }

    r = await cli.json_post(url('login-google-facebook', site='facebook'), data=data)
    assert r.status == 400, await r.text()
    assert {'message': 'facebook userID not consistent'} == await r.json()


async def test_facebook_no_name(cli, url, factory: Factory, signed_fb_request):
    await factory.create_company()
    await factory.create_user(email='facebook-auth@example.org')

    data = {
        'signedRequest': signed_fb_request({'user_id': '123456'}),
        'accessToken': '__no_user__',
        'userID': 123456,
    }

    r = await cli.json_post(url('login-google-facebook', site='facebook'), data=data)
    assert r.status == 400, await r.text()
    assert {
        'message': 'Your Facebook profile needs to have both a last name and email address associated with it.'
    } == await r.json()


async def test_logout(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await login()

    r = await cli.get(url('event-categories'))
    assert r.status == 200, await r.text()

    r = await cli.json_post(url('logout'))
    assert r.status == 200, await r.text()

    r = await cli.get(url('event-categories'))
    assert r.status == 401, await r.text()


@if_online
async def test_host_signup_email(cli, url, factory: Factory, db_conn, dummy_server, settings):
    await factory.create_company()
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    data = {
        'email': 'testing@GMAIL.com',
        'name': 'Jane Doe',
        'grecaptcha_token': '__ok__',
    }
    r = await cli.json_post(url('signup-host', site='email'), data=data)
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
    token = re.search(r'/set-password/\?sig=([^"]+)', email).group(1)
    token_data = json.loads(fernet.Fernet(settings.auth_key).decrypt(token.encode()).decode())
    assert token_data == user['id']


async def test_host_signup_google(cli, url, factory: Factory, db_conn, mocker, dummy_server):
    await factory.create_company()
    data = {'id_token': 'good.test.token'}
    mock_jwt_decode = mocker.patch(
        'web.auth.google_jwt.decode',
        return_value={
            'iss': 'accounts.google.com',
            'email_verified': True,
            'email': 'google-auth@EXAMPLE.org',
            'given_name': 'Foo',
            'family_name': 'Bar',
        },
    )
    r = await cli.json_post(url('signup-host', site='google'), data=data)
    assert r.status == 200, await r.text()
    response_data = await r.json()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    user_id, user_company, status = await db_conn.fetchrow('SELECT id, company, status FROM users')

    assert response_data == {
        'user': {
            'id': user_id,
            'first_name': 'Foo',
            'last_name': 'Bar',
            'email': 'google-auth@example.org',
            'role': 'host',
        },
    }
    assert user_company == factory.company_id
    assert status == 'active'
    mock_jwt_decode.assert_called_once()

    assert dummy_server.app['log'] == [
        'GET google_siw_url',
        ('email_send_endpoint', 'Subject: "Testing Account Created", To: "Foo Bar <google-auth@example.org>"'),
    ]
    email = dummy_server.app['emails'][0]['part:text/plain']
    assert 'Create &amp; Publish Events' in email
    assert 'Confirm Email' not in email


async def test_google_request_error(cli, url, factory: Factory, caplog, settings, dummy_server):
    await factory.create_company()
    data = {'id_token': 'good.test.token'}
    settings.google_siw_url = dummy_server.app['server_name'] + '/broken'
    r = await cli.json_post(url('signup-host', site='google'), data=data)
    assert r.status == 500, await r.text()
    assert dummy_server.app['log'] == [
        'GET broken',
    ]
    assert 'RequestError: response 404 from "http://localhost:' in caplog.text


async def test_google_request_bad_token(cli, url, factory: Factory):
    await factory.create_company()
    data = {'id_token': 'good.test.token'}
    r = await cli.json_post(url('signup-host', site='google'), data=data)
    assert r.status == 400, await r.text()
    assert {'message': 'google jwt decode error'} == await r.json()


async def test_host_signup_facebook(cli, url, factory: Factory, db_conn, signed_fb_request):
    await factory.create_company()
    data = {
        'signedRequest': signed_fb_request({'user_id': '123456'}),
        'accessToken': '__ok__',
        'userID': 123456,
    }
    r = await cli.json_post(url('signup-host', site='facebook'), data=data)
    assert r.status == 200, await r.text()
    response_data = await r.json()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    user_id, user_company = await db_conn.fetchrow('SELECT id, company FROM users')

    assert response_data == {
        'user': {
            'id': user_id,
            'first_name': None,
            'last_name': 'Book',
            'email': 'facebook-auth@example.org',
            'role': 'host',
        },
    }
    assert user_company == factory.company_id


async def test_host_signup_facebook_existing(cli, url, factory: Factory, db_conn, signed_fb_request):
    await factory.create_company()
    await factory.create_user(email='facebook-auth@example.org', role='guest')
    data = {
        'signedRequest': signed_fb_request({'user_id': '123456'}),
        'accessToken': '__ok__',
        'userID': 123456,
    }
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    r = await cli.json_post(url('signup-host', site='facebook'), data=data)
    assert r.status == 200, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')


async def test_host_signup_facebook_existing_admin(cli, url, factory: Factory, db_conn, signed_fb_request):
    await factory.create_company()
    await factory.create_user(email='facebook-auth@example.org')
    data = {
        'signedRequest': signed_fb_request({'user_id': '123456'}),
        'accessToken': '__ok__',
        'userID': 123456,
    }
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    r = await cli.json_post(url('signup-host', site='facebook'), data=data)
    assert r.status == 470, await r.text()
    assert {'status': 'existing user'} == await r.json()


async def test_host_signup_facebook_existing_suspended(cli, url, factory: Factory, db_conn, signed_fb_request):
    await factory.create_company()
    await factory.create_user(email='facebook-auth@example.org', role='guest', status='suspended')
    data = {
        'signedRequest': signed_fb_request({'user_id': '123456'}),
        'accessToken': '__ok__',
        'userID': 123456,
    }
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    r = await cli.json_post(url('signup-host', site='facebook'), data=data)
    assert r.status == 470, await r.text()
    assert {'status': 'user suspended'} == await r.json()


async def test_host_signup_grecaptcha_invalid(cli, url, factory: Factory, db_conn):
    await factory.create_company()
    data = {
        'email': 'testing@gmail.com',
        'name': 'Jane Doe',
        'grecaptcha_token': 'wrong',
    }
    r = await cli.json_post(url('signup-host', site='email'), data=data)
    assert r.status == 400, await r.text()
    response_data = await r.json()
    assert response_data == {
        'message': 'Invalid recaptcha value',
    }
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM users')


async def test_grecaptcha_bad_response(cli, url, factory: Factory, caplog):
    await factory.create_company()
    data = {
        'email': 'testing@gmail.com',
        'name': 'Jane Doe',
        'grecaptcha_token': '__400__',
    }
    r = await cli.json_post(url('signup-host', site='email'), data=data)
    assert r.status == 500, await r.text()
    assert 'RequestError: response 400 from "http://localhost:' in caplog.text


@if_online
async def test_guest_signup_email(cli, url, factory: Factory, db_conn):
    await factory.create_company()
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    data = {
        'email': 'testing@gmail.com',
        'first_name': 'Tes',
        'last_name': 'Ting',
        'grecaptcha_token': '__ok__',
    }
    r = await cli.json_post(url('signup-guest', site='email'), data=data)
    assert r.status == 200, await r.text()
    response_data = await r.json()
    assert response_data == {
        'user': {
            'id': await db_conn.fetchval('SELECT id FROM users'),
            'first_name': 'Tes',
            'last_name': 'Ting',
            'email': 'testing@gmail.com',
            'role': 'guest',
        },
    }
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    user = dict(await db_conn.fetchrow('SELECT first_name, last_name, email, role, status, company FROM users'))
    assert user == {
        'first_name': 'Tes',
        'last_name': 'Ting',
        'email': 'testing@gmail.com',
        'role': 'guest',
        'status': 'pending',
        'company': factory.company_id,
    }


async def test_guest_signup_google(cli, url, factory: Factory, db_conn, mocker):
    await factory.create_company()
    data = {'id_token': 'good.test.token'}
    mock_jwt_decode = mocker.patch(
        'web.auth.google_jwt.decode',
        return_value={
            'iss': 'accounts.google.com',
            'email_verified': True,
            'email': 'google-auth@example.org',
            'given_name': 'Foo',
            'family_name': 'Bar',
        },
    )
    r = await cli.json_post(url('signup-guest', site='google'), data=data)
    assert r.status == 200, await r.text()
    response_data = await r.json()
    assert response_data == {
        'user': {
            'id': await db_conn.fetchval('SELECT id FROM users'),
            'first_name': 'Foo',
            'last_name': 'Bar',
            'email': 'google-auth@example.org',
            'role': 'guest',
        },
    }
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    user = dict(await db_conn.fetchrow('SELECT first_name, last_name, email, role, status, company FROM users'))
    assert user == {
        'first_name': 'Foo',
        'last_name': 'Bar',
        'email': 'google-auth@example.org',
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
    r = await cli.json_post(url('set-password'), data=data, origin_null=True)
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'status': 'success',
        'auth_token': RegexStr(r'.+'),
        'user': {
            'id': factory.user_id,
            'first_name': 'Frank',
            'last_name': 'Spencer',
            'email': 'frank@example.org',
            'role': 'admin',
            'status': 'active',
        },
    }
    pw_after = await db_conn.fetchval('SELECT password_hash FROM users WHERE id=$1', factory.user_id)
    assert pw_after != pw_before
    await login(password='testing-new-password', captcha=True)


async def test_set_password_reuse_token(cli, url, factory: Factory):
    await factory.create_company()
    await factory.create_user()

    data = {
        'password1': 'testing-new-password',
        'password2': 'testing-new-password',
        'token': encrypt_json(cli.app['main_app'], factory.user_id),
    }
    r = await cli.json_post(url('set-password'), data=data, origin_null=True)
    assert r.status == 200, await r.text()

    r = await cli.json_post(url('set-password'), data=data, origin_null=True)
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
    r = await cli.json_post(url('set-password'), data=data, origin_null=True)
    assert r.status == 400, await r.text()

    data = await r.json()
    assert data == {
        'message': 'Invalid Data',
        'details': [{'loc': ['password2'], 'msg': 'passwords do not match', 'type': 'value_error'}],
    }


async def test_password_reset(cli, url, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_user()
    pw_before = await db_conn.fetchval('SELECT password_hash FROM users')

    data = dict(email='frank@example.org', grecaptcha_token='__ok__')
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM actions')
    r = await cli.json_post(url('reset-password-request'), data=data)
    assert r.status == 200, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM actions')

    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]

    sig = re.search(r'\?sig=(.+?)"', email['part:text/plain']).group(1)
    assert email['part:text/plain'] == (
        f'Hi Frank,\n'
        f'\n'
        f'Please use the link below to reset your password for Testing.\n'
        f'\n'
        f'<div class="button">\n'
        f'  <a href="https://127.0.0.1/set-password/?sig={sig}"><span>Reset Your Password</span></a>\n'
        f'</div>\n'
    )

    data = {
        'password1': 'testing-new-password',
        'password2': 'testing-new-password',
        'token': sig,
    }
    r = await cli.json_post(url('set-password'), data=data, origin_null=True)
    assert r.status == 200, await r.text()
    assert pw_before != await db_conn.fetchval('SELECT password_hash FROM users')


async def test_password_reset_wrong(cli, url, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_user()

    data = dict(email='foobar@example.org', grecaptcha_token='__ok__')
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM actions')
    r = await cli.json_post(url('reset-password-request'), data=data)
    assert r.status == 200, await r.text()
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM actions')

    assert len(dummy_server.app['emails']) == 0


async def test_session_expired(cli, url, factory: Factory, login, mocker):
    await factory.create_company()
    await factory.create_user()

    await login()

    r = await cli.get(url('event-categories'))
    assert r.status == 200, await r.text()

    mocker.patch('web.auth.time', return_value=int(1e10))

    r = await cli.get(url('event-categories'))
    assert r.status == 401, await r.text()


async def test_session_updated(cli, url, factory: Factory, login, mocker):
    await factory.create_company()
    await factory.create_user()

    r = await login()
    assert 'Set-Cookie' in r.headers

    r = await cli.get(url('event-categories'))
    assert r.status == 200, await r.text()
    assert 'Set-Cookie' not in r.headers

    mocker.patch('web.auth.time', return_value=time() + 700)

    r = await cli.get(url('event-categories'))
    assert r.status == 200, await r.text()
    assert 'Set-Cookie' in r.headers


async def test_login_captcha_required(cli, url, factory: Factory):
    await factory.create_company()

    r = await cli.get(url('login-captcha-required'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {'captcha_required': False}

    r = await cli.json_post(url('login'), data=dict(email='frank@example.org', password='wrong'), origin_null=True)
    assert r.status == 470, await r.text()

    r = await cli.get(url('login-captcha-required'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {'captcha_required': True}


async def test_captcha_required(cli, url, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user()

    r = await cli.json_post(url('login'), data=dict(email='frank@example.org', password='wrong'), origin_null=True)
    assert r.status == 470, await r.text()

    r = await cli.json_post(url('login'), data=dict(email='frank@example.org', password='testing'), origin_null=True)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'No recaptcha value'}
    assert dummy_server.app['log'] == []

    data = dict(email='frank@example.org', password='testing', grecaptcha_token='__ok__')
    r = await cli.json_post(url('login'), data=data, origin_null=True)
    assert r.status == 200, await r.text()
    assert dummy_server.app['log'] == [('grecaptcha', '__ok__')]
