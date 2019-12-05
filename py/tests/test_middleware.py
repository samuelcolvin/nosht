import pytest
from aiohttp import web
from aiohttp_session import new_session, session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from shared.db import SimplePgPool
from web.middleware import error_middleware, exc_extra

from .conftest import Factory


async def handle_user(request):
    session = await new_session(request)
    async with request.app['main_app']['pg'].acquire() as conn:
        session.update({'user_id': await conn.fetchval('SELECT id FROM users')})
    return web.Response(status=488)


async def handle_errors(request):
    do = request.match_info['do']
    if do == '500':
        raise web.HTTPInternalServerError(text='custom 500 error')
    elif do == 'value_error':
        raise ValueError('snap')
    elif do == 'return_499':
        return web.Response(text='499 response', status=499)
    return web.Response(text='ok')


async def pre_startup_app(app):
    app['main_app'] = {'pg': SimplePgPool(app['test_conn'])}


@pytest.fixture(name='cli')
async def _fix_cli(settings, db_conn, aiohttp_client, redis):
    app = web.Application(
        middlewares=(
            session_middleware(EncryptedCookieStorage(settings.auth_key, cookie_name='testing')),
            error_middleware,
        )
    )
    app.add_routes([web.get('/user', handle_user), web.get('/{do}', handle_errors)])

    app.update(test_conn=db_conn, settings=settings)
    app.on_startup.append(pre_startup_app)
    cli = await aiohttp_client(app)

    return cli


async def test_200(cli, caplog):
    r = await cli.get('/whatever')
    assert r.status == 200, await r.text()
    assert len(caplog.records) == 0


async def test_404_no_path(cli, caplog):
    r = await cli.get('/foo/bar/')
    assert r.status == 404, await r.text()
    assert len(caplog.records) == 0


async def test_500(cli, caplog):
    r = await cli.get('/500', data='foobar')
    assert r.status == 500, await r.text()
    assert 'custom 500 error' == await r.text()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.data.keys() == {'request_duration', 'request', 'response'}
    assert record.data['request']['text'] == 'foobar'
    assert record.data['response']['text'] == 'custom 500 error'
    assert record.user == {'ip_address': '127.0.0.1'}
    assert record.tags == {}


async def test_not_unicode(cli, caplog):
    r = await cli.get('/500', data=b'\xff')
    assert r.status == 500, await r.text()
    assert 'custom 500 error' == await r.text()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.data.keys() == {'request_duration', 'request', 'response'}
    assert record.data['request']['text'] is None
    assert record.user == {'ip_address': '127.0.0.1'}
    assert record.tags == {}


async def test_499(cli, caplog):
    r = await cli.get('/return_499')
    assert r.status == 499, await r.text()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.data.keys() == {'request_duration', 'request', 'response'}
    assert record.user == {'ip_address': '127.0.0.1'}
    assert record.tags == {}


async def test_value_error(cli, caplog):
    r = await cli.get('/value_error')
    assert r.status == 500, await r.text()
    assert '500: Internal Server Error' == await r.text()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.data.keys() == {'request_duration', 'request', 'response', 'exception_extra'}
    assert record.data['exception_extra'] is None
    assert record.user == {'ip_address': '127.0.0.1'}
    assert record.tags == {}


async def test_user(cli, caplog, db_conn, fire_stripe_webhook):
    factory = Factory(db_conn, cli.app, fire_stripe_webhook)
    await factory.create_company()
    await factory.create_user()

    r = await cli.get('/user')
    assert r.status == 488, await r.text()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.data.keys() == {'request_duration', 'request', 'response'}
    assert record.user == {
        'ip_address': '127.0.0.1',
        'email': 'frank@example.org',
        'company_name': 'Testing',
        'company_id': factory.company_id,
        'role': 'admin',
        'status': 'active',
        'username': 'Frank Spencer',
    }
    assert record.tags == {
        'user_status': 'active',
        'user_role': 'admin',
        'company': factory.company_id,
    }


def test_exc_extra_ok():
    class Foo(Exception):
        def extra(self):
            return {'x': 1}

    assert exc_extra(Foo()) == {'x': 1}


def test_exc_extra_error():
    class Foo(Exception):
        def extra(self):
            raise RuntimeError()

    assert exc_extra(Foo()) is None
