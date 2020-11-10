import asyncio
import base64
import hashlib
import hmac
import json
import locale
import random
import sys
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from pprint import pformat
from textwrap import shorten
from time import time

import aiodns
import lorem
import pytest
import pytz
from aiohttp.test_utils import TestClient, teardown_test_loop
from aioredis import create_redis
from async_timeout import timeout
from buildpg import MultipleValues, Values, asyncpg
from PIL import Image, ImageDraw

from shared.actions import ActionTypes
from shared.db import SimplePgPool, create_demo_data as _create_demo_data, prepare_database
from shared.settings import Settings
from shared.utils import encrypt_json, mk_password, slugify
from web.main import create_app
from web.stripe import BookFreeModel, Reservation, book_free

from .dummy_server import create_dummy_server


def pytest_addoption(parser):
    parser.addoption('--reuse-db', action='store_true', default=False, help='keep the existing database if it exists')


settings_args = dict(
    pg_dsn='postgres://postgres:waffle@localhost:5432/nosht_testing',
    redis_settings='redis://localhost:6379/6',
    bcrypt_work_factor=6,
    stripe_idempotency_extra=str(uuid.uuid4()),
    s3_bucket='testingbucket.example.org',
    s3_domain='https://testingbucket.example.org',
    aws_access_key='testing_access_key',
    aws_secret_key='testing_secret_key',
    ticket_ttl=15,
    facebook_siw_app_secret='testing',
    print_emails=False,
    s3_prefix='tests',
    max_request_size=1024 ** 2,
    donorfy_api_key=None,
    donorfy_access_key=None,
    aws_ses_webhook_auth=b'pw:tests',
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
    return await create_dummy_server(aiohttp_server)


replaced_url_fields = (
    'aws_ses_endpoint',
    'grecaptcha_url',
    'google_siw_url',
    'facebook_siw_url',
    'stripe_root_url',
    'aws_endpoint_url',
    's3_demo_image_url',
    'donorfy_api_root',
)


@pytest.fixture(name='settings')
def _fix_settings(dummy_server, request, tmpdir):
    try:
        locale.setlocale(locale.LC_ALL, 'en_GB.utf8')
    except locale.Error:
        # happens on macos
        pass
    # alter stripe_root_url if the real_stripe_test decorator is applied
    real_stripe = any('REAL_STRIPE_TESTS' in m.kwargs.get('reason', '') for m in request.keywords.get('pytestmark', []))
    fields = set(replaced_url_fields)
    if real_stripe:
        fields.remove('stripe_root_url')
    server_name = dummy_server.app['server_name']
    return Settings(custom_static_dir=str(tmpdir), **{f: f'{server_name}/{f}/' for f in fields}, **settings_args)


@pytest.fixture(name='db_conn')
async def _fix_db_conn(loop, settings, clean_db):
    conn = await asyncpg.connect_b(dsn=settings.pg_dsn, loop=loop)

    tr = conn.transaction()
    await tr.start()

    yield conn

    await tr.rollback()
    await conn.close()


@pytest.fixture
def db_pool(db_conn):
    return SimplePgPool(db_conn)


@pytest.fixture
async def create_demo_data(db_conn, settings):
    await _create_demo_data(db_conn, settings, company_host='127.0.0.1')


london = pytz.timezone('Europe/London')


class Factory:
    def __init__(self, conn, app, fire_stripe_webhook):
        self.conn = conn
        self.app = app
        self._fire_stripe_webhook = fire_stripe_webhook
        self.settings: Settings = app['settings']
        self.company_id = None
        self.category_id = None
        self.user_id = None
        self.event_id = None
        self.ticket_type_id = None
        self.donation_ticket_type_id_1 = None
        self.donation_ticket_type_id_2 = None
        self.donation_option_id = None
        self.donation_id = None

    async def create_company(
        self,
        name='Testing',
        slug=None,
        image='https://www.example.org/main.png',
        domain='127.0.0.1',
        stripe_public_key='stripe_key_xxx',
        stripe_secret_key='stripe_secret_xxx',
        stripe_webhook_secret='stripe_webhook_secret_xxx',
        **kwargs,
    ):
        company_id = await self.conn.fetchval_b(
            'INSERT INTO companies (:values__names) VALUES :values RETURNING id',
            values=Values(
                name=name,
                slug=slug or slugify(name),
                image=image,
                domain=domain,
                stripe_public_key=stripe_public_key,
                stripe_secret_key=stripe_secret_key,
                stripe_webhook_secret=stripe_webhook_secret,
                **kwargs,
            ),
        )
        self.company_id = self.company_id or company_id
        return company_id

    async def create_user(
        self,
        *,
        company_id=None,
        password='testing',
        first_name='Frank',
        last_name='Spencer',
        email='frank@example.org',
        role='admin',
        status='active',
        **kwargs,
    ):
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
            ),
        )
        self.user_id = self.user_id or user_id
        return user_id

    async def create_cat(
        self, *, company_id=None, name='Supper Clubs', slug=None, image='https://www.example.org/main.png', **kwargs
    ):
        cat_id = await self.conn.fetchval_b(
            'INSERT INTO categories (:values__names) VALUES :values RETURNING id',
            values=Values(
                company=company_id or self.company_id, name=name, image=image, slug=slug or slugify(name), **kwargs
            ),
        )
        self.category_id = self.category_id or cat_id
        return cat_id

    async def create_event(
        self,
        *,
        category_id=None,
        host_user_id=None,
        name='The Event Name',
        slug=None,
        allow_tickets=True,
        allow_donations=False,
        start_ts=london.localize(datetime(2032, 6, 28, 19, 0)),
        timezone='Europe/London',
        duration=timedelta(hours=1),
        youtube_video_id=None,
        short_description=None,
        long_description=None,
        description_intro=None,
        price=None,
        suggested_donation=10,
        **kwargs,
    ):
        long_description = long_description or lorem.paragraph()
        event_id = await self.conn.fetchval_b(
            'INSERT INTO events (:values__names) VALUES :values RETURNING id',
            values=Values(
                category=category_id or self.category_id,
                host=host_user_id or self.user_id,
                name=name,
                slug=slug or slugify(name),
                allow_tickets=allow_tickets,
                allow_donations=allow_donations,
                youtube_video_id=youtube_video_id,
                long_description=long_description,
                description_intro=description_intro or lorem.paragraph(),
                start_ts=start_ts,
                timezone=timezone,
                duration=duration,
                short_description=(
                    short_description or shorten(long_description, width=random.randint(100, 140), placeholder='...')
                ),
                **kwargs,
            ),
        )
        self.event_id = self.event_id or event_id
        ticket_type_ids = await self.conn.fetch_b(
            'INSERT INTO ticket_types (:values__names) VALUES :values RETURNING id',
            values=MultipleValues(
                Values(event=event_id, name='Standard', price=price, mode='ticket', custom_amount=False),
                Values(event=event_id, name='Standard', price=suggested_donation, mode='donation', custom_amount=False),
                Values(event=event_id, name='Custom Amount', price=None, mode='donation', custom_amount=True),
            ),
        )
        # debug(ticket_type_ids)
        self.ticket_type_id = self.ticket_type_id or ticket_type_ids[0]['id']
        self.donation_ticket_type_id_1 = self.donation_ticket_type_id_1 or ticket_type_ids[1]['id']
        self.donation_ticket_type_id_2 = self.donation_ticket_type_id_2 or ticket_type_ids[2]['id']

        await self.conn.execute_b(
            'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
            values=Values(
                company=self.company_id,
                user_id=host_user_id or self.user_id,
                type=ActionTypes.create_event,
                event=event_id,
            ),
        )
        return event_id

    async def create_reservation(self, user_id=None, *extra_user_ids, event_id=None, ticket_type_id=None):
        user_id = user_id or self.user_id
        action_id = await self.conn.fetchval_b(
            'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
            values=Values(company=self.company_id, user_id=user_id, type=ActionTypes.reserve_tickets),
        )
        ticket_type_id = ticket_type_id or self.ticket_type_id
        event_id = event_id or self.event_id

        assert event_id == await self.conn.fetchval('SELECT event FROM ticket_types WHERE id=$1', ticket_type_id)
        price = await self.conn.fetchval('SELECT price FROM ticket_types WHERE id=$1', ticket_type_id)
        ticket_values = [
            Values(event=event_id, user_id=user_id, reserve_action=action_id, ticket_type=ticket_type_id, price=price)
        ]
        for extra_user_id in extra_user_ids:
            ticket_values.append(
                Values(
                    event=event_id,
                    user_id=extra_user_id,
                    reserve_action=action_id,
                    ticket_type=ticket_type_id,
                    price=price,
                )
            )
        await self.conn.execute_b(
            'INSERT INTO tickets (:values__names) VALUES :values', values=MultipleValues(*ticket_values)
        )
        await self.conn.execute('SELECT check_tickets_remaining($1, $2)', event_id, self.settings.ticket_ttl)
        return Reservation(
            user_id=user_id,
            action_id=action_id,
            event_id=event_id,
            price_cent=price and int(price * 100),
            ticket_count=1 + len(extra_user_ids),
            event_name=await self.conn.fetchval('SELECT name FROM events WHERE id=$1', event_id),
        )

    async def buy_tickets(self, res: Reservation):
        await self.fire_stripe_webhook(reserve_action_id=res.action_id, event_id=res.event_id, user_id=res.user_id)

    async def fire_stripe_webhook(
        self,
        reserve_action_id,
        *,
        event_id=None,
        user_id=None,
        amount=10_00,
        purpose='buy-tickets',
        webhook_type='payment_intent.succeeded',
        charge_id='charge-id',
        expected_status=204,
        fire_delay=0,
        metadata=None,
    ):
        return await self._fire_stripe_webhook(
            user_id=user_id or self.user_id,
            event_id=event_id or self.event_id,
            reserve_action_id=reserve_action_id,
            amount=amount,
            purpose=purpose,
            webhook_type=webhook_type,
            charge_id=charge_id,
            expected_status=expected_status,
            fire_delay=fire_delay,
            metadata=metadata,
        )

    async def book_free(self, reservation: Reservation, user_id=None):
        m = BookFreeModel(
            booking_token=encrypt_json(reservation.dict(), auth_fernet=self.app['auth_fernet']),
            book_action='book-free-tickets',
        )
        return await book_free(m, self.company_id, {'user_id': user_id or self.user_id}, self.app, self.conn)

    async def create_donation_option(self, category_id=None, amount=20):
        donation_option_id = await self.conn.fetchval_b(
            'INSERT INTO donation_options (:values__names) VALUES :values RETURNING id',
            values=Values(
                category=category_id or self.category_id,
                name='testing donation option',
                amount=amount,
                short_description='This is the short_description.',
                long_description='This is the long_description.',
            ),
        )
        self.donation_option_id = self.donation_option_id or donation_option_id
        return donation_option_id

    async def create_donation(self, donation_option_id=None, event_id=None, amount=20, gift_aid=False):
        action_id = await self.conn.fetchval_b(
            'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
            values=Values(
                company=self.company_id, user_id=self.user_id, type=ActionTypes.donate, event=event_id or self.event_id
            ),
        )
        kwargs = dict(
            donation_option=donation_option_id or self.donation_option_id,
            amount=amount,
            gift_aid=gift_aid,
            action=action_id,
            first_name='Foo',
            last_name='Bar',
        )
        if gift_aid:
            kwargs.update(
                address='address', city='city', postcode='postcode',
            )
        donation_id = await self.conn.fetchval_b(
            'INSERT INTO donations (:values__names) VALUES :values RETURNING id', values=Values(**kwargs)
        )
        self.donation_id = self.donation_id or donation_id
        return donation_id


