import base64
import logging
from pathlib import Path

import asyncpg
from aiohttp import web
from aiohttp_session import session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from arq import create_pool_lenient

from shared.db import prepare_database
from shared.logs import setup_logging
from shared.settings import Settings
from shared.worker import MainActor

from .middleware import error_middleware
from .views import foobar
from .views.static import static_handler

logger = logging.getLogger('nosht.web')


async def startup(app: web.Application):
    settings: Settings = app['settings']
    await prepare_database(settings, False)
    redis = await create_pool_lenient(settings.redis_settings, app.loop)
    app.update(
        pg=await asyncpg.create_pool(dsn=settings.pg_dsn, min_size=2),
        redis=redis,
        worker=MainActor(settings=settings, existing_redis=redis),
    )


async def cleanup(app: web.Application):
    await app['worker'].close(True)
    await app['pg'].close()


def setup_routes(app):
    app.add_routes([
        web.get('/api/foobar/', foobar, name='foobar'),
        web.get('/{path:.*}', static_handler, name='static'),
    ])


def create_app(*, settings: Settings=None):
    setup_logging()
    settings = settings or Settings()

    secret_key = base64.urlsafe_b64decode(settings.auth_key)
    app = web.Application(middlewares=(
        error_middleware,
        session_middleware(EncryptedCookieStorage(secret_key, cookie_name='nosht')),
    ))

    static_dir = Path('js/build').resolve()
    logger.info('serving static files "%s"', static_dir)
    assert static_dir.exists()
    app.update(
        settings=settings,
        static_dir=static_dir,
    )
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)

    setup_routes(app)
    return app
