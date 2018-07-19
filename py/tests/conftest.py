import asyncio
import base64
import hashlib
import hmac
import json
import random
import uuid
from datetime import datetime
from functools import partial
from pprint import pformat
from textwrap import shorten

import lorem
import pytest
from aiohttp.test_utils import teardown_test_loop
from aioredis import create_redis
from buildpg import Values, asyncpg

from shared.db import create_demo_data as _create_demo_data
from shared.db import prepare_database
from shared.settings import Settings
from shared.utils import mk_password, slugify
from web.main import create_app
from web.stripe import Reservation

from .dummy_server import create_dummy_server


def pytest_addoption(parser):
    parser.addoption(
        '--reuse-db', action='store_true', default=False, help='keep the existing database if it exists'
    )


settings_args = dict(
    DATABASE_URL='postgres://postgres:waffle@localhost:5432/nosht_testing',
    REDISCLOUD_URL='redis://localhost:6379/6',
    bcrypt_work_factor=6,
    stripe_idempotency_extra=str(uuid.uuid4()),
    aws_access_key='testing_access_key',
    aws_secret_key='testing_secret_key',
    ticket_ttl=15,
    facebook_siw_app_secret='testing',
    print_emails=False,
)


@pytest.fixture(scope='session', name='settings_session')
def _fix_settings_session():
    return Settings(**settings_args)


@pytest.fixture(scope='session', name='clean_db')
def _fix_clean_db(request, settings_session):
    # loop fixture has function scope so can't be used here.
    loop = asyncio.new_event_loop()
    loop.run_until_complete(prepare_database(settings_session, not request.config.getoption('--reuse-db')))
    teardown_test_loop(loop)


@pytest.fixture(name='dummy_server')
async def _fix_dummy_server(loop, aiohttp_server):
    return await create_dummy_server(loop, aiohttp_server)


replaced_url_fields = (
    'aws_ses_endpoint',
    'grecaptcha_url',
    'google_siw_url',
    'facebook_siw_url',
    'stripe_root_url',
)


@pytest.fixture(name='settings')
def _fix_settings(dummy_server, request):
    # alter stripe_root_url if the real_stripe_test decorator is applied
    real_stripe = any('REAL_STRIPE_TESTS' in m.kwargs.get('reason', '') for m in request.keywords.get('pytestmark', []))
    fields = set(replaced_url_fields)
    if real_stripe:
        fields.remove('stripe_root_url')
    server_name = dummy_server.app['server_name']
    return Settings(
        **{f: f'{server_name}/{f}/' for f in fields},
        **settings_args
    )


@pytest.fixture(name='db_conn')
async def _fix_db_conn(loop, settings, clean_db):
    conn = await asyncpg.connect_b(dsn=settings.pg_dsn, loop=loop)

    tr = conn.transaction()
    await tr.start()

    yield conn

    await tr.rollback()
    await conn.close()


class FakePgPool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return self

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def close(self):
        pass


@pytest.fixture
def db_pool(db_conn):
    return FakePgPool(db_conn)


@pytest.fixture
async def create_demo_data(db_conn, settings):
    await _create_demo_data(db_conn, settings, company_host='127.0.0.1')


