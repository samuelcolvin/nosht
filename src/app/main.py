import base64
import logging
from pathlib import Path

import asyncpg
from aiohttp import web
from aiohttp.web_fileresponse import FileResponse
from aiohttp_session import session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from arq import create_pool_lenient

from .db import prepare_database
from .logs import setup_logging
from .middleware import error_middleware
from .settings import Settings
from .views import foobar
from .worker import MainActor

logger = logging.getLogger('events.web')


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


def setup_routes(app, settings):
    app.add_routes([
        web.get('/api/foobar/', foobar, name='foobar'),
    ])

    if settings.on_docker:
        js_build = Path('js/build')
        assert js_build.exists()
        logger.info('js directory exists, serving it')
        index_file = js_build / 'index.html'

        app.add_routes([
            web.get('/', lambda r: FileResponse(index_file)),
            web.static('/', js_build, show_index=True),
        ])


def create_app(*, settings: Settings=None):
    setup_logging()
    settings = settings or Settings()

    secret_key = base64.urlsafe_b64decode(settings.auth_key)
    app = web.Application(middlewares=(
        error_middleware,
        session_middleware(EncryptedCookieStorage(secret_key, cookie_name='events')),
    ))
    app['settings'] = settings
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)

    setup_routes(app, settings)
    return app
