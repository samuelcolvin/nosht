import asyncio

import pytest
from aiohttp.test_utils import teardown_test_loop
from buildpg import asyncpg

from shared.db import create_demo_data as _create_demo_data
from shared.db import prepare_database
from shared.settings import Settings
from web.main import create_app


def pytest_addoption(parser):
    parser.addoption(
        '--reuse-db', action='store_true', default=False, help='keep the existing database if it exists'
    )


@pytest.fixture(scope='session')
def settings():
    return Settings(
        DATABASE_URL='postgres://postgres:waffle@localhost:5432/nosht_testing',
        REDISCLOUD_URL='redis://localhost:6379/1',
    )


@pytest.fixture(scope='session')
def clean_db(request, settings):
    # loop fixture has function scope so can't be used here.
    loop = asyncio.new_event_loop()
    loop.run_until_complete(prepare_database(settings, not request.config.getoption('--reuse-db')))
    teardown_test_loop(loop)


@pytest.yield_fixture
async def db_conn(loop, settings, clean_db):
    conn = await asyncpg.connect_b(dsn=settings.pg_dsn, loop=loop)

    tr = conn.transaction()
    await tr.start()

    yield conn

    await tr.rollback()
    await conn.close()


@pytest.fixture
async def create_demo_data(db_conn, settings):
    await _create_demo_data(db_conn, settings, company_host='127.0.0.1')


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


async def pre_startup_app(app):
    app._subapps[0]['pg'] = FakePgPool(app['test_conn'])


async def post_startup_app(app):
    inner_app = app._subapps[0]
    inner_app['worker']._concurrency_enabled = False
    await inner_app['worker'].startup()


async def shutdown_modify_app(app):
    pass
    # await app['worker'].session.close()


@pytest.fixture
async def cli(settings, db_conn, test_client):
    app = create_app(settings=settings)
    app['test_conn'] = db_conn
    app.on_startup.insert(0, pre_startup_app)
    app.on_startup.append(post_startup_app)
    app.on_shutdown.append(shutdown_modify_app)
    return await test_client(app)
