import asyncio
import logging
import os
import random
from datetime import datetime, timedelta
from enum import Enum
from textwrap import shorten

import lorem
from async_timeout import timeout
from buildpg import Values, asyncpg

from .emails.defaults import Triggers
from .settings import Settings
from .utils import mk_password, slugify

logger = logging.getLogger('nosht.db')
patches = []


class ActionTypes(str, Enum):
    login = 'login'
    guest_signin = 'guest-signin'
    host_signup = 'host-signup'
    logout = 'logout'
    password_reset = 'password-reset'
    reserve_tickets = 'reserve-tickets'
    buy_tickets = 'buy-tickets'
    cancel_reserved_tickets = 'cancel-reserved-tickets'
    edit_event = 'edit-event'
    edit_other = 'edit-other'
    unsubscribe = 'unsubscribe'


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


def reset_database(settings: Settings):
    if not (os.getenv('CONFIRM_DATABASE_RESET') == 'confirm' or input('Confirm database reset? [yN] ') == 'y'):
        print('cancelling')
    else:
        print('resetting database...')
        loop = asyncio.get_event_loop()
        loop.run_until_complete(prepare_database(settings, True))
        print('done.')


def run_patch(settings: Settings, live, direct, patch_name):
    if patch_name is None:
        print('available patches:\n{}'.format(
            '\n'.join('  {}: {}'.format(p.__name__, p.__doc__.strip('\n ')) for p in patches)
        ))
        return
    patch_lookup = {p.__name__: p for p in patches}
    try:
        patch_func = patch_lookup[patch_name]
    except KeyError as e:
        raise RuntimeError(f'patch "{patch_name}" not found in patches: {[p.__name__ for p in patches]}') from e

    if direct:
        print(f'running patch {patch_name} direct')
    else:
        print(f'running patch {patch_name} live {live}')
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_run_patch(settings, live, direct, patch_func))


async def _run_patch(settings, live, direct, patch_func):
    conn = await lenient_conn(settings)
    tr = None
    if not direct:
        tr = conn.transaction()
        await tr.start()
    print('=' * 40)
    try:
        await patch_func(conn, settings=settings, live=live)
    except BaseException as e:
        print('=' * 40)
        if direct:
            raise RuntimeError('error running patch') from e
        else:
            await tr.rollback()
            raise RuntimeError('error running patch, rolling back') from e
    else:
        print('=' * 40)
        if direct:
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


def patch(func):
    patches.append(func)
    return func


@patch
async def run_logic_sql(conn, settings, **kwargs):
    """
    run logic.sql code.
    """
    await conn.execute(settings.logic_sql)


@patch
async def update_enums(conn, settings, **kwargs):
    """
    update sql from ActionTypes and Triggers enums
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

CATS = [
    {
        'name': 'Supper Clubs',
        'description': 'Eat, drink & discuss middle aged, middle class things like house prices and consumerist guilt',
        'image': 'https://nosht.scolvin.com/cat/mountains/options/0DRztZurMo',
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
                'image': 'https://nosht.scolvin.com/cat/mountains/options/3WsQ7fKy0G',
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
                'image': 'https://nosht.scolvin.com/cat/mountains/options/YEcz6kUlsc',
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
        'image': 'https://nosht.scolvin.com/cat/mountains/options/zwaxBXpsyu',
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
                'image': 'https://nosht.scolvin.com/cat/mountains/options/p6UsCdOnGG',
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
                'image': 'https://nosht.scolvin.com/cat/mountains/options/YEcz6kUlsc',
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
    company_id = await conn.fetchval_b(
        'INSERT INTO companies (:values__names) VALUES :values RETURNING id',
        values=Values(
            name='Testing Company',
            slug='testing-co',
            image='https://nosht.scolvin.com/cat/mountains/options/3WsQ7fKy0G',
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
        cat_id = await conn.fetchval_b("""
    INSERT INTO categories (:values__names) VALUES :values RETURNING id
    """, values=Values(company=company_id, slug=slugify(cat['name']), **cat))

        for event in events:
            ticket_types = event.pop('ticket_types', [])
            event_id = await conn.fetchval_b(
                'INSERT INTO events (:values__names) VALUES :values RETURNING id',
                values=Values(
                    category=cat_id,
                    host=user_lookup[event.pop('host_email')],
                    slug=slugify(event['name']),
                    short_description=shorten(lorem.paragraph(), width=random.randint(100, 140), placeholder='...'),
                    long_description=EVENT_LONG_DESCRIPTION,
                    **event
                )
            )
            await conn.executemany_b(
                'INSERT INTO ticket_types (:values__names) VALUES :values',
                [Values(event=event_id, **tt) for tt in ticket_types]
            )
