import json
from datetime import datetime, timedelta

from pytest_toolbox.comparison import RegexStr

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
            'stripe_key': None,
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