@pytest.fixture
async def factory(db_conn, cli, fire_stripe_webhook):
    return Factory(db_conn, cli.app['main_app'], fire_stripe_webhook)


@pytest.fixture
def login(cli, url):
    async def f(email='frank@example.org', password='testing', captcha=False):
        data = dict(email=email, password=password)
        if captcha:
            data['grecaptcha_token'] = '__ok__'
        r = await cli.json_post(url('login'), data=data, origin_null=True)
        assert r.status == 200, await r.text()
        data = await r.json()
        r = await cli.json_post(url('auth-token'), data={'token': data['auth_token']})
        assert r.status == 200, await r.text()
        assert len(cli.session.cookie_jar) == 1
        return r

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
    app['main_app']['pg'] = SimplePgPool(app['test_conn'])


async def post_startup_app(app):
    inner_app = app['main_app']
    inner_app['email_actor'].pg = inner_app['pg']
    inner_app['email_actor']._concurrency_enabled = False
    inner_app['donorfy_actor'].pg = inner_app['pg']
    inner_app['donorfy_actor']._concurrency_enabled = False
    await inner_app['donorfy_actor'].startup()


async def pre_cleanup(app):
    donorfy_actor = app['main_app']['donorfy_actor']
    if donorfy_actor.client:
        await donorfy_actor.client.close()


