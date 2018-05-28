import asyncio
import logging
import os

import asyncpg
from async_timeout import timeout

from .settings import Settings

logger = logging.getLogger('nosht.db')
patches = []


async def lenient_conn(settings: Settings, with_db=True):
    if with_db:
        dsn = settings.pg_dsn
    else:
        dsn, _ = settings.pg_dsn.rsplit('/', 1)

    for retry in range(8, -1, -1):
        try:
            async with timeout(2):
                conn = await asyncpg.connect(dsn=dsn)
        except (asyncpg.PostgresError, OSError) as e:
            if retry == 0:
                raise
            else:
                logger.warning('pg temporary connection error "%s", %d retries remaining...', e, retry)
                await asyncio.sleep(1)
        else:
            logger.info('pg connection successful, version: %s', await conn.fetchval('SELECT version()'))
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
                    logger.info('database already exists ✓')
                    return False
        finally:
            await conn.close()
    else:
        conn = await lenient_conn(settings, with_db=False)
        try:
            await conn.execute(DROP_CONNECTIONS, settings.pg_name)
            logger.debug('attempting to create database "%s"...', settings.pg_name)
            try:
                await conn.execute('CREATE DATABASE {}'.format(settings.pg_name))
            except (asyncpg.DuplicateDatabaseError, asyncpg.UniqueViolationError):
                if overwrite_existing:
                    logger.debug('database already exists...')
                else:
                    logger.info('database already exists, skipping creation')
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


def run_patch(settings: Settings, live, patch_name):
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

    print(f'running patch {patch_name} live {live}')
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_run_patch(settings, live, patch_func))


async def _run_patch(settings, live, patch_func):
    conn = await lenient_conn(settings)
    tr = conn.transaction()
    await tr.start()
    print('=' * 40)
    try:
        await patch_func(conn, settings=settings, live=live)
    except BaseException as e:
        print('=' * 40)
        await tr.rollback()
        raise RuntimeError('error running patch, rolling back') from e
    else:
        print('=' * 40)
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
async def create_demo_data(conn, settings, **kwargs):
    """
    Create some demo data for manual testing.
    """
    await conn.execute("""
INSERT INTO companies (name, domain) VALUES ('testing', 'localhost:3000');

INSERT INTO users (company, type, status, first_name, last_name, email)
SELECT id, 'admin', 'active', 'joe', 'blogs', 'joe.blogs@example.com' FROM companies;

WITH values_ (name_, slug_) AS (VALUES
  ('Supper Club', 'supper-club'),
  ('Singing', 'singing')
)
INSERT INTO categories (company, name, slug)
SELECT id, name_, slug_ FROM companies, values_;

WITH values_ (cat_slug_, name_, slug_, start_ts_, price_, ticket_limit_) AS (VALUES
  ('supper-club', 'Franks Great Supper', 'franks-great-supper', date '2020-01-28', 30, 40),
  ('supper-club', 'Unpublished Supper', null, date '2020-02-01', 30, 10),
  ('singing', 'Loud Singing', 'loud-singing', date '2020-02-10', 10.2, 200)
)
INSERT INTO events (company, category, name, slug, start_ts, price, ticket_limit)
SELECT c.company, c.id, name_, slug_, start_ts_, price_, ticket_limit_  FROM values_
JOIN categories AS c ON cat_slug_=c.slug;

UPDATE events SET status='published' WHERE slug IS NOT NULL;
UPDATE events SET highlight=TRUE WHERE slug='franks-great-supper';
    """)
