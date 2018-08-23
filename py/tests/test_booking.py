from pytest_toolbox.comparison import AnyInt, RegexStr

from web.stripe import Reservation
from web.utils import decrypt_json, encrypt_json

from .conftest import Factory


async def test_booking_info(cli, url, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(ticket_limit=20, status='published')
    await login()

    cat_slug, event_slug = await db_conn.fetchrow(
        'SELECT cat.slug, e.slug FROM events AS e JOIN categories cat on e.category = cat.id WHERE e.id=$1',
        factory.event_id
    )
    r = await cli.get(url('event-booking-info-public', category=cat_slug, event=event_slug))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'tickets_remaining': None,
        'existing_tickets': 0,
        'ticket_types': [{'id': AnyInt(), 'name': 'Standard', 'price': None}],
    }


async def test_booking_info_limited(cli, url, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(ticket_limit=8, status='published')
    await login()

    cat_slug, event_slug = await db_conn.fetchrow(
        'SELECT cat.slug, e.slug FROM events AS e JOIN categories cat on e.category = cat.id WHERE e.id=$1',
        factory.event_id
    )
    r = await cli.get(url('event-booking-info-public', category=cat_slug, event=event_slug))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'tickets_remaining': 8,
        'existing_tickets': 0,
        'ticket_types': [{'id': AnyInt(), 'name': 'Standard', 'price': None}],
    }


async def test_booking_info_sig(cli, url, factory: Factory, login, settings, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(ticket_limit=20, status='published', public=False)
    await login()

    event_link = await db_conn.fetchval(
        """
        SELECT event_link(cat.slug, e.slug, e.public, $2)
        FROM events AS e JOIN categories cat on e.category = cat.id WHERE e.id=$1
        """,
        factory.event_id, settings.auth_key
    )
    _, cat_slug, event_slug, sig = event_link.strip('/').split('/')
    r = await cli.get(url('event-booking-info-private', category=cat_slug, event=event_slug, sig=sig))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'tickets_remaining': None,
        'existing_tickets': 0,
        'ticket_types': [{'id': AnyInt(), 'name': 'Standard', 'price': None}],
    }


