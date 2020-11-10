import asyncio
import logging
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, web
from aiohttp_session import session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from arq import create_pool_lenient
from buildpg import asyncpg
from cryptography import fernet

from shared.db import prepare_database
from shared.donorfy import DonorfyActor
from shared.emails import EmailActor
from shared.logs import setup_logging
from shared.settings import Settings
from shared.utils import mk_password

from .middleware import csrf_middleware, error_middleware, pg_middleware, user_middleware
from .views import index, ses_webhook, sitemap
from .views.auth import (
    authenticate_token,
    guest_signup,
    host_signup,
    login,
    login_captcha_required,
    login_with,
    logout,
    reset_password_request,
    set_password,
    unsubscribe,
)
from .views.booking import (
    BookFreeTickets,
    CancelReservedTickets,
    ReserveTickets,
    booking_info,
    donating_info,
    waiting_list_add,
    waiting_list_remove,
)
from .views.categories import (
    CategoryBread,
    category_add_image,
    category_delete_image,
    category_images,
    category_public,
    category_set_image,
)
from .views.company import CompanyBread, company_set_footer_link, company_upload
from .views.donate import (
    DonationGiftAid,
    DonationOptionBread,
    PrepareDirectDonation,
    donation_after_prepare,
    donation_image_upload,
    donation_options,
    opt_donations,
)
from .views.emails import clear_email_def, email_def_browse, email_def_edit, email_def_retrieve
from .views.events import (
    CancelTickets,
    EventBread,
    EventClone,
    EventUpdate,
    SetEventStatus,
    SetTicketTypes,
    event_categories,
    event_donations_export,
    event_get,
    event_search,
    event_ticket_types,
    event_tickets,
    event_tickets_export,
    event_updates_sent,
    remove_event_description_image,
    remove_event_secondary_image,
    set_event_description_image,
    set_event_image_existing,
    set_event_image_new,
    set_event_secondary_image,
    switch_highlight,
)
from .views.export import export
from .views.static import get_csp_headers, static_handler
from .views.stripe import get_payment_method_details, stripe_webhook
from .views.users import UserBread, UserSelfBread, switch_user_status, user_actions, user_search, user_tickets

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
        donorfy_actor=DonorfyActor(settings=settings, existing_redis=redis),
        http_client=http_client,
        # custom stripe client to make stripe requests as speedy as possible
        stripe_client=ClientSession(timeout=ClientTimeout(total=9), loop=app.loop),
    )


async def cleanup(app: web.Application):
    await asyncio.gather(
        app['email_actor'].close(),
        app['donorfy_actor'].close(),
        app['pg'].close(),
        app['http_client'].close(),
        app['stripe_client'].close(),
    )
    logging_client = app['logging_client']
    transport = logging_client and logging_client.remote.get_transport()
    transport and await transport.close()


