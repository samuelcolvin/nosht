from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from aiohttp import FormData
from pytest_toolbox.comparison import AnyInt, CloseToNow, RegexStr

from web.utils import decrypt_json, encrypt_json

from .conftest import Factory, create_image


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
        'ticket_types': [{'name': 'Standard', 'price': None}],
        'event': {
            'id': factory.event_id,
            'name': 'The Event Name',
            'image': 'https://www.example.org/co.png',
            'short_description': RegexStr('.*'),
            'long_description': RegexStr('.*'),
            'category_content': None,
            'location': {
                'name': 'Testing Location',
                'lat': 51.5,
                'lng': -0.5,
            },
            'start_ts': '2020-01-28T19:00:00',
            'duration': None,
            'tickets_available': None,
            'host_id': factory.user_id,
            'host_name': 'Frank Spencer',
            'stripe_key': 'stripe_key_xxx',
            'ticket_extra_help_text': None,
            'ticket_extra_title': None,
        },
    }


async def test_event_wrong_slug(cli, url, factory: Factory, db_conn):
    await factory.create_company()

    r = await cli.get(url('event-get', category='foobar', event='snap'))
    assert r.status == 404, await r.text()


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


async def test_create_event(cli, url, db_conn, factory: Factory, login, dummy_server):
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
        long_description='# title\nI love to **party**'
    )
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM ticket_types')
    r = await cli.json_post(url('event-add'), data=data)
    assert r.status == 201, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    data = await r.json()
    event = dict(await db_conn.fetchrow('SELECT * FROM events'))
    event_id = event.pop('id')
    assert data == {
        'status': 'ok',
        'pk': event_id,
    }
    assert event == {
        'category': factory.category_id,
        'status': 'published',
        'host': factory.user_id,
        'name': 'foobar',
        'slug': 'foobar',
        'highlight': False,
        'start_ts': datetime(2020, 2, 1, 19, 0),
        'duration': timedelta(seconds=7200),
        'short_description': 'title I love to party',
        'long_description': '# title\nI love to **party**',
        'public': True,
        'location_name': 'London',
        'location_lat': 50.0,
        'location_lng': 0.0,
        'ticket_limit': None,
        'tickets_taken': 0,
        'image': None,
    }
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM ticket_types')
    tt = dict(await db_conn.fetchrow('SELECT event, name, price, slots_used, active FROM ticket_types'))
    assert tt == {
        'event': event_id,
        'name': 'Standard',
        'price': None,
        'slots_used': 1,
        'active': True,
    }
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    # debug(email)
    assert email['Subject'] == 'Update: Event Created'
    assert email['part:text/plain'] == (
        'Testing update:\n'
        '\n'
        'Event "foobar" (Supper Clubs) created by "Frank Spencer" (admin), click the link below to view the event.\n'
        '\n'
        '<div class="button">\n'
        '  <a href="https://127.0.0.1/supper-clubs/foobar/"><span>View Event</span></a>\n'
        '</div>\n'
    )


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
    r = await cli.json_post(url('event-add'), data=data)
    assert r.status == 201, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    public, start_ts, duration = await db_conn.fetchrow('SELECT public, start_ts, duration FROM events')
    assert public is False
    assert start_ts == datetime(2020, 2, 1, 0, 0)
    assert duration is None


