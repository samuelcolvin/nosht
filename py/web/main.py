import logging
from pathlib import Path

from aiohttp import web
from aiohttp_session import session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from arq import create_pool_lenient
from buildpg import asyncpg
from cryptography import fernet

from shared.db import prepare_database
from shared.logs import setup_logging
from shared.settings import Settings
from shared.utils import mk_password
from shared.worker import MainActor

from .middleware import error_middleware, host_middleware, pg_middleware
from .views.admin import category_add_image, category_images
from .views.auth import authenticate_token, login, logout
from .views.bread import CategoryBread, EventBread, UserBread
from .views.public import category, event, index
from .views.static import static_handler

logger = logging.getLogger('nosht.web')


async def startup(app: web.Application):
    settings: Settings = app['settings']
    await prepare_database(settings, False)
    redis = await create_pool_lenient(settings.redis_settings, app.loop)
    app.update(
        pg=await asyncpg.create_pool_b(dsn=settings.pg_dsn, min_size=2),
        redis=redis,
        worker=MainActor(settings=settings, existing_redis=redis),
    )


async def cleanup(app: web.Application):
    await app['worker'].close(True)
    await app['pg'].close()


def create_app(*, settings: Settings=None):
    setup_logging()
    settings = settings or Settings()

    app = web.Application(middlewares=(
        session_middleware(EncryptedCookieStorage(settings.auth_key, cookie_name='nosht')),
        pg_middleware,
        host_middleware,
    ))

    app.update(
        settings=settings,
        auth_fernet=fernet.Fernet(settings.auth_key),
        dummy_password_hash=mk_password(settings.dummy_password, settings)
    )
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)

    app.add_routes([
        web.get('/', index, name='index'),
        web.get('/cat/{category}/', category, name='category'),
        web.get('/event/{category}/{event}/', event, name='event'),

        web.post('/login/', login, name='login'),
        web.post('/auth-token/', authenticate_token, name='auth-token'),
        web.post('/logout/', logout, name='logout'),

        *CategoryBread.routes('/categories/'),
        web.post('/categories/{cat_id:\d+}/add-image/', category_add_image, name='categories-add-image'),
        web.get('/categories/{cat_id:\d+}/images/', category_images, name='categories-images'),
        *EventBread.routes('/events/'),
        *UserBread.routes('/users/'),
    ])

    wrapper_app = web.Application(
        client_max_size=settings.max_request_size,
        middlewares=(error_middleware,),
    )
    wrapper_app['settings'] = settings
    this_dir = Path(__file__).parent
    static_dir = (this_dir / '../../js/build').resolve()
    assert static_dir.exists()
    logger.debug('serving static files "%s"', static_dir)
    wrapper_app['static_dir'] = static_dir
    wrapper_app.add_subapp('/api/', app)
    wrapper_app.add_routes([
        web.get('/{path:.*}', static_handler, name='static'),
    ])
    return wrapper_app