@pytest.fixture(name='cli')
async def _fix_cli(settings, db_conn, aiohttp_client, redis):
    app = create_app(settings=settings)
    app['test_conn'] = db_conn
    app.on_startup.insert(0, pre_startup_app)
    app.on_startup.append(post_startup_app)
    app.on_cleanup.insert(0, pre_cleanup)
    cli = await aiohttp_client(app)

    def json_post(url, *, data=None, headers=None, origin_null=False):
        if data and not isinstance(data, str):
            data = json.dumps(data)
        headers = {
            'Content-Type': 'application/json',
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': 'null' if origin_null else f'http://127.0.0.1:{cli.server.port}',
            **(headers or {}),
        }
        return cli.post(url, data=data, headers=headers)

    cli.json_post = json_post
    return cli


@pytest.fixture(name='url')
def _fix_url(cli):
    def f(name, *, query=None, **kwargs):
        inner_app = cli.server.app['main_app']
        try:
            r = inner_app.router[name]
        except KeyError as e:
            print('routes:', pformat(inner_app.router._named_resources))
            raise e
        assert None not in kwargs.values(), f'invalid kwargs, includes none: {kwargs}'
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


def create_image(width=2000, height=1200, mode='RGB', format='JPEG'):
    stream = BytesIO()
    image = Image.new(mode, (width, height), (50, 100, 150))
    ImageDraw.Draw(image).line((0, 0) + image.size, fill=128)
    image.save(stream, format=format, optimize=True)
    return stream.getvalue()