async def test_create_event_duplicate_slug(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await login()

    data = dict(
        name='foobar',
        category=factory.category_id,
        long_description='I love to party',
        date={'dt': datetime(2020, 2, 1, 19, 0).strftime('%s'), 'dur': 3600},
    )
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    r = await cli.json_post(url('event-add'), data=data)
    assert r.status == 201, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM events')

    r = await cli.json_post(url('event-add'), data=data)
    assert r.status == 201, await r.text()
    assert 2 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    slug1, slug2 = [r[0] for r in await db_conn.fetch('SELECT slug FROM events ORDER BY id')]
    assert slug1 == 'foobar'
    assert slug2 == RegexStr(r'foobar\-[A-Za-z0-9]{4}')


async def test_create_event_host(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await login()
    await db_conn.fetchval("UPDATE users SET status='pending'")

    data = dict(
        name='foobar',
        category=factory.category_id,
        long_description='I love to party',
        date={'dt': datetime(2020, 2, 1, 19, 0).strftime('%s'), 'dur': 3600},
    )
    r = await cli.json_post(url('event-add'), data=data)
    assert r.status == 201, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    status = await db_conn.fetchval('SELECT status FROM events')
    assert status == 'pending'


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
    r = await cli.json_post(url('event-add'), data=data)
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
    r = await cli.json_post(url('event-edit', pk=event_id), data=data)
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

    r = await cli.json_post(url('event-set-status', id=factory.event_id), data=dict(status='published'))
    assert r.status == 200, await r.text()

    assert 'published' == await db_conn.fetchval('SELECT status FROM events')


async def test_set_event_status_bad(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()

    assert 'pending' == await db_conn.fetchval('SELECT status FROM events')

    r = await cli.json_post(url('event-set-status', id=factory.event_id), data=dict(status='foobar'))
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
        'ticket_types': [{'id': AnyInt(), 'name': 'Standard', 'price': None}],
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
        'ticket_types': [{'id': AnyInt(), 'name': 'Standard', 'price': None}],
    }


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
    assert users == [
        {
            'first_name': None,
            'last_name': None,
            'email': 'ticket.buyer@example.org',
            'role': 'admin',
        },
        {
            'first_name': None,
            'last_name': None,
            'email': 'other.person@example.org',
            'role': 'guest',
        },
    ]
    users = [dict(r) for r in await db_conn.fetch(
        """
        SELECT event, user_id, first_name, last_name, reserve_action, booked_action, status, extra
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
            'extra': None,
        },
        {
            'event': factory.event_id,
            'user_id': await db_conn.fetchval('SELECT id FROM users WHERE email=$1', 'other.person@example.org'),
            'first_name': 'Other',
            'last_name': 'Person',
            'reserve_action': reserve_action_id,
            'booked_action': None,
            'status': 'reserved',
            'extra': '{"extra_info": "I love to party"}',
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
        'item_price_cent': 10_00,
        'total_price_cent': 20_00,
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
        SELECT event, user_id, first_name, last_name, reserve_action, booked_action, status, extra
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
            'extra': None,
        },
        {
            'event': factory.event_id,
            'user_id': None,
            'first_name': None,
            'last_name': None,
            'reserve_action': reserve_action_id,
            'booked_action': None,
            'status': 'reserved',
            'extra': None,
        },
    ]


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


async def test_event_tickets_admin(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=10)

    user2_id = await factory.create_user(first_name='guest', last_name='guest', email='guest@example.org')

    res = await factory.create_reservation(user2_id)
    await factory.buy_tickets(res, user2_id)

    await login()

    r = await cli.get(url('event-tickets', id=factory.event_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'tickets': [
            {
                'ticket_id': await db_conn.fetchval('SELECT id from tickets'),
                'ticket_type_name': 'Standard',
                'ticket_type_id': await db_conn.fetchval('SELECT id from ticket_types'),
                'price': 10,
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
    r = await cli.json_post(url('event-cancel-reservation'), data={'booking_token': booking_token})
    assert r.status == 200, await r.text()

    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM tickets')
    assert 0 == await db_conn.fetchval('SELECT tickets_taken FROM events')


async def test_image_existing(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()
    r = await cli.json_post(url('event-set-image-existing', id=factory.event_id),
                            data={'image': 'https://testingbucket.example.org/testing.png'})
    assert r.status == 200, await r.text()
    assert 'https://testingbucket.example.org/testing.png' == await db_conn.fetchval('SELECT image FROM events')

    assert len(dummy_server.app['log']) == 1


async def test_image_existing_bad(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()
    r = await cli.json_post(url('event-set-image-existing', id=factory.event_id),
                            data={'image': 'https://foobar.example.org/testing.png'})
    assert r.status == 400, await r.text()
    assert None is await db_conn.fetchval('SELECT image FROM events')

    assert len(dummy_server.app['log']) == 1


async def test_image_existing_wrong_host(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    user_id = await factory.create_user(email='admin@example.org')
    await factory.create_event(host_user_id=user_id)
    await login()
    r = await cli.json_post(url('event-set-image-existing', id=factory.event_id),
                            data={'image': 'https://testingbucket.example.org/testing.png'})
    assert r.status == 403, await r.text()
    assert None is await db_conn.fetchval('SELECT image FROM events')
    data = await r.json()
    assert data == {'message': 'you may not edit this event'}

    assert len(dummy_server.app['log']) == 1


async def test_image_existing_wrong_id(cli, url, factory: Factory, login, dummy_server):
    await factory.create_company()
    await factory.create_user()
    await login()
    r = await cli.json_post(url('event-set-image-existing', id=1),
                            data={'image': 'https://testingbucket.example.org/testing.png'})
    assert r.status == 404, await r.text()
    assert len(dummy_server.app['log']) == 1


async def test_image_existing_delete(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(image='https://testingbucket.example.org/foobar.png')
    await login()

    r = await cli.json_post(url('event-set-image-existing', id=factory.event_id),
                            data={'image': 'https://testingbucket.example.org/testing.png'})
    assert r.status == 200, await r.text()
    assert 'https://testingbucket.example.org/testing.png' == await db_conn.fetchval('SELECT image FROM events')

    assert len(dummy_server.app['log']) == 3
    assert set(dummy_server.app['log'][1:]) == {
        'DELETE aws_endpoint_url/testingbucket.example.org/foobar.png/main.jpg',
        'DELETE aws_endpoint_url/testingbucket.example.org/foobar.png/thumb.jpg'
    }


async def test_image_new(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(image='https://testingbucket.example.org/foobar.png')
    await login()

    data = FormData()
    data.add_field('image', create_image(), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('event-set-image-new', id=factory.event_id),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        }
    )
    assert r.status == 200, await r.text()

    img_path = await db_conn.fetchval('SELECT image FROM events')
    assert img_path == RegexStr(r'https://testingbucket.example.org/tests/testing/supper-clubs/the-event-name/\w+')

    # debug(dummy_server.app['log'])
    assert len(dummy_server.app['log']) == 5

    log = sorted(dummy_server.app['log'][1:])
    assert log[0] == 'DELETE aws_endpoint_url/testingbucket.example.org/foobar.png/main.jpg'
    assert log[1] == 'DELETE aws_endpoint_url/testingbucket.example.org/foobar.png/thumb.jpg'
    assert log[2] == RegexStr(r'PUT aws_endpoint_url/testingbucket.example.org/tests/testing/supper-clubs/'
                              r'the-event-name/\w+?/main.jpg')
    assert log[3] == RegexStr(r'PUT aws_endpoint_url/testingbucket.example.org/tests/testing/supper-clubs/'
                              r'the-event-name/\w+?/thumb.jpg')


async def test_add_ticket_type(cli, url, factory: Factory, db_conn, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM ticket_types')
    r = await cli.get(url('event-ticket-types', id=factory.event_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    ticket_types = data['ticket_types']
    assert len(ticket_types) == 1
    ticket_types.append({
        'name': 'Foobar',
        'price': 123.5,
        'slots_used': 2,
        'active': False,
    })

    r = await cli.json_post(url('update-event-ticket-types', id=factory.event_id), data={'ticket_types': ticket_types})
    assert r.status == 200, await r.text()

    ticket_types = [dict(r) for r in await db_conn.fetch('SELECT * FROM ticket_types')]
    assert ticket_types == [
        {
            'id': AnyInt(),
            'event': factory.event_id,
            'name': 'Standard',
            'price': None,
            'slots_used': 1,
            'active': True,
        },
        {
            'id': AnyInt(),
            'event': factory.event_id,
            'name': 'Foobar',
            'price': Decimal('123.50'),
            'slots_used': 2,
            'active': False,
        },
    ]


async def test_delete_ticket_type(cli, url, factory: Factory, db_conn, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()

    tt_id = await db_conn.fetchval('SELECT id FROM ticket_types')
    data = {'ticket_types': [{'name': 'xxx', 'price': 12.3, 'slots_used': 50, 'active': True}]}
    r = await cli.json_post(url('update-event-ticket-types', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()

    ticket_types = [dict(r) for r in await db_conn.fetch('SELECT * FROM ticket_types')]
    assert ticket_types == [
        {
            'id': AnyInt(),
            'event': factory.event_id,
            'name': 'xxx',
            'price': Decimal('12.30'),
            'slots_used': 50,
            'active': True,
        },
    ]
    assert ticket_types[0]['id'] != tt_id


async def test_delete_wrong_ticket_type(cli, url, factory: Factory, db_conn, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await factory.create_reservation()
    await login()

    data = {'ticket_types': [{'name': 'xxx', 'price': 12.3, 'slots_used': 50, 'active': True}]}
    r = await cli.json_post(url('update-event-ticket-types', id=factory.event_id), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'ticket types deleted which have ticket associated with them',
    }


async def test_edit_ticket_type(cli, url, factory: Factory, db_conn, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()

    tt_id = await db_conn.fetchval('SELECT id FROM ticket_types')
    data = {
        'ticket_types': [
            {
                'id': tt_id,
                'name': 'xxx',
                'price': 12.3,
                'slots_used': 50,
                'active': True,
            }
        ]
    }

    r = await cli.json_post(url('update-event-ticket-types', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    ticket_types = [dict(r) for r in await db_conn.fetch('SELECT * FROM ticket_types')]
    assert ticket_types == [
        {
            'id': tt_id,
            'event': factory.event_id,
            'name': 'xxx',
            'price': Decimal('12.30'),
            'slots_used': 50,
            'active': True,
        },
    ]


@pytest.mark.parametrize('get_input,response_contains', [
    (
        lambda event_id, tt_id: (event_id, [{'id': tt_id, 'name': 'foobar'}]),
        '"msg": "field required"'
    ),
    (
        lambda event_id, tt_id: (event_id + 1, [{'id': tt_id, 'name': 'x', 'slots_used': 1, 'active': True}]),
        '"message": "wrong ticket updated"'
    ),
    (
        lambda event_id, tt_id: (event_id + 1, [{'id': tt_id, 'name': 'x', 'slots_used': 1, 'active': False}]),
        '"msg": "at least 1 ticket type must be active"'
    ),
])
async def test_invalid_ticket_updates(get_input, response_contains, cli, url, factory: Factory, db_conn, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()

    tt_id = await db_conn.fetchval('SELECT id FROM ticket_types')
    event_id, ticket_types = get_input(factory.event_id, tt_id)

    r = await cli.json_post(url('update-event-ticket-types', id=event_id), data={'ticket_types': ticket_types})
    assert r.status == 400, await r.text()
    assert response_contains in await r.text()
