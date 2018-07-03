import json
from datetime import datetime, timedelta

from .conftest import Factory


async def test_event_categories(cli, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()

    await login()
    r = await cli.get('/api/event/categories/')
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


async def test_create_event(cli, db_conn, factory: Factory, login):
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
    r = await cli.post('/api/events/add/', data=json.dumps(data))
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
        'location': 'London',
        'location_lat': 50.0,
        'location_lng': 0.0,
        'price': None,
        'ticket_limit': None,
        'tickets_sold': 0,
        'image': None,
    }


async def test_create_private_all_day(cli, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await login()

    data = dict(
        name='foobar',
        category=factory.category_id,
        private=True,
        location={'lat': 50, 'lng': 0, 'name': 'London'},
        date={
            'dt': datetime(2020, 2, 1, 19, 0).strftime('%s'),
            'dur': None,
        },
        long_description='I love to party'
    )
    r = await cli.post('/api/events/add/', data=json.dumps(data))
    assert r.status == 201, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    public, start_ts, duration = await db_conn.fetchrow('SELECT public, start_ts, duration FROM events')
    assert public is False
    assert start_ts == datetime(2020, 2, 1, 0, 0)
    assert duration is None


async def test_not_auth(cli, db_conn, factory: Factory):
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
    r = await cli.post('/api/events/add/', data=json.dumps(data))
    assert r.status == 401, await r.text()
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