def create_app(*, settings: Settings = None, logging_client=None):
    logging_client = logging_client or setup_logging()
    settings = settings or Settings()

    app = web.Application(logger=None, middlewares=(pg_middleware, user_middleware, csrf_middleware))

    app.update(
        settings=settings,
        auth_fernet=fernet.Fernet(settings.auth_key),
        dummy_password_hash=mk_password(settings.dummy_password, settings),
        logging_client=logging_client,
    )
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)

    app.add_routes(
        [
            web.get(r'/', index, name='index'),
            web.get(r'/sitemap.xml', sitemap, name='sitemap'),
            web.post(r'/ses-webhook/', ses_webhook, name='ses-webhook'),
            web.get(r'/cat/{category}/', category_public, name='category'),
            # event admin
            web.get(r'/events/categories/', event_categories, name='event-categories'),
            *EventBread.routes(r'/events/'),
            web.get(r'/events/search/', event_search, name='event-search'),
            web.post(r'/events/{id:\d+}/set-status/', SetEventStatus.view(), name='event-set-status'),
            web.post(r'/events/{id:\d+}/set-image/new/', set_event_image_new, name='event-set-image-new'),
            web.post(
                r'/events/{id:\d+}/set-image/existing/', set_event_image_existing, name='event-set-image-existing'
            ),
            web.post(
                r'/events/{id:\d+}/set-image/secondary/', set_event_secondary_image, name='event-set-image-secondary'
            ),
            web.post(
                r'/events/{id:\d+}/remove-image/secondary/',
                remove_event_secondary_image,
                name='event-remove-image-secondary',
            ),
            web.post(
                r'/events/{id:\d+}/set-image/description/',
                set_event_description_image,
                name='event-set-image-description',
            ),
            web.post(
                r'/events/{id:\d+}/remove-image/description/',
                remove_event_description_image,
                name='event-remove-image-description',
            ),
            web.post(r'/events/{id:\d+}/clone/', EventClone.view(), name='event-clone'),
            web.get(r'/events/{id:\d+}/tickets/', event_tickets, name='event-tickets'),
            web.post(r'/events/{id:\d+}/tickets/{tid:\d+}/cancel/', CancelTickets.view(), name='event-tickets-cancel'),
            web.get(r'/events/{id:\d+}/tickets/export.csv', event_tickets_export, name='event-tickets-export'),
            web.get(r'/events/{id:\d+}/donations/export.csv', event_donations_export, name='event-donations-export'),
            web.get(r'/events/{id:\d+}/ticket-types/', event_ticket_types, name='event-ticket-types'),
            web.post(r'/events/{id:\d+}/ticket-types/update/', SetTicketTypes.view(), name='update-event-ticket-types'),
            web.post(r'/events/{id:\d+}/reserve/', ReserveTickets.view(), name='event-reserve-tickets'),
            web.post(r'/events/{id:\d+}/updates/send/', EventUpdate.view(), name='event-send-update'),
            web.get(r'/events/{id:\d+}/updates/list/', event_updates_sent, name='event-updates-sent'),
            web.post(r'/events/{id:\d+}/switch-highlight/', switch_highlight, name='event-switch-highlight'),
            web.post(r'/events/{id:\d+}/waiting-list/add/', waiting_list_add, name='event-waiting-list-add'),
            web.get(
                r'/events/{id:\d+}/waiting-list/remove/{user_id:\d+}/',
                waiting_list_remove,
                name='event-waiting-list-remove',
            ),
            # event public views
            web.post(r'/events/book-free/', BookFreeTickets.view(), name='event-book-tickets'),
            web.post(r'/events/cancel-reservation/', CancelReservedTickets.view(), name='event-cancel-reservation'),
            web.get(r'/events/{category}/{event}/', event_get, name='event-get-public'),
            web.get(r'/events/{category}/{event}/booking-info/', booking_info, name='event-booking-info-public'),
            web.get(r'/events/{category}/{event}/donating-info/', donating_info, name='event-donating-info-public'),
            web.get(r'/events/{category}/{event}/{sig}/', event_get, name='event-get-private'),
            web.get(r'/events/{category}/{event}/{sig}/booking-info/', booking_info, name='event-booking-info-private'),
            web.get(
                r'/events/{category}/{event}/{sig}/donating-info/', donating_info, name='event-donating-info-private'
            ),
            # stripe views
            web.post(r'/stripe/webhook/', stripe_webhook, name='stripe-webhook'),
            web.get(
                r'/stripe/payment-method-details/{payment_method}/',
                get_payment_method_details,
                name='payment-method-details',
            ),
            web.post(r'/login/', login, name='login'),
            web.get(r'/login/captcha/', login_captcha_required, name='login-captcha-required'),
            web.post(r'/login/{site:(google|facebook)}/', login_with, name='login-google-facebook'),
            web.post(r'/auth-token/', authenticate_token, name='auth-token'),
            web.post(r'/reset-password/', reset_password_request, name='reset-password-request'),
            web.post(r'/set-password/', set_password, name='set-password'),
            web.post(r'/logout/', logout, name='logout'),
            web.post(r'/signup/guest/{site:(google|facebook|email)}/', guest_signup, name='signup-guest'),
            web.post(r'/signup/host/{site:(google|facebook|email)}/', host_signup, name='signup-host'),
            web.get(r'/unsubscribe/{id:\d+}/', unsubscribe, name='unsubscribe'),
            *CompanyBread.routes(r'/companies/'),
            web.post(r'/companies/upload/{field:(image|logo)}/', company_upload, name='company-upload'),
            web.post(r'/companies/footer-links/set/', company_set_footer_link, name='company-footer-links'),
            web.post(r'/categories/{cat_id:\d+}/add-image/', category_add_image, name='categories-add-image'),
            web.get(r'/categories/{cat_id:\d+}/images/', category_images, name='categories-images'),
            web.post(r'/categories/{cat_id:\d+}/images/set-default/', category_set_image, name='categories-set-image'),
            web.post(r'/categories/{cat_id:\d+}/images/delete/', category_delete_image, name='categories-delete-image'),
            *CategoryBread.routes(r'/categories/'),
            *UserBread.routes(r'/users/'),
            *UserSelfBread.routes(r'/account/', name='account'),
            web.get(r'/users/search/', user_search, name='user-search'),
            web.get(r'/users/{pk:\d+}/actions/', user_actions, name='user-actions'),
            web.get(r'/users/{pk:\d+}/tickets/', user_tickets, name='user-tickets'),
            web.post(r'/users/{pk:\d+}/switch-status/', switch_user_status, name='user-switch-status'),
            web.get(r'/export/{type:(events|categories|users|tickets|donations)}.csv', export, name='export'),
            web.get(r'/email-defs/', email_def_browse, name='email-defs-browse'),
            web.get(r'/email-defs/{trigger}/', email_def_retrieve, name='email-defs-retrieve'),
            web.post(r'/email-defs/{trigger}/edit/', email_def_edit, name='email-defs-edit'),
            web.post(r'/email-defs/{trigger}/clear/', clear_email_def, name='email-defs-clear'),
            # donations
            *DonationOptionBread.routes(r'/donation-options/', name='donation-options'),
            web.get(r'/categories/{cat_id:\d+}/donation-options/', donation_options, name='donation-options'),
            web.post(r'/donation-options/{pk:\d+}/upload-image/', donation_image_upload, name='donation-image-upload'),
            web.get(r'/donation-options/{pk:\d+}/donations/', opt_donations, name='donation-opt-donations'),
            web.post(
                r'/donation-options/{don_opt_id:\d+}/prepare/{event_id:\d+}/',
                donation_after_prepare,
                name='donation-after-prepare',
            ),
            web.post(r'/donation-prepare/{tt_id:\d+}/', PrepareDirectDonation.view(), name='donation-direct-prepare'),
            web.post(r'/donation/{action_id:\d+}/gift-aid/', DonationGiftAid.view(), name='donation-gift-aid'),
        ]
    )

    wrapper_app = web.Application(
        client_max_size=settings.max_request_size,
        middlewares=(
            session_middleware(EncryptedCookieStorage(settings.auth_key, cookie_name='nosht')),
            error_middleware,
        ),
        logger=None,
    )
    wrapper_app.update(
        settings=settings, main_app=app,
    )
    static_dir = settings.custom_static_dir or (Path(__file__).parent / '../../js/build').resolve()
    assert static_dir.exists(), f'js static directory "{static_dir}" does not exists'
    logger.debug('serving static files "%s"', static_dir)
    wrapper_app.update(
        static_dir=static_dir, csp_headers=get_csp_headers(settings),
    )
    wrapper_app.add_subapp(r'/api/', app)
    wrapper_app.add_routes([web.get(r'/{path:.*}', static_handler, name='static')])
    return wrapper_app
