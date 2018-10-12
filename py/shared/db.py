import asyncio
import logging
import os
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, NamedTuple

import aiohttp
from async_timeout import timeout
from buildpg import Values, asyncpg

from .actions import ActionTypes
from .emails.defaults import Triggers
from .emails.main import EmailActor
from .images import upload_background
from .settings import Settings
from .utils import mk_password, slugify

logger = logging.getLogger('nosht.db')
patches = []


class Patch(NamedTuple):
    func: Callable
    direct: bool = False


async def lenient_conn(settings: Settings, with_db=True):
    if with_db:
        dsn = settings.pg_dsn
    else:
        dsn, _ = settings.pg_dsn.rsplit('/', 1)

    for retry in range(8, -1, -1):
        try:
            async with timeout(2):
                conn = await asyncpg.connect_b(dsn=dsn)
        except (asyncpg.PostgresError, OSError) as e:
            if retry == 0:
                raise
            else:
                logger.warning('pg temporary connection error "%s", %d retries remaining...', e, retry)
                await asyncio.sleep(1)
        else:
            log = logger.debug if retry == 8 else logger.info
            log('pg connection successful, version: %s', await conn.fetchval('SELECT version()'))
            return conn


DROP_CONNECTIONS = """
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = $1 AND pid <> pg_backend_pid();
"""


