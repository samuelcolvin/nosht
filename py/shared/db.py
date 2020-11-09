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
from buildpg import MultipleValues, Values, asyncpg

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


class SimplePgPool:  # pragam: no cover
    def __init__(self, conn):
        self.conn = conn
        # could also add lock to each method of the returned connection
        self._lock = asyncio.Lock(loop=self.conn._loop)

    def acquire(self):
        return self

    async def __aenter__(self):
        return self.conn

    async def execute(self, *args, **kwargs):
        async with self._lock:
            return await self.conn.execute(*args, **kwargs)

    async def fetch(self, *args, **kwargs):
        async with self._lock:
            return await self.conn.fetch(*args, **kwargs)

    async def fetchval(self, *args, **kwargs):
        async with self._lock:
            return await self.conn.fetchval(*args, **kwargs)

    async def fetchrow(self, *args, **kwargs):
        async with self._lock:
            return await self.conn.fetchrow(*args, **kwargs)

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
        print(
            'available patches:\n{}'.format(
                '\n'.join('  {}: {}'.format(p.func.__name__, p.func.__doc__.strip('\n ')) for p in patches)
            )
        )
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
                'start_ts': datetime(2032, 1, 28, 19, 0),
                'duration': timedelta(hours=2),
                'location_name': '31 Testing Road, London',
                'location_lat': 51.479415,
                'location_lng': -0.132098,
                'ticket_limit': 40,
                'host_email': 'frank@example.com',
                'ticket_types': [{'name': 'Standard', 'price': 30}],
            },
            {
                'status': 'published',
                'highlight': True,
                'name': "Jane's Great Supper",
                'start_ts': datetime(2032, 2, 10, 18, 0),
                'duration': timedelta(hours=3),
                'location_name': '253 Brixton Road, London',
                'location_lat': 51.514412,
                'location_lng': -0.073994,
                'ticket_limit': None,
                'host_email': 'jane@example.com',
                'ticket_types': [{'name': 'Standard', 'price': 25, 'slots_used': 5}],
            },
        ],
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
                'start_ts': datetime(2032, 2, 15),
                'duration': None,
                'location_name': 'Big Church, London',
                'ticket_limit': None,
                'host_email': 'frank@example.com',
                'ticket_types': [{'name': 'Standard', 'price': None, 'slots_used': 5}],
            },
            {
                'status': 'published',
                'highlight': False,
                'name': 'Quiet Singing',
                'start_ts': datetime(2032, 2, 20),
                'duration': None,
                'location_name': 'Small Church, London',
                'ticket_limit': None,
                'host_email': 'frank@example.com',
                'ticket_types': [{'name': 'Standard', 'price': None}],
            },
        ],
    },
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
                stripe_secret_key='sk_test_GLQSaid6wFrYZp44d3dcTl8f',
            ),
        )

        user_lookup = {}
        for user in USERS:
            user_lookup[user['email']] = await conn.fetchval_b(
                'INSERT INTO users (:values__names) VALUES :values RETURNING id',
                values=Values(company=company_id, password_hash=mk_password(user.pop('password'), settings), **user),
            )

        for cat in CATS:
            events = cat.pop('events')
            cat_slug = slugify(cat['name'])
            cat_id = await conn.fetchval_b(
                'INSERT INTO categories (:values__names) VALUES :values RETURNING id',
                values=Values(
                    company=company_id,
                    slug=cat_slug,
                    image=await create_image(Path(co_slug) / cat_slug / 'option', client, settings),
                    **cat,
                ),
            )

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
                        **event,
                    ),
                )
                await conn.executemany_b(
                    'INSERT INTO ticket_types (:values__names) VALUES :values',
                    [Values(event=event_id, **tt) for tt in ticket_types],
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
        values=Values(name=co_name, slug=co_slug, domain=co_domain),
    )
    user_name = input("Enter the main admin's name: ").strip(' ')
    if ' ' in user_name:
        first_name, last_name = user_name.split(' ', 1)
    else:
        first_name, last_name = user_name, None
    user_email = input("Enter the main admin's email address: ").strip(' ')

    user_id = await conn.fetchval_b(
        'INSERT INTO users (:values__names) VALUES :values RETURNING id',
        values=Values(company=company_id, email=user_email, first_name=first_name, last_name=last_name, role='admin'),
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


@patch
async def email_logging(conn, settings, **kwargs):
    """
    create emails and email_events tables and indexes
    """
    models_sql = settings.models_sql
    m = re.search('-- { email change(.*)-- } email change', models_sql, flags=re.DOTALL)
    sql = m.group(1).strip(' \n')
    await conn.execute(sql)


@patch
async def add_secondary_image(conn, **kwargs):
    """
    add secondary_image field to events
    """
    await conn.execute('ALTER TABLE events ADD COLUMN secondary_image VARCHAR(255)')


@patch
async def add_cancel_action(conn, **kwargs):
    """
    add cancel_action field to tickets
    """
    await conn.execute('ALTER TABLE tickets ADD COLUMN cancel_action INT REFERENCES actions ON DELETE SET NULL')


@patch
async def add_external_ticketing(conn, **kwargs):
    """
    add the external_ticket_url column to events
    """
    await conn.execute('ALTER TABLE events ADD COLUMN external_ticket_url VARCHAR(255)')


@patch
async def add_stripe_webhook_secret(conn, **kwargs):
    """
    add the stripe_webhook_secret column to companies
    """
    await conn.execute('ALTER TABLE companies ADD COLUMN stripe_webhook_secret VARCHAR(63)')


@patch
async def add_search_table(conn, settings, **kwargs):
    """
    create search table and indexes, also runs logic.sql to create triggers
    """
    models_sql = settings.models_sql
    m = re.search('-- { search(.*)-- } search', models_sql, flags=re.DOTALL)
    search_sql = m.group(1).strip(' \n')
    print('running search table sql...')
    await conn.execute(search_sql)
    print('running logic.sql...')
    await conn.execute(settings.logic_sql)


@patch
async def update_search_index(conn, **kwargs):
    """
    update the search index by running a pointless update on users and events
    """
    await conn.execute('UPDATE users SET phone_number=phone_number')
    await conn.execute('UPDATE events SET short_description=short_description')


@patch
async def add_waiting_list(conn, settings, **kwargs):
    """
    create waiting_list table and indexes
    """
    models_sql = settings.models_sql
    m = re.search('-- { waiting-list(.*)-- } waiting-list', models_sql, flags=re.DOTALL)
    waiting_list_sql = m.group(1).strip(' \n')
    print('running waiting-list table sql...')
    await conn.execute(waiting_list_sql)


@patch(direct=True)
async def add_donation_enum(conn, settings, **kwargs):
    """
    create the TICKET_MODE enum
    """
    await conn.execute("CREATE TYPE TICKET_MODE AS ENUM ('ticket', 'donation')")


@patch
async def add_donations(conn, settings, **kwargs):
    """
    modifications required to allow direct donations on events.
    """
    await conn.execute('ALTER TABLE events ADD COLUMN allow_donations BOOLEAN NOT NULL DEFAULT FALSE')
    await conn.execute('ALTER TABLE events ADD COLUMN allow_tickets BOOLEAN NOT NULL DEFAULT TRUE')
    await conn.execute(
        'ALTER TABLE events ADD COLUMN donation_target NUMERIC(10, 2) '
        'CONSTRAINT donation_target_gte_1 CHECK (donation_target > 0)'
    )
    await conn.execute("ALTER TABLE ticket_types ADD COLUMN mode TICKET_MODE NOT NULL DEFAULT 'ticket'")
    await conn.execute('ALTER TABLE ticket_types ADD COLUMN custom_amount BOOL NOT NULL DEFAULT FALSE')
    await conn.execute('CREATE INDEX ticket_type_mode ON ticket_types USING btree (mode)')

    await conn.execute('ALTER TABLE donations ALTER COLUMN donation_option DROP NOT NULL')
    await conn.execute('ALTER TABLE donations ADD COLUMN ticket_type INT REFERENCES ticket_types ON DELETE CASCADE')
    await conn.execute(
        'ALTER TABLE donations ADD CONSTRAINT donation_option_or_ticket_type_required '
        'CHECK (num_nonnulls(donation_option, ticket_type) = 1)'
    )


@patch
async def insert_donation_ticket_types(conn, settings, **kwargs):
    """
    add donation ticket types to old event
    """
    event_ids = await conn.fetchval(
        """
        select coalesce(array_agg(event_id), '{}'::integer[])
        from (
            select e.id event_id, COUNT(tt.id) > 0 AS has_donation_tts
            from events e
            left join ticket_types tt on e.id = tt.event and tt.mode = 'donation'
            group by e.id
        ) t
        where not has_donation_tts
        """
    )
    logger.info('%s events to add donation ticket types to', len(event_ids))

    values = []
    for event_id in event_ids:
        values += [
            Values(event=event_id, name='Standard', price=10, mode='donation', custom_amount=False),
            Values(event=event_id, name='Custom Amount', price=None, mode='donation', custom_amount=True),
        ]
    if values:
        logger.info('inserting %d ticket_types', len(values))
        await conn.execute_b(
            'INSERT INTO ticket_types (:values__names) VALUES :values', values=MultipleValues(*values),
        )


@patch
async def add_event_youtube_field(conn, **kwargs):
    """
    add the youtube_video_id column to events
    """
    await conn.execute('ALTER TABLE events ADD COLUMN youtube_video_id VARCHAR(140)')


@patch
async def change_event_name_field_length(conn, **kwargs):
    """
    Change the length of event name field
    """
    await conn.execute('ALTER TABLE events ALTER COLUMN name TYPE VARCHAR(150)')


@patch
async def add_event_description_intro_field(conn, **kwargs):
    """
    add the description_intro column to events
    """
    await conn.execute('ALTER TABLE events ADD COLUMN description_intro TEXT')
    await conn.execute('ALTER TABLE events ADD COLUMN description_image VARCHAR(255)')


@patch
async def add_external_donations(conn, **kwargs):
    """
    add the external_donation_url column to events
    """
    await conn.execute('ALTER TABLE events ADD COLUMN external_donation_url VARCHAR(255)')