@pytest.fixture(name='setup_static')
def _setup_static(tmpdir):
    tmpdir.join('index.html').write('this is index.html')
    tmpdir.join('test.js').write('this is test.js')
    tmpdir.join('iframes').mkdir()
    tmpdir.join('iframes').join('login.html').write('this is iframes/login.html')


@pytest.yield_fixture(name='fire_stripe_webhook')
async def _fix_fire_stripe_webhook(url, settings, cli, loop):
    webhook_cli = TestClient(cli.server, loop=loop)

    async def fire(
        *,
        user_id,
        event_id,
        reserve_action_id,
        amount,
        purpose,
        webhook_type,
        charge_id,
        expected_status,
        fire_delay,
        metadata,
    ):
        if metadata is None:
            metadata = {
                'purpose': purpose,
                'user_id': user_id,
                'event_id': event_id,
                'reserve_action_id': reserve_action_id,
            }
        data = {
            'type': webhook_type,
            'data': {
                'object': {
                    'amount': amount,
                    'metadata': metadata,
                    'charges': {
                        'data': [
                            {
                                'id': charge_id,
                                'balance_transaction': 'txn_' + charge_id,
                                'created': time() - fire_delay,
                                'payment_method_details': {
                                    'card': {
                                        'brand': 'Visa',
                                        'last4': '1234',
                                        'exp_month': 12,
                                        'exp_year': 2032,
                                        'three_d_secure': True,
                                    }
                                },
                            }
                        ]
                    },
                }
            },
        }
        body = json.dumps(data)
        t = int(time())
        sig = hmac.new(b'stripe_webhook_secret_xxx', f'{t}.{body}'.encode(), hashlib.sha256).hexdigest()

        r = await cli.post(url('stripe-webhook'), data=body, headers={'Stripe-Signature': f't={t},v1={sig}'})
        assert r.status == expected_status, await r.text()
        return r

    yield fire

    await webhook_cli.close()


class Offline:
    def __init__(self):
        self.is_offline = None

    def __bool__(self):
        if self.is_offline is None:
            loop = asyncio.new_event_loop()
            self.is_offline = loop.run_until_complete(self._check())
        return self.is_offline

    async def _check(self):
        resolver = aiodns.DNSResolver()
        try:
            with timeout(1):
                await resolver.query('google.com', 'A')
        except (aiodns.error.DNSError, asyncio.TimeoutError) as e:
            print(f'\nnot online: {e.__class__.__name__} {e}\n', file=sys.stderr)
            return True
        else:
            return False


_offline = Offline()
if_online = pytest.mark.skipif(_offline, reason='not online')