async def prepare_database(settings: Settings, overwrite_existing: bool) -> bool:
    """
    (Re)create a fresh database and run migrations.
    :param settings: settings to use for db connection
    :param overwrite_existing: whether or not to drop an existing database if it exists
    :return: whether or not a database has been (re)created
    """
    # the db already exists on heroku and never has to be created
    if settings.on_heroku:
        conn = await lenient_conn(settings, with_db=True)
        try:
            tables = await conn.fetchval("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
            logger.info('existing tables: %d', tables)
            if tables > 0:
                if overwrite_existing:
                    logger.debug('database already exists...')
                else:
                    logger.debug('database already exists ✓')
                    return False
        finally:
            await conn.close()
    else:
        conn = await lenient_conn(settings, with_db=False)
        try:
            if not overwrite_existing:
                # don't drop connections and try creating a db if it already exists and we're not overwriting
                exists = await conn.fetchval('SELECT 1 AS result FROM pg_database WHERE datname=$1', settings.pg_name)
                if exists:
                    return False

            await conn.execute(DROP_CONNECTIONS, settings.pg_name)
            logger.debug('attempting to create database "%s"...', settings.pg_name)
            try:
                await conn.execute('CREATE DATABASE {}'.format(settings.pg_name))
            except (asyncpg.DuplicateDatabaseError, asyncpg.UniqueViolationError):
                if overwrite_existing:
                    logger.debug('database already exists...')
                else:
                    logger.debug('database already exists, skipping creation')
                    return False
            else:
                logger.debug('database did not exist, now created')

            logger.debug('settings db timezone to utc...')
            await conn.execute(f"ALTER DATABASE {settings.pg_name} SET TIMEZONE TO 'UTC';")
        finally:
            await conn.close()

    conn = await asyncpg.connect(dsn=settings.pg_dsn)
    try:
        logger.debug('creating tables from model definition...')
        async with conn.transaction():
            await conn.execute(settings.models_sql + '\n' + settings.logic_sql)
    finally:
        await conn.close()
    logger.info('database successfully setup ✓')
    return True


class SimplePgPool:
    def __init__(self, conn):
        self.conn = conn
        self.fetchval = conn.fetchval
        self.fetchrow = conn.fetchrow
        self.fetch = conn.fetch

    def acquire(self):
        return self

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def close(self):
        pass


def reset_database(settings: Settings):
    if not (os.getenv('CONFIRM_DATABASE_RESET') == 'confirm' or input('Confirm database reset? [yN] ') == 'y'):
        print('cancelling')
    else:
        print('resetting database...')
        loop = asyncio.get_event_loop()
        loop.run_until_complete(prepare_database(settings, True))
        print('done.')


def run_patch(settings: Settings, live, patch_name):
    if patch_name is None:
        print('available patches:\n{}'.format(
            '\n'.join('  {}: {}'.format(p.func.__name__, p.func.__doc__.strip('\n ')) for p in patches)
        ))
        return
    patch_lookup = {p.func.__name__: p for p in patches}
    try:
        patch = patch_lookup[patch_name]
    except KeyError as e:
        raise RuntimeError(f'patch "{patch_name}" not found in patches: {[p.func.__name__ for p in patches]}') from e

    if patch.direct:
        if not live:
            raise RuntimeError('direct patches must be called with "--live"')
        print(f'running patch {patch_name} direct')
    else:
        print(f'running patch {patch_name} live {live}')
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(_run_patch(settings, live, patch))


async def _run_patch(settings, live, patch: Patch):
    conn = await lenient_conn(settings)
    tr = None
    if not patch.direct:
        tr = conn.transaction()
        await tr.start()
    print('=' * 40)
    try:
        await patch.func(conn, settings=settings, live=live)
    except BaseException:
        print('=' * 40)
        logger.exception('Error running %s patch', patch.func.__name__)
        if not patch.direct:
            await tr.rollback()
        return 1
    else:
        print('=' * 40)
        if patch.direct:
            print('committed patch')
        else:
            if live:
                print('live, committed patch')
                await tr.commit()
            else:
                print('not live, rolling back')
                await tr.rollback()
    finally:
        await conn.close()


def patch(*args, direct=False):
    if args:
        assert len(args) == 1, 'wrong arguments to patch'
        func = args[0]
        patches.append(Patch(func=func))
        return func
    else:
        def wrapper(func):
            patches.append(Patch(func=func, direct=direct))
            return func

        return wrapper


@patch
async def run_logic_sql(conn, settings, **kwargs):
    """
    run logic.sql code.
    """
    await conn.execute(settings.logic_sql)


@patch(direct=True)
async def update_enums(conn, settings, **kwargs):
    """
    update sql from ActionTypes and Triggers enums (direct)
    """
    for t in ActionTypes:
        await conn.execute(f"ALTER TYPE ACTION_TYPES ADD VALUE IF NOT EXISTS '{t.value}'")
    for t in Triggers:
        await conn.execute(f"ALTER TYPE EMAIL_TRIGGERS ADD VALUE IF NOT EXISTS '{t.value}'")


USERS = [
    {
        'first_name': 'Frank',
        'last_name': 'Spencer',
        'email': 'frank@example.com',
        'role': 'admin',
        'status': 'active',
        'password': 'testing',
    },
    {
        'first_name': 'Jane',
        'last_name': 'Dow',
        'email': 'jane@example.com',
        'role': 'host',
        'status': 'pending',
        'password': 'testing',
    },
]

IMAGES = [
    '0KPVDbDZFU/main.jpg',
    '0PYuY1448h/main.jpg',
    '8MkUuIAlTC/main.jpg',
    '8TeTuuJ2Eo/main.jpg',
    '9temf5JuFg/main.jpg',
    'EVmwCc1E3j/main.jpg',
    'H0aDotyQ10/main.jpg',
    'H2tpkxGYFB/main.jpg',
    'LODboU025Q/main.jpg',
    'a3Am9F1TwZ/main.jpg',
    'bHxDxtbBx6/main.jpg',
    'bIh18JppSg/main.jpg',
    'hTIw27nQBu/main.jpg',
    'hvo3lwnW8O/main.jpg',
    'jcOl33tWAW/main.jpg',
    'qCLMsyr437/main.jpg',
    'tutva5VL4W/main.jpg',
    'u0Mnok4eTF/main.jpg',
    'vCKpy2SW85/main.jpg',
]


async def create_image(upload_path, client, settings):
    url = settings.s3_demo_image_url + random.choice(IMAGES)
    async with client.get(url) as r:
        assert r.status == 200, r.status
        content = await r.read()

    return await upload_background(content, upload_path, settings)


CATS = [
    {
        'name': 'Supper Clubs',
        'description': 'Eat, drink & discuss middle aged, middle class things like house prices and consumerist guilt',
        'ticket_extra_title': 'Dietary Requirements & Extra Information',
        'ticket_extra_help_text': 'This is the help text for this field, tell us about your nut allergy',
        'sort_index': 1,
        'events': [

            {
                'status': 'published',
                'highlight': True,
                'name': "Frank's Great Supper",
                'start_ts': datetime(2020, 1, 28, 19, 0),
                'duration': timedelta(hours=2),
                'location_name': '31 Testing Road, London',
                'location_lat': 51.479415,
                'location_lng': -0.132098,
                'ticket_limit': 40,
                'host_email': 'frank@example.com',
                'ticket_types': [
                    {
                        'name': 'Standard',
                        'price': 30,
                    }
                ]
            },
            {
                'status': 'published',
                'highlight': True,
                'name': "Jane's Great Supper",
                'start_ts': datetime(2020, 2, 10, 18, 0),
                'duration': timedelta(hours=3),
                'location_name': '253 Brixton Road, London',
                'location_lat': 51.514412,
                'location_lng': -0.073994,
                'ticket_limit': None,
                'host_email': 'jane@example.com',
                'ticket_types': [
                    {
                        'name': 'Standard',
                        'price': 25,
                        'slots_used': 5,
                    }
                ]
            }
        ]
    },
    {

        'name': 'Singing Events',
        'description': 'Sing loudly and badly in the company of other people too polite to comment',
        'ticket_extra_title': 'Extra Information',
        'ticket_extra_help_text': 'This is the help text for this field',
        'sort_index': 2,
        'events': [
            {
                'status': 'published',
                'highlight': True,
                'name': 'Loud Singing',
                'start_ts': datetime(2020, 2, 15),
                'duration': None,
                'location_name': 'Big Church, London',
                'ticket_limit': None,
                'host_email': 'frank@example.com',
                'ticket_types': [
                    {
                        'name': 'Standard',
                        'price': None,
                        'slots_used': 5,
                    }
                ]
            },
            {
                'status': 'published',
                'highlight': False,
                'name': 'Quiet Singing',
                'start_ts': datetime(2020, 2, 20),
                'duration': None,
                'location_name': 'Small Church, London',
                'ticket_limit': None,
                'host_email': 'frank@example.com',
                'ticket_types': [
                    {
                        'name': 'Standard',
                        'price': None,
                    }
                ]
            },
        ]
    }
]

EVENT_LONG_DESCRIPTION = """
Sit quisquam quisquam eius sed tempora. Aliquam labore **quisquam** tempora _voluptatem_.
Porro eius eius etincidunt sit etincidunt. Adipisci dolor amet eius. [Magnam quaerat](https://www.example.com).

Neque labore est numquam dolorem. Quiquia ipsum ut dolore dolore porro. Voluptatem consectetur amet ipsum adipisci
dolor aliquam. Quiquia modi tempora tempora non amet aliquam. Aliquam eius quiquia voluptatem. Numquam numquam
etincidunt neque non est est consectetur.

## Lists

Example of list:
* Tempora ut aliquam consectetur aliquam.
* Dolorem quaerat porro ipsum. Sed ipsum tempora est. Neque
* amet amet quisquam dolore labore magnam.

Numbered:
1. whatever
1. whenever
1. whichever

### Table

| foo | bar |
| --- | --- |
| baz | bim |

"""


@patch
async def create_demo_data(conn, settings, **kwargs):
    """
    Create some demo data for manual testing.
    """
    async with aiohttp.ClientSession() as client:
        co_slug = 'testing-co'
        company_id = await conn.fetchval_b(
            'INSERT INTO companies (:values__names) VALUES :values RETURNING id',
            values=Values(
                name='Testing Company',
                slug=co_slug,
                image=await create_image(Path(co_slug) / 'co' / 'image', client, settings),
                domain=kwargs.get('company_domain', os.getenv('NEW_COMPANY_DOMAIN', 'localhost')),
                # from "Scolvin Testing" testing account
                stripe_public_key='pk_test_efpfygU2qxGIwgcjn5T5DTTI',
                stripe_secret_key='sk_test_GLQSaid6wFrYZp44d3dcTl8f'
            )
        )

        user_lookup = {}
        for user in USERS:
            user_lookup[user['email']] = await conn.fetchval_b("""
            INSERT INTO users (:values__names) VALUES :values RETURNING id
            """, values=Values(company=company_id, password_hash=mk_password(user.pop('password'), settings), **user))

        for cat in CATS:
            events = cat.pop('events')
            cat_slug = slugify(cat['name'])
            cat_id = await conn.fetchval_b("""
        INSERT INTO categories (:values__names) VALUES :values RETURNING id
        """, values=Values(
                company=company_id,
                slug=cat_slug,
                image=await create_image(Path(co_slug) / cat_slug / 'option', client, settings),
                **cat,
            ))

            for event in events:
                ticket_types = event.pop('ticket_types', [])
                event_slug = slugify(event['name'])
                event_id = await conn.fetchval_b(
                    'INSERT INTO events (:values__names) VALUES :values RETURNING id',
                    values=Values(
                        category=cat_id,
                        host=user_lookup[event.pop('host_email')],
                        slug=event_slug,
                        image=await create_image(Path(co_slug) / cat_slug / event_slug, client, settings),
                        short_description='Neque labore est numquam dolorem. Quiquia ipsum ut dolore dolore porro.',
                        long_description=EVENT_LONG_DESCRIPTION,
                        **event
                    )
                )
                await conn.executemany_b(
                    'INSERT INTO ticket_types (:values__names) VALUES :values',
                    [Values(event=event_id, **tt) for tt in ticket_types]
                )


@patch
async def create_new_company(conn, settings, live, **kwargs):
    """
    Create a new company
    """
    co_name = input("Enter the company's name: ")
    co_slug = slugify(co_name)
    co_domain = input("Enter the company's domain: ")

    company_id = await conn.fetchval_b(
        'INSERT INTO companies (:values__names) VALUES :values RETURNING id',
        values=Values(
            name=co_name,
            slug=co_slug,
            domain=co_domain,
        )
    )
    user_name = input("Enter the main admin's name: ").strip(' ')
    if ' ' in user_name:
        first_name, last_name = user_name.split(' ', 1)
    else:
        first_name, last_name = user_name, None
    user_email = input("Enter the main admin's email address: ").strip(' ')

    user_id = await conn.fetchval_b(
        'INSERT INTO users (:values__names) VALUES :values RETURNING id',
        values=Values(
            company=company_id,
            email=user_email,
            first_name=first_name,
            last_name=last_name,
            role='admin',
        ),
    )
    actor = EmailActor(settings=settings, pg=SimplePgPool(conn))
    await actor.startup()
    if live:
        await actor.send_account_created.direct(user_id, created_by_admin=True)
    await actor.close(shutdown=True)


@patch
async def apply_donation_migrations(conn, settings, **kwargs):
    """
    create donation_options and donations tables and indexes, you'll also need to update enums
    """
    models_sql = settings.models_sql
    m = re.search('-- { donations change(.*)-- } donations change', models_sql, flags=re.DOTALL)
    donations_sql = m.group(1).strip(' \n')
    await conn.execute(donations_sql)


@patch
async def update_image_paths(conn, settings, **kwargs):
    """
    add main.jpg to all image paths
    """
    v = await conn.execute("UPDATE companies SET image = image || '/main.jpg' WHERE image NOT LIKE '%/main%'")
    logger.info('companies image: %s', v)
    v = await conn.execute("UPDATE companies SET logo = logo || '/main.jpg' WHERE logo NOT LIKE '%/main%'")
    logger.info('companies logo: %s', v)
    v = await conn.execute("UPDATE categories SET image = image || '/main.jpg' WHERE image NOT LIKE '%/main%'")
    logger.info('categories: %s', v)
    v = await conn.execute("UPDATE events SET image = image || '/main.jpg' WHERE image NOT LIKE '%/main%'")
    logger.info('events: %s', v)
    v = await conn.execute("UPDATE donation_options SET image = image || '/main.jpg' WHERE image NOT LIKE '%/main%'")
    logger.info('donation_options: %s', v)


@patch
async def add_post_booking_message(conn, **kwargs):
    """
    add post_booking_message field to categories
    """
    await conn.execute('ALTER TABLE categories ADD COLUMN post_booking_message TEXT')


@patch
async def add_footer_links(conn, **kwargs):
    """
    add footer_links field to companies
    """
    await conn.execute('ALTER TABLE companies ADD COLUMN footer_links JSONB')


@patch
async def use_timezones(conn, **kwargs):
    """
    convert all TIMESTAMP fields to TIMESTAMPTZ
    """
    await conn.execute("ALTER TABLE companies ADD COLUMN display_timezone VARCHAR(63) NOT NULL DEFAULT 'Europe/London'")

    await conn.execute("ALTER TABLE events ADD COLUMN timezone VARCHAR(63) NOT NULL DEFAULT 'Europe/London'")
    await conn.execute('ALTER TABLE events ALTER COLUMN start_ts TYPE TIMESTAMPTZ')

    await conn.execute('ALTER TABLE users ALTER COLUMN created_ts TYPE TIMESTAMPTZ')
    await conn.execute('ALTER TABLE users ALTER COLUMN active_ts TYPE TIMESTAMPTZ')

    await conn.execute('ALTER TABLE actions ALTER COLUMN ts TYPE TIMESTAMPTZ')

    await conn.execute('ALTER TABLE tickets ALTER COLUMN created_ts TYPE TIMESTAMPTZ')


@patch
async def add_donation_title(conn, **kwargs):
    """
    add title field to donations
    """
    await conn.execute('ALTER TABLE donations ADD COLUMN title VARCHAR(31)')
