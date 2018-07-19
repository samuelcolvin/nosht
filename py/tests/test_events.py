import json
from datetime import datetime, timedelta

from buildpg import MultipleValues, Values
from pytest_toolbox.comparison import AnyInt, CloseToNow, RegexStr

from shared.db import ActionTypes
from web.utils import decrypt_json, encrypt_json

from .conftest import Factory


async def test_event_public(cli, url, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(
        status='published',
        location_name='Testing Location',
        location_lat=51.5,
        location_lng=-0.5
    )
    cat_slug, event_slug = await db_conn.fetchrow(
        """
        SELECT cat.slug, e.slug
        FROM events AS e
        JOIN categories cat on e.category = cat.id
        WHERE e.id=$1
        """,
        factory.event_id)
    r = await cli.get(url('event-get', category=cat_slug, event=event_slug))
    assert r.status == 200, await r.text()
    data = await r.json()
    # debug(data)
    assert data == {
        'event': {
            'id': factory.event_id,
            'name': 'The Event Name',
            'image': None,
            'short_description': RegexStr('.*'),
            'long_description': RegexStr('.*'),
            'category_content': None,
            'location': {
                'name': 'Testing Location',
                'lat': 51.5,
                'lng': -0.5,
            },
            'price': None,
            'start_ts': '2020-01-28T19:00:00',
            'duration': None,
            'tickets_available': None,
            'host_id': factory.user_id,
            'host_name': 'Frank Spencer',
            'stripe_key': 'stripe_key_xxx',
            'currency': 'gbp',
        },
    }


async def test_event_categories(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()

    await login()
    r = await cli.get(url('event-categories'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'categories': [
            {
                'id': factory.category_id,
                'name': 'Supper Clubs',
                'host_advice': None,
                'event_type': 'ticket_sales',
            },
        ],
    }


async def test_create_event(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await login()

    data = dict(
        name='foobar',
        category=factory.category_id,
        location={
            'lat': 50,
            'lng': 0,
            'name': 'London',
        },
        date={
            'dt': datetime(2020, 2, 1, 19, 0).strftime('%s'),
            'dur': 7200,
        },
        long_description='I love to party'
    )
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    r = await cli.post(url('event-add'), data=json.dumps(data))
    assert r.status == 201, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    data = await r.json()
    event = dict(await db_conn.fetchrow('SELECT * FROM events'))
    assert data == {
        'status': 'ok',
        'pk': event.pop('id'),
    }
    assert event == {
        'category': factory.category_id,
        'status': 'pending',
        'host': factory.user_id,
        'name': 'foobar',
        'slug': 'foobar',
        'highlight': False,
        'start_ts': datetime(2020, 2, 1, 19, 0),
        'duration': timedelta(seconds=7200),
        'short_description': 'I love to party',
        'long_description': 'I love to party',
        'public': True,
        'location_name': 'London',
        'location_lat': 50.0,
        'location_lng': 0.0,
        'price': None,
        'ticket_limit': None,
        'tickets_taken': 0,
        'image': None,
    }


async def test_create_private_all_day(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await login()

    data = dict(
        name='foobar',
        category=factory.category_id,
        public=False,
        location={'lat': 50, 'lng': 0, 'name': 'London'},
        date={
            'dt': datetime(2020, 2, 1, 19, 0).strftime('%s'),
            'dur': None,
        },
        long_description='I love to party'
    )
    r = await cli.post(url('event-add'), data=json.dumps(data))
    assert r.status == 201, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    public, start_ts, duration = await db_conn.fetchrow('SELECT public, start_ts, duration FROM events')
    assert public is False
    assert start_ts == datetime(2020, 2, 1, 0, 0)
    assert duration is None


async def test_not_auth(cli, url, db_conn, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()

    data = dict(
        name='foobar',
        category=factory.category_id,
        location={'lat': 50, 'lng': 0, 'name': 'London'},
        date={'dt': datetime(2020, 2, 1, 19, 0).strftime('%s'), 'dur': None},
        long_description='I love to party'
    )
    r = await cli.post(url('event-add'), data=json.dumps(data))
    assert r.status == 401, await r.text()
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM events')


async def test_edit_event(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()

    event_id, ticket_limit, location_lat = await db_conn.fetchrow('SELECT id, ticket_limit, location_lat FROM events')
    assert ticket_limit is None
    assert location_lat is None
    data = dict(
        ticket_limit=12,
        location={
            'name': 'foobar',
            'lat': 50,
            'lng': 1,
        }
    )
    r = await cli.put(url('event-edit', pk=event_id), data=json.dumps(data))
    assert r.status == 200, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    ticket_limit, location_lat = await db_conn.fetchrow('SELECT ticket_limit, location_lat FROM events')
    assert ticket_limit == 12
    assert location_lat == 50


async def test_set_event_status(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()

    assert 'pending' == await db_conn.fetchval('SELECT status FROM events')

    r = await cli.post(url('event-set-status', id=factory.event_id), data=json.dumps(dict(status='published')))
    assert r.status == 200, await r.text()

    assert 'published' == await db_conn.fetchval('SELECT status FROM events')


async def test_set_event_status_bad(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()

    assert 'pending' == await db_conn.fetchval('SELECT status FROM events')

    r = await cli.post(url('event-set-status', id=factory.event_id), data=json.dumps(dict(status='foobar')))
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'Invalid Data',
        'details': [
            {
                'loc': ['status'],
                'msg': 'value is not a valid enumeration member',
                'type': 'type_error.enum',
            },
        ],
    }

    assert 'pending' == await db_conn.fetchval('SELECT status FROM events')


async def test_booking_info(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(ticket_limit=20)
    await login()

    r = await cli.get(url('event-booking-info', id=factory.event_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'tickets_remaining': None,
        'existing_tickets': 0,
    }


async def test_booking_info_limited(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(ticket_limit=8)
    await login()

    r = await cli.get(url('event-booking-info', id=factory.event_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'tickets_remaining': 8,
        'existing_tickets': 0,
    }


async def test_reserve_tickets(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(first_name=None, last_name=None, email='ticket.buyer@example.com')
    await factory.create_event(status='published', price=10)
    await login(email='ticket.buyer@example.com')

    data = {
        'tickets': [
            {
                't': True,
                'first_name': 'Ticket',
                'last_name': 'Buyer',
                'email': 'ticket.buyer@example.com',
            },
            {
                't': True,
                'first_name': 'Other',
                'last_name': 'Person',
                'email': 'other.person@example.com',
                'extra_info': 'I love to party'
            },
        ]
    }
    r = await cli.post(url('event-reserve-tickets', id=factory.event_id), data=json.dumps(data))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'booking_token': RegexStr('.+'),
        'ticket_count': 2,
        'item_price_cent': 10_00,
        'total_price_cent': 20_00,
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

    users = [dict(r) for r in await db_conn.fetch('SELECT first_name, last_name, email, role FROM users ORDER BY id')]
    debug(users)
    assert users == [
        {
            'first_name': None,
            'last_name': None,
            'email': 'ticket.buyer@example.com',
            'role': 'admin',
        },
        {
            'first_name': None,
            'last_name': None,
            'email': 'other.person@example.com',
            'role': 'guest',
        },
    ]
    users = [dict(r) for r in await db_conn.fetch(
        """
        SELECT event, user_id, first_name, last_name, reserve_action, paid_action, status, extra
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
            'paid_action': None,
            'status': 'reserved',
            'extra': None,
        },
        {
            'event': factory.event_id,
            'user_id': await db_conn.fetchval('SELECT id FROM users WHERE email=$1', 'other.person@example.com'),
            'first_name': 'Other',
            'last_name': 'Person',
            'reserve_action': reserve_action_id,
            'paid_action': None,
            'status': 'reserved',
            'extra': '{"extra_info": "I love to party"}',
        },
    ]


async def test_reserve_0_tickets(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(first_name='Ticket', last_name=None, email='ticket.buyer@example.com')
    await factory.create_event(status='published', price=10)
    await login(email='ticket.buyer@example.com')

    data = {
        'tickets': []
    }
    r = await cli.post(url('event-reserve-tickets', id=factory.event_id), data=json.dumps(data))
    assert r.status == 400, await r.text()


async def test_reserve_tickets_none_left(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(first_name='Ticket', last_name=None, email='ticket.buyer@example.com')
    await factory.create_event(status='published', price=10, ticket_limit=1)
    await login(email='ticket.buyer@example.com')

    data = {
        'tickets': [
            {'t': True, 'email': 'foo1@example.com'},
            {'t': True, 'email': 'foo2@example.com'},
        ]
    }
    r = await cli.post(url('event-reserve-tickets', id=factory.event_id), data=json.dumps(data))
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
    await factory.create_user(first_name='Ticket', last_name=None, email='ticket.buyer@example.com')
    await factory.create_event(status='published', price=10, ticket_limit=1)
    await login(email='ticket.buyer@example.com')

    data = {
        'tickets': [
            {'t': True, 'email': 'foo1@example.com'},
            {'t': True, 'email': 'foo2@example.com'},
        ]
    }
    r = await cli.post(url('event-reserve-tickets', id=factory.event_id), data=json.dumps(data))
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'insufficient tickets remaining',
    }


async def test_event_tickets_admin(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()

    user2_id = await factory.create_user(first_name='guest', last_name='guest', email='guest@example.com')

    r = await db_conn.fetch_b(
        'INSERT INTO actions (:values__names) VALUES :values RETURNING id', values=MultipleValues(
            Values(
                company=factory.company_id,
                user_id=user2_id,
                type=ActionTypes.reserve_tickets
            ),
            Values(
                company=factory.company_id,
                user_id=user2_id,
                type=ActionTypes.buy_tickets
            ),
        )
    )
    reserve_action, paid_action = [r_['id'] for r_ in r]
    ticket_id = await db_conn.fetchval_b(
        'INSERT INTO tickets (:values__names) VALUES :values RETURNING id',
        values=Values(
            event=factory.event_id,
            user_id=user2_id,
            reserve_action=reserve_action,
            paid_action=paid_action,
            status='paid'
        )
    )

    await login()

    r = await cli.get(url('event-tickets', id=factory.event_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'tickets': [
            {
                'ticket_id': ticket_id,
                'extra': None,
                'user_id': user2_id,
                'user_name': 'guest guest',
                'bought_at': CloseToNow(),
                'buyer_id': user2_id,
                'buyer_name': 'guest guest',
            },
        ],
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
    r = await cli.post(url('event-cancel-reservation'), data=json.dumps({'booking_token': booking_token}))
    assert r.status == 200, await r.text()

    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM tickets')
    assert 0 == await db_conn.fetchval('SELECT tickets_taken FROM events')