class Factory:
    def __init__(self, conn, settings):
        self.conn = conn
        self.settings = settings
        self.company_id = None
        self.category_id = None
        self.user_id = None
        self.event_id = None

    async def create_company(self,
                             name='Testing',
                             slug=None,
                             image='https://www.example.com/co.png',
                             domain='127.0.0.1',
                             stripe_public_key='stripe_key_xxx',
                             stripe_secret_key='stripe_secret_xxx',
                             **kwargs):
        company_id = await self.conn.fetchval_b(
            'INSERT INTO companies (:values__names) VALUES :values RETURNING id',
            values=Values(
                name=name,
                slug=slug or slugify(name),
                image=image,
                domain=domain,
                stripe_public_key=stripe_public_key,
                stripe_secret_key=stripe_secret_key,
                **kwargs,
            )
        )
        self.company_id = self.company_id or company_id
        return company_id

    async def create_user(self, *,
                          company_id=None,
                          password='testing',
                          first_name='Frank',
                          last_name='Spencer',
                          email='frank@example.com',
                          role='admin',
                          status='active',
                          **kwargs):
        user_id = await self.conn.fetchval_b(
            'INSERT INTO users (:values__names) VALUES :values RETURNING id',
            values=Values(
                company=company_id or self.company_id,
                password_hash=mk_password(password, self.settings),
                first_name=first_name,
                last_name=last_name,
                email=email,
                role=role,
                status=status,
                **kwargs,
            )
        )
        self.user_id = self.user_id or user_id
        return user_id

    async def create_cat(self, *,
                         company_id=None,
                         name='Supper Clubs',
                         slug=None,
                         image='https://www.example.com/co.png',
                         **kwargs):
        cat_id = await self.conn.fetchval_b(
            'INSERT INTO categories (:values__names) VALUES :values RETURNING id',
            values=Values(
                company=company_id or self.company_id,
                name=name,
                image=image,
                slug=slug or slugify(name),
                **kwargs
            )
        )
        self.category_id = self.category_id or cat_id
        return cat_id

    async def create_event(self, *,
                           category_id=None,
                           host_user_id=None,
                           name='The Event Name',
                           slug=None,
                           start_ts=datetime(2020, 1, 28, 19, 0),
                           short_description=None,
                           long_description=None,
                           **kwargs):
        long_description = long_description or lorem.paragraph()
        event_id = await self.conn.fetchval_b(
            'INSERT INTO events (:values__names) VALUES :values RETURNING id',
            values=Values(
                category=category_id or self.category_id,
                host=host_user_id or self.user_id,
                name=name,
                slug=slug or slugify(name),
                long_description=long_description,
                start_ts=start_ts,
                short_description=(
                    short_description or
                    shorten(long_description, width=random.randint(100, 140), placeholder='...')
                ),
                **kwargs
            )
        )
        self.event_id = self.event_id or event_id
        return event_id

    async def create_reservation(self):
        action_id = await self.conn.fetchval_b(
            'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
            values=Values(
                company=self.company_id,
                user_id=self.user_id,
                type='reserve-tickets'
            )
        )
        await self.conn.execute_b(
            'INSERT INTO tickets (:values__names) VALUES :values',
            values=Values(
                event=self.event_id,
                user_id=self.user_id,
                reserve_action=action_id,
            )
        )
        await self.conn.execute('SELECT check_tickets_remaining($1, $2)', self.event_id, self.settings.ticket_ttl)
        return Reservation(
            user_id=self.user_id,
            action_id=action_id,
            event_id=self.event_id,
            price_cent=10_00,
            ticket_count=1,
            event_name='Foobar',
        )


@pytest.fixture
async def factory(db_conn, settings):
    return Factory(db_conn, settings)


@pytest.fixture
def login(cli, url):
    async def f(email='frank@example.com', password='testing'):
        data = dict(email=email, password=password, grecaptcha_token='__ok__')
        r = await cli.json_post(url('login'), data=data)
        assert r.status == 200, await r.text()
        data = await r.json()
        r = await cli.json_post(url('auth-token'), data={'token': data['auth_token']})
        assert r.status == 200, await r.text()
        assert len(cli.session.cookie_jar) == 1

    return f


@pytest.yield_fixture
async def redis(loop, settings: Settings):
    addr = settings.redis_settings.host, settings.redis_settings.port
    redis = await create_redis(addr, db=settings.redis_settings.database, loop=loop)
    await redis.flushdb()

    yield redis

    redis.close()
    await redis.wait_closed()


async def pre_startup_app(app):
    app['main_app']['pg'] = FakePgPool(app['test_conn'])


async def post_startup_app(app):
    inner_app = app['main_app']
    inner_app['email_actor'].pg = inner_app['pg']
    inner_app['email_actor']._concurrency_enabled = False


@pytest.fixture(name='cli')
async def _fix_cli(settings, db_conn, aiohttp_client, redis):
    app = create_app(settings=settings)
    app['test_conn'] = db_conn
    app.on_startup.insert(0, pre_startup_app)
    app.on_startup.append(post_startup_app)
    cli = await aiohttp_client(app)

    def json_data_request(method, url, *, data=None, headers=None):
        if data and not isinstance(data, str):
            data = json.dumps(data)
        headers = {
            'Content-Type': 'application/json',
            # 'Origin': 'http://{'
            **(headers or {}),
        }
        return cli.request(method, url, data=data, headers=headers)

    cli.json_post = partial(json_data_request, 'POST')
    cli.json_put = partial(json_data_request, 'PUT')
    return cli


@pytest.fixture(name='url')
def _fix_url(cli):
    def f(name, *, query=None, **kwargs):
        inner_app = cli.server.app['main_app']
        try:
            r = inner_app.router[name]
        except KeyError as e:
            raise KeyError(f'invalid url name, choices: {pformat(inner_app.router._named_resources)}') from e
        url = r.url_for(**{k: str(v) for k, v in kwargs.items()})
        if query:
            url = url.with_query(**query)
        return url
    return f


@pytest.fixture(name='signed_fb_request')
def _fix_signed_fb_request(settings):
    def f(data):
        raw_data = base64.urlsafe_b64encode(json.dumps(data, separators=(',', ':')).encode())[:-1]
        sig_raw = hmac.new(settings.facebook_siw_app_secret, raw_data, hashlib.sha256).digest()
        sig = base64.urlsafe_b64encode(sig_raw).decode()
        return sig[:-1] + '.' + raw_data.decode()

    return f