async def test_booking_info_private(cli, url, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(ticket_limit=20, status='published', public=False)
    await login()

    cat_slug, event_slug = await db_conn.fetchrow(
        'SELECT cat.slug, e.slug FROM events AS e JOIN categories cat on e.category = cat.id WHERE e.id=$1',
        factory.event_id
    )
    r = await cli.get(url('event-booking-info-public', category=cat_slug, event=event_slug))
    assert r.status == 404, await r.text()


async def test_booking_info_sig_wrong(cli, url, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(ticket_limit=20, status='published', public=False)
    await login()

    cat_slug, event_slug = await db_conn.fetchrow(
        'SELECT cat.slug, e.slug FROM events AS e JOIN categories cat on e.category = cat.id WHERE e.id=$1',
        factory.event_id
    )
    r = await cli.get(url('event-booking-info-private', category=cat_slug, event=event_slug, sig='xxx'))
    assert r.status == 404, await r.text()


async def test_reserve_tickets(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(first_name=None, last_name=None, email='ticket.buyer@example.org')
    await factory.create_event(status='published', price=10)
    await login(email='ticket.buyer@example.org')

    data = {
        'tickets': [
            {
                't': True,
                'first_name': 'Ticket',
                'last_name': 'Buyer',
                'email': 'ticket.buyer@example.org',
                'allow_marketing': True,
            },
            {
                't': True,
                'first_name': 'Other',
                'last_name': 'Person',
                'email': 'other.person@example.org',
                'extra_info': 'I love to party'
            },
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'booking_token': RegexStr('.+'),
        'ticket_count': 2,
        'extra_donated': None,
        'item_price': 10.0,
        'total_price': 20.0,
        'timeout': AnyInt(),
    }
    booking_token = decrypt_json(cli.app['main_app'], data['booking_token'].encode())
    reserve_action_id = await db_conn.fetchval("SELECT id FROM actions WHERE type='reserve-tickets'")
    assert booking_token == {
        'user_id': factory.user_id,
        'action_id': reserve_action_id,
        'event_id': factory.event_id,
        'price_cent': 20_00,
        'ticket_count': 2,
        'event_name': 'The Event Name',
    }

    users = [
        dict(r) for r in
        await db_conn.fetch('SELECT first_name, last_name, email, role, allow_marketing FROM users ORDER BY id')
    ]
    assert users == [
        {
            'first_name': None,
            'last_name': None,
            'email': 'ticket.buyer@example.org',
            'role': 'admin',
            'allow_marketing': True,
        },
        {
            'first_name': None,
            'last_name': None,
            'email': 'other.person@example.org',
            'role': 'guest',
            'allow_marketing': False,
        },
    ]
    users = [dict(r) for r in await db_conn.fetch(
        """
        SELECT event, user_id, first_name, last_name, reserve_action, booked_action, status, extra_info
        FROM tickets
        ORDER BY user_id
        """
    )]
    assert users == [
        {
            'event': factory.event_id,
            'user_id': factory.user_id,
            'first_name': 'Ticket',
            'last_name': 'Buyer',
            'reserve_action': reserve_action_id,
            'booked_action': None,
            'status': 'reserved',
            'extra_info': None,
        },
        {
            'event': factory.event_id,
            'user_id': await db_conn.fetchval('SELECT id FROM users WHERE email=$1', 'other.person@example.org'),
            'first_name': 'Other',
            'last_name': 'Person',
            'reserve_action': reserve_action_id,
            'booked_action': None,
            'status': 'reserved',
            'extra_info': 'I love to party',
        },
    ]


async def test_reserve_tickets_no_name(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(first_name='T', last_name='B', email='ticket.buyer@example.org')
    await factory.create_event(status='published', price=10)
    await login(email='ticket.buyer@example.org')

    data = {
        'tickets': [
            {
                't': True,
                'first_name': 'TT',
                'last_name': 'BB',
                'email': 'ticket.buyer@example.org',
            },
            {
                't': True,
            },
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'booking_token': RegexStr('.+'),
        'ticket_count': 2,
        'extra_donated': None,
        'item_price': 10.0,
        'total_price': 20.0,
        'timeout': AnyInt(),
    }

    users = [dict(r) for r in await db_conn.fetch('SELECT first_name, last_name, email, role FROM users ORDER BY id')]
    assert users == [
        {
            'first_name': 'T',
            'last_name': 'B',
            'email': 'ticket.buyer@example.org',
            'role': 'admin',
        },
    ]
    users = [dict(r) for r in await db_conn.fetch(
        """
        SELECT event, user_id, first_name, last_name, reserve_action, booked_action, status, extra_info
        FROM tickets
        ORDER BY user_id
        """
    )]
    reserve_action_id = await db_conn.fetchval("SELECT id FROM actions WHERE type='reserve-tickets'")
    assert users == [
        {
            'event': factory.event_id,
            'user_id': factory.user_id,
            'first_name': 'TT',
            'last_name': 'BB',
            'reserve_action': reserve_action_id,
            'booked_action': None,
            'status': 'reserved',
            'extra_info': None,
        },
        {
            'event': factory.event_id,
            'user_id': None,
            'first_name': None,
            'last_name': None,
            'reserve_action': reserve_action_id,
            'booked_action': None,
            'status': 'reserved',
            'extra_info': None,
        },
    ]


async def test_reserve_tickets_cover_costs(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat(cover_costs_message='Help!', cover_costs_percentage=12.5)
    await factory.create_user(first_name=None, last_name=None, email='ticket.buyer@example.org')
    await factory.create_event(status='published', price=10)
    await login(email='ticket.buyer@example.org')

    data = {
        'tickets': [
            {
                't': True,
                'first_name': 'Ticket',
                'last_name': 'Buyer',
                'email': 'ticket.buyer@example.org',
                'cover_costs': True,
            },
            {
                't': True,
            },
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'booking_token': RegexStr('.+'),
        'ticket_count': 2,
        'extra_donated': 2.5,
        'item_price': 10.0,
        'total_price': 22.50,
        'timeout': AnyInt(),
    }
    assert decrypt_json(cli.app['main_app'], data['booking_token'].encode()) == {
        'user_id': factory.user_id,
        'action_id': AnyInt(),
        'event_id': factory.event_id,
        'price_cent': 22_50,
        'ticket_count': 2,
        'event_name': 'The Event Name',
    }


async def test_reserve_tickets_free(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published')
    await login()

    data = {
        'tickets': [
            {
                't': True,
                'first_name': 'Ticket',
                'last_name': 'Buyer',
                'email': 'ticket.buyer@example.org',
            },
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'booking_token': RegexStr('.+'),
        'ticket_count': 1,
        'extra_donated': None,
        'item_price': None,
        'total_price': None,
        'timeout': AnyInt(),
    }
    assert decrypt_json(cli.app['main_app'], data['booking_token'].encode()) == {
        'user_id': factory.user_id,
        'action_id': AnyInt(),
        'event_id': factory.event_id,
        'price_cent': None,
        'ticket_count': 1,
        'event_name': 'The Event Name',
    }


async def test_reserve_tickets_wrong_type(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published')
    await login()

    data = {
        'tickets': [
            {
                't': True,
                'first_name': 'Ticket',
                'last_name': 'Buyer',
                'email': 'ticket.buyer@example.org',
            },
        ],
        'ticket_type': 999,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'Ticket type not found'}


async def test_reserve_0_tickets(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(first_name='Ticket', last_name=None, email='ticket.buyer@example.org')
    await factory.create_event(status='published', price=10)
    await login(email='ticket.buyer@example.org')

    data = {
        'tickets': []
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 400, await r.text()


async def test_reserve_tickets_none_left(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(first_name='Ticket', last_name=None, email='ticket.buyer@example.org')
    await factory.create_event(status='published', price=10, ticket_limit=1)
    await login(email='ticket.buyer@example.org')

    data = {
        'tickets': [
            {'t': True, 'email': 'foo1@example.org'},
            {'t': True, 'email': 'foo2@example.org'},
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 470, await r.text()
    data = await r.json()
    assert data == {
        'message': 'only 1 tickets remaining',
        'tickets_remaining': 1,
    }


async def test_reserve_tickets_none_left_no_precheck(cli, url, factory: Factory, login, settings):
    settings.ticket_reservation_precheck = False
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(first_name='Ticket', last_name=None, email='ticket.buyer@example.org')
    await factory.create_event(status='published', price=10, ticket_limit=1)
    await login(email='ticket.buyer@example.org')

    data = {
        'tickets': [
            {'t': True, 'email': 'foo1@example.org'},
            {'t': True, 'email': 'foo2@example.org'},
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'insufficient tickets remaining',
    }


async def test_cancel_reservation(cli, url, db_conn, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=12.5)

    res = await factory.create_reservation()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM tickets')
    assert 1 == await db_conn.fetchval('SELECT tickets_taken FROM events')

    booking_token = encrypt_json(cli.app['main_app'], res.dict())
    r = await cli.json_post(url('event-cancel-reservation'), data={'booking_token': booking_token})
    assert r.status == 200, await r.text()

    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM tickets')
    assert 0 == await db_conn.fetchval('SELECT tickets_taken FROM events')


async def test_book_free(cli, url, dummy_server, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=None)

    res: Reservation = await factory.create_reservation()
    app = cli.app['main_app']

    data = dict(
        booking_token=encrypt_json(app, res.dict()),
        book_action='book-free-tickets',
        grecaptcha_token='__ok__',
    )
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 200, await r.text()

    assert dummy_server.app['log'] == [
        ('grecaptcha', '__ok__'),
        (
            'email_send_endpoint',
            'Subject: "The Event Name Ticket Confirmation", To: "Frank Spencer <frank@example.org>"',
        ),
    ]
    assert 1 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='book-free-tickets'")
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='buy-tickets-offline'")


async def test_book_free_with_price(cli, url, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=10)

    res: Reservation = await factory.create_reservation()
    app = cli.app['main_app']

    data = dict(
        booking_token=encrypt_json(app, res.dict()),
        book_action='book-free-tickets',
        grecaptcha_token='__ok__',
    )
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 400, await r.text()

    data = await r.json()
    assert data == {
        'message': 'booking not free',
    }


async def test_buy_offline(cli, url, dummy_server, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=10)

    await login()

    res: Reservation = await factory.create_reservation()
    app = cli.app['main_app']

    data = dict(
        booking_token=encrypt_json(app, res.dict()),
        book_action='buy-tickets-offline',
        grecaptcha_token='__ok__',
    )
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 200, await r.text()

    assert dummy_server.app['log'] == [
        ('grecaptcha', '__ok__'),
        ('grecaptcha', '__ok__'),
        (
            'email_send_endpoint',
            'Subject: "The Event Name Ticket Confirmation", To: "Frank Spencer <frank@example.org>"',
        ),
    ]
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='book-free-tickets'")
    assert 1 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='buy-tickets-offline'")


async def test_buy_offline_other_admin(cli, url, dummy_server, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=10)

    u2 = await factory.create_user(email='other@example.org')
    await login('other@example.org')

    res: Reservation = await factory.create_reservation(u2)
    app = cli.app['main_app']

    data = dict(
        booking_token=encrypt_json(app, res.dict()),
        book_action='buy-tickets-offline',
        grecaptcha_token='__ok__',
    )
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 200, await r.text()

    assert dummy_server.app['log'] == [
        ('grecaptcha', '__ok__'),
        ('grecaptcha', '__ok__'),
        (
            'email_send_endpoint',
            'Subject: "The Event Name Ticket Confirmation", To: "Frank Spencer <other@example.org>"',
        ),
    ]
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='book-free-tickets'")
    assert 1 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='buy-tickets-offline'")


async def test_buy_offline_other_not_admin(cli, url, dummy_server, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=10)

    u2 = await factory.create_user(email='other@example.org', role='host')
    await login('other@example.org')

    res: Reservation = await factory.create_reservation(u2)
    app = cli.app['main_app']

    data = dict(
        booking_token=encrypt_json(app, res.dict()),
        book_action='buy-tickets-offline',
        grecaptcha_token='__ok__',
    )
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 400, await r.text()
    assert {'message': 'to buy tickets offline you must be the host or an admin'} == await r.json()

    assert dummy_server.app['log'] == [
        ('grecaptcha', '__ok__'),
        ('grecaptcha', '__ok__'),
    ]
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='book-free-tickets'")
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='buy-tickets-offline'")
