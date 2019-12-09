import pytest
from pytest_toolbox.comparison import AnyInt, RegexStr

from shared.actions import ActionTypes
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
        factory.event_id,
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
        factory.event_id,
    )
    r = await cli.get(url('event-booking-info-public', category=cat_slug, event=event_slug))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'tickets_remaining': 8,
        'existing_tickets': 0,
        'ticket_types': [{'id': AnyInt(), 'name': 'Standard', 'price': None}],
    }


async def test_booking_info_inactive(cli, url, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published')
    await login()

    ticket_type2_id = await db_conn.fetchval(
        "INSERT INTO ticket_types (event, name, price) VALUES ($1, 'Different', 42) RETURNING id", factory.event_id
    )

    cat_slug, event_slug = await db_conn.fetchrow(
        'SELECT cat.slug, e.slug FROM events AS e JOIN categories cat on e.category = cat.id WHERE e.id=$1',
        factory.event_id,
    )
    r = await cli.get(url('event-booking-info-public', category=cat_slug, event=event_slug))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'tickets_remaining': None,
        'existing_tickets': 0,
        'ticket_types': [
            {'id': factory.ticket_type_id, 'name': 'Standard', 'price': None},
            {'id': ticket_type2_id, 'name': 'Different', 'price': 42},
        ],
    }

    await db_conn.execute('update ticket_types set active=false where id=$1', ticket_type2_id)
    r = await cli.get(url('event-booking-info-public', category=cat_slug, event=event_slug))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'tickets_remaining': None,
        'existing_tickets': 0,
        'ticket_types': [{'id': factory.ticket_type_id, 'name': 'Standard', 'price': None}],
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
        factory.event_id,
        settings.auth_key,
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
        factory.event_id,
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
        factory.event_id,
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
                'extra_info': 'I love to party',
                'cover_costs': None,
                'allow_marketing': None,
            },
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'booking_token': RegexStr(r'.+'),
        'ticket_count': 2,
        'extra_donated': None,
        'item_price': 10.0,
        'total_price': 20.0,
        'timeout': AnyInt(),
        'client_secret': RegexStr(r'payment_intent_secret_\d+'),
        'action_id': AnyInt(),
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
        dict(r)
        for r in await db_conn.fetch(
            'SELECT first_name, last_name, email, role, allow_marketing FROM users ORDER BY id'
        )
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
    users = [
        dict(r)
        for r in await db_conn.fetch(
            """
        SELECT event, user_id, first_name, last_name, reserve_action, booked_action, status, extra_info
        FROM tickets
        ORDER BY user_id
        """
        )
    ]
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
            {'t': True, 'first_name': 'TT', 'last_name': 'BB', 'email': 'ticket.buyer@example.org'},
            {'t': True},
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'booking_token': RegexStr(r'.+'),
        'ticket_count': 2,
        'extra_donated': None,
        'item_price': 10.0,
        'total_price': 20.0,
        'timeout': AnyInt(),
        'client_secret': RegexStr(r'payment_intent_secret_\d+'),
        'action_id': AnyInt(),
    }

    users = [dict(r) for r in await db_conn.fetch('SELECT first_name, last_name, email, role FROM users ORDER BY id')]
    assert users == [
        {'first_name': 'T', 'last_name': 'B', 'email': 'ticket.buyer@example.org', 'role': 'admin'},
    ]
    users = [
        dict(r)
        for r in await db_conn.fetch(
            """
        SELECT event, user_id, first_name, last_name, reserve_action, booked_action, status, extra_info
        FROM tickets
        ORDER BY user_id
        """
        )
    ]
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
            {'t': True},
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'booking_token': RegexStr(r'.+'),
        'ticket_count': 2,
        'extra_donated': 2.5,
        'item_price': 10.0,
        'total_price': 22.50,
        'timeout': AnyInt(),
        'client_secret': RegexStr(r'payment_intent_secret_\d+'),
        'action_id': AnyInt(),
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
        'tickets': [{'t': True, 'first_name': 'Ticket', 'last_name': 'Buyer', 'email': 'ticket.buyer@example.org'}],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'booking_token': RegexStr(r'.+'),
        'ticket_count': 1,
        'extra_donated': None,
        'item_price': None,
        'total_price': None,
        'timeout': AnyInt(),
        'client_secret': None,
        'action_id': AnyInt(),
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
        'tickets': [{'t': True, 'first_name': 'Ticket', 'last_name': 'Buyer', 'email': 'ticket.buyer@example.org'}],
        'ticket_type': 999,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'Ticket type not found'}


