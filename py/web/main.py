import logging
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, web
from aiohttp_session import session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from arq import create_pool_lenient
from buildpg import asyncpg
from cryptography import fernet

from shared.db import prepare_database
from shared.emails import EmailActor
from shared.logs import setup_logging
from shared.settings import Settings
from shared.utils import mk_password

from .middleware import csrf_middleware, error_middleware, host_middleware, pg_middleware
from .views import index
from .views.auth import (authenticate_token, guest_signup, host_signup, login, login_with, logout, set_password,
                         unsubscribe)
from .views.categories import (CategoryBread, category_add_image, category_default_image, category_delete_image,
                               category_images, category_public)
from .views.events import (BuyTickets, CancelReservedTickets, EventBread, ReserveTickets, SetEventStatus, booking_info,
                           event_categories, event_public, event_tickets)
from .views.static import static_handler
from .views.users import UserBread

logger = logging.getLogger('nosht.web')


async def startup(app: web.Application):
    settings: Settings = app['settings']
    await prepare_database(settings, False)
    redis = await create_pool_lenient(settings.redis_settings, app.loop)
    http_client = ClientSession(timeout=ClientTimeout(total=20), loop=app.loop)
    app.update(
        pg=app.get('pg') or await asyncpg.create_pool_b(dsn=settings.pg_dsn, min_size=2),
        redis=redis,
        email_actor=EmailActor(settings=settings, existing_redis=redis, http_client=http_client),
        http_client=http_client,
        # custom stripe client to make stripe requests as speedy as possible
        stripe_client=ClientSession(timeout=ClientTimeout(total=5), loop=app.loop),
    )


async def cleanup(app: web.Application):
    await app['email_actor'].close()
    await app['pg'].close()
    await app['http_client'].close()
    await app['stripe_client'].close()
    logging_client = app['logging_client']
    transport = logging_client and logging_client.remote.get_transport()
    transport and await transport.close()


def create_app(*, settings: Settings=None, logging_client=None):
    logging_client = logging_client or setup_logging()
    settings = settings or Settings()

    app = web.Application(middlewares=(
        session_middleware(EncryptedCookieStorage(settings.auth_key, cookie_name='nosht')),
        pg_middleware,
        host_middleware,
        csrf_middleware,
    ))

    app.update(
        settings=settings,
        auth_fernet=fernet.Fernet(settings.auth_key),
        dummy_password_hash=mk_password(settings.dummy_password, settings),
        logging_client=logging_client,
    )
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)

    app.add_routes([
        web.get('/', index, name='index'),

        web.post('/categories/{cat_id:\d+}/add-image/', category_add_image, name='categories-add-image'),
        web.get('/categories/{cat_id:\d+}/images/', category_images, name='categories-images'),
        web.post('/categories/{cat_id:\d+}/set-default/', category_default_image, name='categories-set-default'),
        web.post('/categories/{cat_id:\d+}/delete/', category_delete_image, name='categories-delete'),
        *CategoryBread.routes('/categories/'),
        web.get('/cat/{category}/', category_public, name='category'),

        web.get('/events/categories/', event_categories, name='event-categories'),
        *EventBread.routes('/events/'),
        web.post('/events/{id:\d+}/set-status/', SetEventStatus.view(), name='event-set-status'),
        web.get('/events/{id:\d+}/booking-info/', booking_info, name='event-booking-info'),
        web.get('/events/{id:\d+}/tickets/', event_tickets, name='event-tickets'),
        web.post('/events/{id:\d+}/reserve/', ReserveTickets.view(), name='event-reserve-tickets'),
        web.post('/events/buy/', BuyTickets.view(), name='event-buy-tickets'),
        web.post('/events/cancel-reservation/', CancelReservedTickets.view(), name='event-cancel-reservation'),
        web.get('/events/{category}/{event}/', event_public, name='event-get'),

        web.post('/login/', login, name='login'),
        web.post('/login/{site:(google|facebook)}/', login_with, name='login-google-facebook'),
        web.post('/auth-token/', authenticate_token, name='auth-token'),
        web.post('/set-password/', set_password, name='set-password'),
        web.post('/logout/', logout, name='logout'),
        web.post('/signup/guest/{site:(google|facebook|email)}/', guest_signup, name='signup-guest'),
        web.post('/signup/host/{site:(google|facebook|email)}/', host_signup, name='signup-host'),

        web.get('/unsubscribe/{id:\d+}/', unsubscribe, name='unsubscribe'),

        *UserBread.routes('/users/'),
    ])

    wrapper_app = web.Application(
        client_max_size=settings.max_request_size,
        middlewares=(error_middleware,),
    )
    wrapper_app.update(
        settings=settings,
        main_app=app,
    )
    this_dir = Path(__file__).parent
    static_dir = (this_dir / '../../js/build').resolve()
    assert static_dir.exists(), f'js static directory "{static_dir}" does not exists'
    logger.debug('serving static files "%s"', static_dir)
    wrapper_app['static_dir'] = static_dir
    wrapper_app.add_subapp('/api/', app)
    wrapper_app.add_routes([
        web.get('/{path:.*}', static_handler, name='static'),
    ])
    return wrapper_app