async def test_reserve_tickets_externally_ticketed(cli, url, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published')
    await login()

    await db_conn.execute('update events set external_ticket_url=$1', 'https://www.example.com/thing')

    data = {
        'tickets': [{'t': True}],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'Cannot reserve ticket for an externally ticketed event'}


async def test_reserve_0_tickets(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(first_name='Ticket', last_name=None, email='ticket.buyer@example.org')
    await factory.create_event(status='published', price=10)
    await login(email='ticket.buyer@example.org')

    data = {'tickets': []}
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 400, await r.text()


async def test_reserve_tickets_none_left(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(first_name='Ticket', last_name=None, email='ticket.buyer@example.org')
    await factory.create_event(status='published', price=10, ticket_limit=1)
    await login(email='ticket.buyer@example.org')

    data = {
        'tickets': [{'t': True, 'email': 'foo1@example.org'}, {'t': True, 'email': 'foo2@example.org'}],
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
        'tickets': [{'t': True, 'email': 'foo1@example.org'}, {'t': True, 'email': 'foo2@example.org'}],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'insufficient tickets remaining',
    }


async def test_reserve_tickets_too_many(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', price=10)
    await login()

    data = {
        'tickets': [{'t': True, 'email': f'foo{i}@example.org'} for i in range(30)],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'Too many tickets reserved'}


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


async def test_cancel_reservation_booked(cli, url, db_conn, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=12.5)

    res = await factory.create_reservation()
    await db_conn.execute("UPDATE tickets SET status='booked'")

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM tickets')
    assert 1 == await db_conn.fetchval('SELECT tickets_taken FROM events')

    booking_token = encrypt_json(cli.app['main_app'], res.dict())
    r = await cli.json_post(url('event-cancel-reservation'), data={'booking_token': booking_token})
    assert r.status == 400, await r.text()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM tickets')
    assert 1 == await db_conn.fetchval('SELECT tickets_taken FROM events')


async def test_book_free(cli, url, dummy_server, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=None)

    res: Reservation = await factory.create_reservation()
    app = cli.app['main_app']

    data = dict(booking_token=encrypt_json(app, res.dict()), book_action='book-free-tickets')
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 200, await r.text()

    assert dummy_server.app['log'] == [
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

    data = dict(booking_token=encrypt_json(app, res.dict()), book_action='book-free-tickets')
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
    assert 10 == await db_conn.fetchval('SELECT price FROM tickets')

    data = dict(booking_token=encrypt_json(app, res.dict()), book_action='buy-tickets-offline')
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 200, await r.text()

    assert dummy_server.app['log'] == [
        (
            'email_send_endpoint',
            'Subject: "The Event Name Ticket Confirmation", To: "Frank Spencer <frank@example.org>"',
        ),
    ]
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='book-free-tickets'")
    assert 1 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='buy-tickets-offline'")
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM tickets')
    assert None is await db_conn.fetchval('SELECT price FROM tickets')


async def test_buy_offline_other_admin(cli, url, dummy_server, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=10)

    u2 = await factory.create_user(email='other@example.org')
    await login('other@example.org')

    res: Reservation = await factory.create_reservation(u2)
    app = cli.app['main_app']

    data = dict(booking_token=encrypt_json(app, res.dict()), book_action='buy-tickets-offline')
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 200, await r.text()

    assert dummy_server.app['log'] == [
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

    data = dict(booking_token=encrypt_json(app, res.dict()), book_action='buy-tickets-offline')
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 400, await r.text()
    assert {'message': 'to buy tickets offline you must be the host or an admin'} == await r.json()

    assert dummy_server.app['log'] == []
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='book-free-tickets'")
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='buy-tickets-offline'")
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='buy-tickets'")


async def test_buy_offline_host(cli, url, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await factory.create_event(price=10)

    await login()

    res: Reservation = await factory.create_reservation()
    app = cli.app['main_app']

    data = dict(booking_token=encrypt_json(app, res.dict()), book_action='buy-tickets-offline')
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 200, await r.text()
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='book-free-tickets'")
    assert 1 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='buy-tickets-offline'")
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='buy-tickets'")


async def test_free_repeat(factory: Factory, cli, url, login, db_conn):
    await factory.create_company()
    await factory.create_cat(cover_costs_message='Help!', cover_costs_percentage=5)
    await factory.create_user()
    await factory.create_event(status='published')

    await factory.create_user(email='ticket.buyer@example.org')
    await login(email='ticket.buyer@example.org')

    data = {
        'tickets': [{'t': True, 'email': 'ticket.buyer@example.org'}],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    data = await r.json()

    data = dict(booking_token=data['booking_token'], book_action='book-free-tickets')
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 200, await r.text()

    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'invalid reservation'}

    assert 1 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='book-free-tickets'")
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='buy-tickets-offline'")
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='buy-tickets'")


@pytest.fixture(name='buy_tickets')
def _fix_buy_tickets(cli, url, login):
    async def run(factory: Factory):
        await factory.create_user(email='ticket.buyer@example.org')
        await login(email='ticket.buyer@example.org')

        data = {
            'tickets': [{'t': True, 'email': 'ticket.buyer@example.org', 'cover_costs': True}],
            'ticket_type': factory.ticket_type_id,
        }
        r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
        assert r.status == 200, await r.text()

        action_id = (await r.json())['action_id']
        await factory.fire_stripe_webhook(action_id)

    return run


async def test_cancel_ticket(factory: Factory, cli, url, buy_tickets, db_conn, dummy_server):
    await factory.create_company()
    await factory.create_cat(cover_costs_message='Help!', cover_costs_percentage=5)
    await factory.create_user()
    await factory.create_event(status='published', price=100, ticket_limit=10)

    tickets_remaining = await db_conn.fetchval('SELECT check_tickets_remaining($1, $2)', factory.event_id, 600)
    assert tickets_remaining == 10

    await buy_tickets(factory)

    tickets_remaining = await db_conn.fetchval('SELECT check_tickets_remaining($1, $2)', factory.event_id, 600)
    assert tickets_remaining == 9
    assert 0 == await db_conn.fetchval('select count(*) from actions where type=$1', ActionTypes.cancel_booked_tickets)

    assert 1 == await db_conn.fetchval('select tickets_taken from events where id=$1', factory.event_id)
    ticket_id, status = await db_conn.fetchrow('select id, status from tickets')
    assert status == 'booked'
    r = await cli.json_post(url('event-tickets-cancel', id=factory.event_id, tid=ticket_id), data='{}')
    assert r.status == 200, await r.text()
    assert 0 == await db_conn.fetchval('select tickets_taken from events where id=$1', factory.event_id)

    status = await db_conn.fetchval('select status from tickets where id=$1', ticket_id)
    assert status == 'cancelled'
    assert 1 == await db_conn.fetchval('select count(*) from actions where type=$1', ActionTypes.cancel_booked_tickets)
    assert 'POST stripe_root_url/refunds' not in dummy_server.app['log']


async def test_cancel_ticket_refund(factory: Factory, cli, url, buy_tickets, db_conn, dummy_server):
    await factory.create_company()
    await factory.create_cat(cover_costs_message='Help!', cover_costs_percentage=5)
    await factory.create_user()
    await factory.create_event(status='published', price=100)

    await buy_tickets(factory)

    ticket_id, status = await db_conn.fetchrow('select id, status from tickets')
    assert status == 'booked'
    data = {'refund_amount': 99}
    r = await cli.json_post(url('event-tickets-cancel', id=factory.event_id, tid=ticket_id), data=data)
    assert r.status == 200, await r.text()
    assert 'POST stripe_root_url/refunds' in dummy_server.app['log']


async def test_cancel_ticket_wrong_ticket(factory: Factory, cli, url, buy_tickets, db_conn):
    await factory.create_company()
    await factory.create_cat(cover_costs_message='Help!', cover_costs_percentage=5)
    await factory.create_user()
    await factory.create_event(status='published', price=100)

    await buy_tickets(factory)

    ticket_id = await db_conn.fetchval('select id, status from tickets')
    event2_id = await factory.create_event(status='published', name='Another Event')

    r = await cli.json_post(url('event-tickets-cancel', id=event2_id, tid=ticket_id), data='{}')
    assert r.status == 404, await r.text()
    data = await r.json()
    assert data == {'message': 'Ticket not found'}


async def test_cancel_ticket_refund_free(factory: Factory, cli, url, buy_tickets, db_conn, dummy_server):
    await factory.create_company()
    await factory.create_cat(cover_costs_message='Help!', cover_costs_percentage=5)
    await factory.create_user()
    await factory.create_event(status='published', price=100)

    await buy_tickets(factory)

    v = await db_conn.execute(
        'update actions set type=$1 where type=$2', ActionTypes.book_free_tickets, ActionTypes.buy_tickets
    )
    assert v == 'UPDATE 1'
    ticket_id, status = await db_conn.fetchrow('select id, status from tickets')
    assert status == 'booked'
    data = {'refund_amount': 99}
    r = await cli.json_post(url('event-tickets-cancel', id=factory.event_id, tid=ticket_id), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'Refund not possible unless ticket was bought through stripe.'}
    assert 'POST stripe_root_url/refunds' not in dummy_server.app['log']


async def test_cancel_ticket_refund_too_much(factory: Factory, cli, url, buy_tickets, db_conn, dummy_server):
    await factory.create_company()
    await factory.create_cat(cover_costs_message='Help!', cover_costs_percentage=5)
    await factory.create_user()
    await factory.create_event(status='published', price=100)

    await buy_tickets(factory)

    ticket_id, status = await db_conn.fetchrow('select id, status from tickets')
    assert status == 'booked'
    data = {'refund_amount': 101}
    r = await cli.json_post(url('event-tickets-cancel', id=factory.event_id, tid=ticket_id), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'Refund amount must not exceed 100.00.'}
    assert 'POST stripe_root_url/refunds' not in dummy_server.app['log']


async def test_ticket_expiry(factory: Factory, db_conn, settings):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', price=10, ticket_limit=2)

    res = await factory.create_reservation()
    assert await db_conn.fetchval('select count(*) from tickets') == 1
    ticket_id = await db_conn.fetchval('select id from tickets where reserve_action=$1', res.action_id)

    assert 1 == await db_conn.fetchval('select check_tickets_remaining($1, $2)', factory.event_id, settings.ticket_ttl)

    await db_conn.execute("update tickets set created_ts=now() - '3600 seconds'::interval where id=$1", ticket_id)

    assert 2 == await db_conn.fetchval('select check_tickets_remaining($1, $2)', factory.event_id, settings.ticket_ttl)
    assert await db_conn.fetchval('select count(*) from tickets') == 1

    await db_conn.execute("update tickets set created_ts=now() - '10 days'::interval where id=$1", ticket_id)

    assert 2 == await db_conn.fetchval('select check_tickets_remaining($1, $2)', factory.event_id, settings.ticket_ttl)
    assert await db_conn.fetchval('select count(*) from tickets') == 0


async def test_index_sold_out(factory: Factory, cli, url, buy_tickets, db_conn):
    await factory.create_company()
    await factory.create_cat(slug='testing', cover_costs_percentage=5)
    await factory.create_user()
    await factory.create_event(highlight=True, status='published', price=100, ticket_limit=1)

    assert await db_conn.fetchval('SELECT check_tickets_remaining($1, $2)', factory.event_id, 600) == 1

    r = await cli.get(url('index'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data['highlight_events'][0]['sold_out'] is False

    r = await cli.get(url('category', category='testing'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data['events'][0]['sold_out'] is False

    await buy_tickets(factory)

    assert await db_conn.fetchval('SELECT check_tickets_remaining($1, $2)', factory.event_id, 600) == 0

    r = await cli.get(url('index'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data['highlight_events'][0]['sold_out'] is True

    r = await cli.get(url('category', category='testing'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data['events'][0]['sold_out'] is True


async def test_waiting_list(cli, url, factory: Factory, login, db_conn, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()

    assert await db_conn.fetchval('select count(*) from waiting_list') == 0
    assert len(dummy_server.app['emails']) == 0

    r = await cli.json_post(url('event-waiting-list-add', id=factory.event_id))
    assert r.status == 200, await r.text()
    assert await db_conn.fetchval('select count(*) from waiting_list') == 1
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    assert 'trigger=waiting-list-add' in email['X-SES-MESSAGE-TAGS']

    event_id, user_id = await db_conn.fetchrow('select event, user_id from waiting_list')
    assert event_id == factory.event_id
    assert user_id == factory.user_id

    r = await cli.json_post(url('event-waiting-list-add', id=factory.event_id))
    assert r.status == 200, await r.text()
    assert await db_conn.fetchval('select count(*) from waiting_list') == 1
    assert len(dummy_server.app['emails']) == 1


async def test_waiting_list_book_free(cli, url, login, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=None, status='published')

    await login()

    assert await db_conn.fetchval('select count(*) from waiting_list') == 0

    r = await cli.json_post(url('event-waiting-list-add', id=factory.event_id))
    assert r.status == 200, await r.text()

    assert await db_conn.fetchval('select count(*) from waiting_list') == 1

    res: Reservation = await factory.create_reservation()
    app = cli.app['main_app']

    data = dict(booking_token=encrypt_json(app, res.dict()), book_action='book-free-tickets')
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 200, await r.text()

    assert await db_conn.fetchval('select count(*) from waiting_list') == 0


async def test_waiting_list_buy(cli, url, login, factory: Factory, db_conn, buy_tickets):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=100, status='published')

    await login()

    assert await db_conn.fetchval('select count(*) from waiting_list') == 0

    r = await cli.json_post(url('event-waiting-list-add', id=factory.event_id))
    assert r.status == 200, await r.text()

    assert await db_conn.fetchval('select count(*) from waiting_list') == 1

    await buy_tickets(factory)

    assert await db_conn.fetchval('select count(*) from waiting_list') == 0


async def test_cancel_ticket_waiting_list(factory: Factory, cli, url, buy_tickets, db_conn, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', price=100, ticket_limit=1)

    assert await db_conn.fetchval('SELECT check_tickets_remaining($1, $2)', factory.event_id, 600) == 1
    await buy_tickets(factory)
    assert await db_conn.fetchval('SELECT check_tickets_remaining($1, $2)', factory.event_id, 600) == 0

    ben = await factory.create_user(first_name='ben', last_name='ben', email='ben@example.org')
    await db_conn.execute('insert into waiting_list (event, user_id) values ($1, $2)', factory.event_id, ben)

    ticket_id, status = await db_conn.fetchrow('select id, status from tickets')
    assert status == 'booked'
    r = await cli.json_post(url('event-tickets-cancel', id=factory.event_id, tid=ticket_id), data='{}')
    assert r.status == 200, await r.text()
    assert 0 == await db_conn.fetchval('select tickets_taken from events where id=$1', factory.event_id)

    assert len(dummy_server.app['emails']) == 3
    email = next(e for e in dummy_server.app['emails'] if 'trigger=event-tickets-available' in e['X-SES-MESSAGE-TAGS'])
    assert email['To'] == 'ben ben <ben@example.org>'
    assert email['Subject'] == 'The Event Name - New Tickets Available'
