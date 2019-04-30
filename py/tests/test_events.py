from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from aiohttp import FormData
from pytest_toolbox.comparison import AnyInt, CloseToNow, RegexStr

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
        'SELECT cat.slug, e.slug FROM events AS e JOIN categories cat on e.category = cat.id WHERE e.id=$1',
        factory.event_id
    )
    r = await cli.get(url('event-get-public', category=cat_slug, event=event_slug))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'ticket_types': [{'name': 'Standard', 'price': None}],
        'event': {
            'id': factory.event_id,
            'category_id': factory.category_id,
            'name': 'The Event Name',
            'image': 'https://www.example.org/main.png',
            'secondary_image': None,
            'short_description': RegexStr(r'.*'),
            'long_description': RegexStr(r'.*'),
            'external_ticket_url': None,
            'category_content': None,
            'location': {
                'name': 'Testing Location',
                'lat': 51.5,
                'lng': -0.5,
            },
            'start_ts': '2020-06-28T19:00:00',
            'tz': 'BST',
            'duration': 3600,
            'tickets_available': None,
            'host_id': factory.user_id,
            'host_name': 'Frank Spencer',
            'ticket_extra_help_text': None,
            'ticket_extra_title': None,
            'allow_marketing_message': None,
            'booking_trust_message': None,
            'cover_costs_message': None,
            'cover_costs_percentage': None,
            'terms_and_conditions_message': None,
        },
    }


async def test_event_wrong_slug(cli, url, factory: Factory):
    await factory.create_company()

    r = await cli.get(url('event-get-public', category='foobar', event='snap'))
    assert r.status == 404, await r.text()


async def test_event_not_public(cli, url, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(public=False, status='published')

    cat_slug, event_slug = await db_conn.fetchrow(
        'SELECT cat.slug, e.slug FROM events AS e JOIN categories cat on e.category = cat.id WHERE e.id=$1',
        factory.event_id
    )
    r = await cli.get(url('event-get-public', category=cat_slug, event=event_slug))
    assert r.status == 404, await r.text()
    assert {'message': 'event not found'} == await r.json()


async def test_private_event_good(cli, url, factory: Factory, db_conn, settings):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(public=False, status='published')

    event_link = await db_conn.fetchval(
        """
        SELECT event_link(cat.slug, e.slug, e.public, $2)
        FROM events AS e JOIN categories cat on e.category = cat.id WHERE e.id=$1
        """,
        factory.event_id, settings.auth_key
    )
    _, cat_slug, event_slug, sig = event_link.strip('/').split('/')
    r = await cli.get(url('event-get-private', category=cat_slug, event=event_slug, sig=sig))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data['event']['id'] == factory.event_id


async def test_private_event_bad_sig(cli, url, factory: Factory, db_conn, settings):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(public=False, status='published')

    event_link = await db_conn.fetchval(
        """
        SELECT event_link(cat.slug, e.slug, e.public, $2)
        FROM events AS e JOIN categories cat on e.category = cat.id WHERE e.id=$1
        """,
        factory.event_id, settings.auth_key
    )
    _, cat_slug, event_slug, sig = event_link.strip('/').split('/')
    r = await cli.get(url('event-get-private', category=cat_slug, event=event_slug, sig=sig + 'x'))
    assert r.status == 404, await r.text()
    assert {'message': 'event not found'} == await r.json()


async def test_bread_browse(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(public=False, status='published')
    await factory.create_event(name='second event')

    await login()

    r = await cli.get(url('event-browse'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'items': [
            {
                'id': AnyInt(),
                'name': 'second event',
                'category': 'Supper Clubs',
                'status': 'pending',
                'highlight': False,
                'start_ts': '2020-06-28T19:00:00',
                'duration': 3600,
            },
            {
                'id': AnyInt(),
                'name': 'The Event Name',
                'category': 'Supper Clubs',
                'status': 'published',
                'highlight': False,
                'start_ts': '2020-06-28T19:00:00',
                'duration': 3600,
            },
        ],
        'count': 2,
        'pages': 1,
    }


async def test_bread_retrieve(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(public=False, status='published', short_description='xxx', long_description='yyy')

    await login()

    r = await cli.get(url('event-retrieve', pk=factory.event_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'id': factory.event_id,
        'name': 'The Event Name',
        'category': 'Supper Clubs',
        'status': 'published',
        'highlight': False,
        'start_ts': '2020-06-28T19:00:00',
        'timezone': 'Europe/London',
        'duration': 3600,
        'cat_id': factory.category_id,
        'public': False,
        'image': None,
        'secondary_image': None,
        'ticket_limit': None,
        'location_name': None,
        'location_lat': None,
        'location_lng': None,
        'short_description': 'xxx',
        'long_description': 'yyy',
        'external_ticket_url': None,
        'host': factory.user_id,
        'host_name': 'Frank Spencer',
        'link': '/pvt/supper-clubs/the-event-name/8d2a9334aa29f2151668a54433df2e9d/',
    }


async def test_bread_browse_host(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await factory.create_event()

    u2 = await factory.create_user(email='u2@example.org')
    await factory.create_event(host_user_id=u2, name='another event')

    await login()

    r = await cli.get(url('event-browse'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data['count'] == 1
    assert data['pages'] == 1
    assert len(data['items']) == 1


async def test_bread_retrieve_host(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await factory.create_event()

    u2 = await factory.create_user(email='u2@example.org')
    e2 = await factory.create_event(host_user_id=u2, name='another event')

    await login()

    r = await cli.get(url('event-retrieve', pk=factory.event_id))
    assert r.status == 200, await r.text()

    r = await cli.get(url('event-retrieve', pk=e2))
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
                'suggested_price': None,
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
        timezone='Europe/London',
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
        'start_ts': datetime(2020, 2, 1, 19, 0, tzinfo=timezone.utc),
        'timezone': 'Europe/London',
        'duration': timedelta(seconds=7200),
        'short_description': 'title I love to party',
        'long_description': '# title\nI love to **party**',
        'external_ticket_url': None,
        'public': True,
        'location_name': 'London',
        'location_lat': 50.0,
        'location_lng': 0.0,
        'ticket_limit': None,
        'tickets_taken': 0,
        'image': None,
        'secondary_image': None,
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
    assert email['Subject'] == 'Update: Frank Spencer created an event "foobar"'
    assert email['part:text/plain'] == (
        'Testing update:\n'
        '\n'
        'Event "foobar" (Supper Clubs) created by "Frank Spencer" (admin), click the link below to view the event.\n'
        '\n'
        '<div class="button">\n'
        '  <a href="https://127.0.0.1/dashboard/events/%s/"><span>View Event</span></a>\n'
        '</div>\n'
    ) % event_id


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
        timezone='Europe/London',
        long_description='I love to party'
    )
    r = await cli.json_post(url('event-add'), data=data)
    assert r.status == 201, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    public, start_ts, duration = await db_conn.fetchrow('SELECT public, start_ts, duration FROM events')
    assert public is False
    assert start_ts == datetime(2020, 2, 1, 0, 0, tzinfo=timezone.utc)
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
        timezone='Europe/London',
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
        timezone='Europe/London',
        date={'dt': datetime(2020, 2, 1, 19, 0).strftime('%s'), 'dur': 3600},
    )
    r = await cli.json_post(url('event-add'), data=data)
    assert r.status == 201, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    status = await db_conn.fetchval('SELECT status FROM events')
    assert status == 'pending'


async def test_create_timezone(cli, url, db_conn, factory: Factory, login):
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
            'dt': datetime(2020, 6, 1, 19, 0).isoformat(),
            'dur': 7200,
        },
        timezone='America/New_York',
        long_description='# title\nI love to **party**'
    )
    r = await cli.json_post(url('event-add'), data=data)
    assert r.status == 201, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    data = await r.json()
    start_ts, tz = await db_conn.fetchrow('SELECT start_ts, timezone FROM events WHERE id=$1', data['pk'])
    assert tz == 'America/New_York'
    assert start_ts == datetime(2020, 6, 1, 23, 0, tzinfo=timezone.utc)


async def test_create_external_ticketing(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await login()

    data = dict(
        name='foobar',
        category=factory.category_id,
        location={'lat': 50, 'lng': 0, 'name': 'London'},
        date={'dt': datetime(2020, 6, 1, 19, 0).isoformat(), 'dur': 7200},
        external_ticket_url='https://www.example.com/the-test-event/',
        timezone='America/New_York',
        long_description='# title\nI love to **party**'
    )
    r = await cli.json_post(url('event-add'), data=data)
    assert r.status == 201, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    data = await r.json()
    external_ticket_url = await db_conn.fetchval('SELECT external_ticket_url FROM events WHERE id=$1', data['pk'])
    assert external_ticket_url == 'https://www.example.com/the-test-event/'

    cat_slug, event_slug = await db_conn.fetchrow(
        'SELECT cat.slug, e.slug FROM events e JOIN categories cat on e.category = cat.id WHERE e.id=$1', data['pk']
    )
    r = await cli.get(url('event-get-public', category=cat_slug, event=event_slug))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data['event']['external_ticket_url'] == 'https://www.example.com/the-test-event/'


async def test_create_bad_timezone(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await login()

    data = dict(
        name='foobar',
        category=factory.category_id,
        date={
            'dt': datetime(2020, 6, 1, 19, 0).strftime('%s'),
            'dur': 7200,
        },
        timezone='foobar',
        long_description='# title\nI love to **party**'
    )
    r = await cli.json_post(url('event-add'), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'Invalid Data',
        'details': [
            {
                'loc': [
                    'timezone',
                ],
                'msg': 'invalid timezone',
                'type': 'value_error',
            },
        ],
    }


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

    ticket_limit, location_lat = await db_conn.fetchrow('SELECT ticket_limit, location_lat FROM events')
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
    r = await cli.json_post(url('event-edit', pk=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM events')
    ticket_limit, location_lat = await db_conn.fetchrow('SELECT ticket_limit, location_lat FROM events')
    assert ticket_limit == 12
    assert location_lat == 50

    action = await db_conn.fetchrow("SELECT * FROM actions WHERE type='edit-event'")
    assert action['user_id'] == factory.user_id
    assert action['event'] == factory.event_id


async def test_edit_event_date(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()

    start_ts = await db_conn.fetchval('SELECT start_ts FROM events')
    assert start_ts == datetime(2020, 6, 28, 18, 0, tzinfo=timezone.utc)
    data = dict(date={'dt': datetime(2020, 1, 1, 12).isoformat(), 'dur': 3600})
    r = await cli.json_post(url('event-edit', pk=factory.event_id), data=data)
    assert r.status == 200, await r.text()

    start_ts = await db_conn.fetchval('SELECT start_ts FROM events')
    assert start_ts == datetime(2020, 1, 1, 12, tzinfo=timezone.utc)


async def test_edit_event_timezone(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()

    start_ts, tz = await db_conn.fetchrow('SELECT start_ts, timezone FROM events')
    assert start_ts == datetime(2020, 6, 28, 18, 0, tzinfo=timezone.utc)
    start_ts_local = await db_conn.fetchval('SELECT start_ts AT TIME ZONE timezone FROM events')
    assert start_ts_local == datetime(2020, 6, 28, 19, 0)
    assert tz == 'Europe/London'
    data = dict(timezone='America/New_York')
    r = await cli.json_post(url('event-edit', pk=factory.event_id), data=data)
    assert r.status == 200, await r.text()

    start_ts, tz = await db_conn.fetchrow('SELECT start_ts, timezone FROM events')
    assert start_ts == datetime(2020, 6, 28, 23, 0, tzinfo=timezone.utc)
    assert tz == 'America/New_York'

    start_ts_local = await db_conn.fetchval('SELECT start_ts AT TIME ZONE timezone FROM events')
    assert start_ts_local == datetime(2020, 6, 28, 19, 0)


async def test_edit_event_ticket_limit(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(ticket_limit=20)
    await login()

    anne = await factory.create_user(first_name='x', email='anne@example.org')
    ben = await factory.create_user(first_name='x', email='ben@example.org')
    await factory.book_free(await factory.create_reservation(anne, ben), anne)

    r = await cli.json_post(url('event-edit', pk=factory.event_id), data=dict(ticket_limit=1))
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data['details'][0]['msg'] == 'May not be less than the number of tickets already booked.'


async def test_edit_past_event(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await factory.create_event()
    await login()

    r = await cli.json_post(url('event-edit', pk=factory.event_id), data=dict(ticket_limit=12))
    assert r.status == 200, await r.text()
    assert 12 == await db_conn.fetchval('SELECT ticket_limit FROM events')
    assert 1 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='edit-event'")

    await db_conn.execute("UPDATE events SET start_ts=now() - '1 hour'::interval")
    r = await cli.json_post(url('event-edit', pk=factory.event_id), data=dict(ticket_limit=100))
    assert r.status == 404, await r.text()
    assert 12 == await db_conn.fetchval('SELECT ticket_limit FROM events')
    assert 1 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='edit-event'")


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


async def test_set_event_status_host_not_active(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await factory.create_event()
    await login()
    await db_conn.execute("UPDATE users SET status='pending'")

    r = await cli.json_post(url('event-set-status', id=factory.event_id), data=dict(status='published'))
    assert r.status == 403, await r.text()
    data = await r.json()
    assert data == {'message': 'Host not active'}
    assert 'pending' == await db_conn.fetchval('SELECT status FROM events')


async def test_set_event_status_missing_event(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await login()

    r = await cli.json_post(url('event-set-status', id=999), data=dict(status='published'))
    assert r.status == 404, await r.text()


async def test_set_event_status_wrong_host(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    user2 = await factory.create_user(role='host', email='user2@example.org')
    await factory.create_event(host_user_id=user2)
    await login()

    r = await cli.json_post(url('event-set-status', id=factory.event_id), data=dict(status='published'))
    assert r.status == 403, await r.text()
    data = await r.json()
    assert data == {'message': 'user is not the host of this event'}
    assert 'pending' == await db_conn.fetchval('SELECT status FROM events')


async def test_event_tickets_host(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await factory.create_event(price=10)

    user2_id = await factory.create_user(first_name='guest', last_name='guest', email='guest@example.org', role='guest')

    res = await factory.create_reservation(user2_id)
    await factory.buy_tickets(res, user2_id)

    await login()

    r = await cli.get(url('event-tickets', id=factory.event_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    ticket_id = await db_conn.fetchval('SELECT id from tickets')
    assert data == {
        'tickets': [
            {
                'id': ticket_id,
                'ticket_id': RegexStr(r'.{7}-%s' % ticket_id),
                'ticket_status': 'booked',
                'extra_info': None,
                'booked_at': CloseToNow(),
                'booking_type': 'buy-tickets',
                'price': 10,
                'extra_donated': None,
                'guest_user_id': user2_id,
                'guest_name': None,
                'buyer_user_id': user2_id,
                'buyer_name': 'guest guest',
                'ticket_type_name': 'Standard',
                'ticket_type_id': await db_conn.fetchval('SELECT id from ticket_types'),
            },
        ],
    }


async def test_event_tickets_admin(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()

    anne = await factory.create_user(first_name='x', email='anne@example.org')
    ben = await factory.create_user(first_name='x', email='ben@example.org')
    await factory.book_free(await factory.create_reservation(anne, ben), anne)
    await db_conn.execute(
        "UPDATE tickets SET first_name='anne', last_name='apple', extra_donated=1.23 WHERE user_id=$1", anne)
    await db_conn.execute(
        "UPDATE tickets SET first_name='ben', last_name='banana', extra_donated=1.23 WHERE user_id=$1", ben)

    await login()

    r = await cli.get(url('event-tickets', id=factory.event_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert len(data['tickets']) == 2
    tickets = sorted(data['tickets'], key=lambda t: t['guest_name'])
    tt_id = await db_conn.fetchval('SELECT id from ticket_types')
    assert tickets == [
        {
            'id': await db_conn.fetchval("SELECT id FROM tickets where first_name='anne'"),
            'ticket_id': RegexStr(r'.{7}-\d+'),
            'ticket_status': 'booked',
            'extra_info': None,
            'booked_at': CloseToNow(),
            'booking_type': 'book-free-tickets',
            'price': None,
            'extra_donated': 1.23,
            'guest_user_id': anne,
            'guest_name': 'anne apple',
            'guest_email': 'anne@example.org',
            'buyer_user_id': anne,
            'buyer_name': 'anne apple',
            'buyer_email': 'anne@example.org',
            'ticket_type_name': 'Standard',
            'ticket_type_id': tt_id,
        },
        {
            'id': await db_conn.fetchval("SELECT id FROM tickets where first_name='ben'"),
            'ticket_id': RegexStr(r'.{7}-\d+'),
            'ticket_status': 'booked',
            'extra_info': None,
            'booked_at': CloseToNow(),
            'booking_type': 'book-free-tickets',
            'price': None,
            'extra_donated': 1.23,
            'guest_user_id': ben,
            'guest_name': 'ben banana',
            'guest_email': 'ben@example.org',
            'buyer_user_id': anne,
            'buyer_name': 'anne apple',
            'buyer_email': 'anne@example.org',
            'ticket_type_name': 'Standard',
            'ticket_type_id': tt_id,
        },
    ]


async def test_image_existing(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await factory.create_event()
    await login()
    assert dummy_server.app['log'] == []
    r = await cli.json_post(url('event-set-image-existing', id=factory.event_id),
                            data={'image': 'https://testingbucket.example.org/testing.png'})
    assert r.status == 200, await r.text()
    assert 'https://testingbucket.example.org/testing.png' == await db_conn.fetchval('SELECT image FROM events')

    assert dummy_server.app['log'] == []


async def test_image_existing_past(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await factory.create_event(start_ts=datetime(2000, 1, 1))
    await login()
    r = await cli.json_post(url('event-set-image-existing', id=factory.event_id),
                            data={'image': 'https://testingbucket.example.org/testing.png'})
    assert r.status == 403, await r.text()
    assert {'message': "you can't modify past events"} == await r.json()


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

    assert dummy_server.app['log'] == []


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
    assert data == {'message': 'user is not the host of this event'}

    assert dummy_server.app['log'] == []


async def test_image_existing_wrong_id(cli, url, factory: Factory, login, dummy_server):
    await factory.create_company()
    await factory.create_user()
    await login()
    r = await cli.json_post(url('event-set-image-existing', id=1),
                            data={'image': 'https://testingbucket.example.org/testing.png'})
    assert r.status == 404, await r.text()
    assert dummy_server.app['log'] == []


async def test_image_existing_delete(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(image='https://testingbucket.example.org/main.png')
    await login()

    r = await cli.json_post(url('event-set-image-existing', id=factory.event_id),
                            data={'image': 'https://testingbucket.example.org/testing.png'})
    assert r.status == 200, await r.text()
    assert 'https://testingbucket.example.org/testing.png' == await db_conn.fetchval('SELECT image FROM events')

    assert set(dummy_server.app['log']) == {
        'DELETE aws_endpoint_url/testingbucket.example.org/main.png',
        'DELETE aws_endpoint_url/testingbucket.example.org/thumb.png'
    }


async def test_image_new(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(image='https://testingbucket.example.org/main.png')
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
    assert img_path == RegexStr(r'https://testingbucket.example.org/tests/testing/'
                                r'supper-clubs/the-event-name/\w+/main.png')

    # debug(dummy_server.app['log'])
    assert sorted(dummy_server.app['log']) == [
        'DELETE aws_endpoint_url/testingbucket.example.org/main.png',
        'DELETE aws_endpoint_url/testingbucket.example.org/thumb.png',
        RegexStr(r'PUT aws_endpoint_url/testingbucket.example.org/tests/testing/supper-clubs/'
                 r'the-event-name/\w+?/main.png'),
        RegexStr(r'PUT aws_endpoint_url/testingbucket.example.org/tests/testing/supper-clubs/'
                 r'the-event-name/\w+?/thumb.png'),
    ]


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


async def test_delete_wrong_ticket_type(cli, url, factory: Factory, login):
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
        lambda tt_id: [{'id': tt_id, 'name': 'foobar'}],
        '"msg": "field required"'
    ),
    (
        lambda tt_id: [{'id': 999, 'name': 'x', 'slots_used': 1, 'active': True}],
        '"message": "wrong ticket updated"'
    ),
    (
        lambda tt_id: [{'id': tt_id, 'name': 'x', 'slots_used': 1, 'active': False}],
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
    ticket_types = get_input(tt_id)

    r = await cli.json_post(url('update-event-ticket-types', id=factory.event_id), data={'ticket_types': ticket_types})
    assert r.status == 400, await r.text()
    assert response_contains in await r.text()


async def test_event_updates_sent(cli, url, login, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=10)
    await login()

    anne = await factory.create_user(first_name='anne', email='anne@example.org')
    await factory.buy_tickets(await factory.create_reservation(anne, None), anne)

    data = dict(
        subject='This is a test email & whatever',
        message='this is the **message**.'
    )

    r = await cli.json_post(url('event-send-update', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()

    assert len(dummy_server.app['emails']) == 1

    r = await cli.get(url('event-updates-sent', id=factory.event_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {'event_updates': [
        {
            'message': 'this is the **message**.',
            'subject': 'This is a test email & whatever',
            'ts': CloseToNow(),
        }
    ]}


async def test_event_updates_past(cli, url, login, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await factory.create_event()
    await login()

    anne = await factory.create_user(first_name='anne', email='anne@example.org')
    await factory.book_free(await factory.create_reservation(anne, None), anne)

    data = dict(
        subject='This is a test email & whatever',
        message='this is the **message**.'
    )

    r = await cli.json_post(url('event-send-update', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    assert len(dummy_server.app['emails']) == 1

    r = await cli.json_post(url('event-send-update', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    assert len(dummy_server.app['emails']) == 2

    await db_conn.execute("UPDATE events SET start_ts=now() - '1 hour'::interval")

    r = await cli.json_post(url('event-send-update', id=factory.event_id), data=data)
    assert r.status == 403, await r.text()
    assert {'message': "you can't modify past events"} == await r.json()
    assert len(dummy_server.app['emails']) == 2


async def test_send_event_update_wrong_user(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    user2 = await factory.create_user(role='host', email='user2@example.org')
    await factory.create_event(price=10, host_user_id=user2)
    await login()

    data = dict(
        subject='This is a test email & whatever',
        message='this is the **message**.'
    )

    r = await cli.json_post(url('event-send-update', id=factory.event_id), data=data)
    assert r.status == 403, await r.text()


async def test_send_event_update_no_event(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await login()

    data = dict(
        subject='This is a test email & whatever',
        message='this is the **message**.'
    )

    r = await cli.json_post(url('event-send-update', id=999), data=data)
    assert r.status == 404, await r.text()


async def test_event_updates_none(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()

    r = await cli.get(url('event-updates-sent', id=factory.event_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {'event_updates': []}


async def test_event_updates_wrong_event(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    user2 = await factory.create_user(role='host', email='user2@example.org')
    await factory.create_event(price=10, host_user_id=user2)
    await login()

    r = await cli.get(url('event-updates-sent', id=factory.event_id))
    assert r.status == 403, await r.text()


@pytest.mark.parametrize('previous_status', [
    True, False
])
async def test_event_switch_status(previous_status, cli, url, login, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=10)
    await login()

    await db_conn.execute('UPDATE events SET highlight=$1', previous_status)

    r = await cli.json_post(url('event-switch-highlight', id=factory.event_id))
    assert r.status == 200, await r.text()

    h = await db_conn.fetchval('SELECT highlight FROM events')
    assert h == (not previous_status)


async def test_delete_event(cli, url, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()
    await factory.create_reservation()

    event2 = await factory.create_event(slug='event2')
    ticket_type = await db_conn.fetchval('SELECT id FROM ticket_types WHERE event=$1', event2)
    await factory.create_reservation(event_id=event2, ticket_type_id=ticket_type)

    assert 2 == await db_conn.fetchval('SELECT count(*) FROM events')
    assert 2 == await db_conn.fetchval('SELECT count(*) FROM ticket_types')
    assert 2 == await db_conn.fetchval('SELECT count(*) FROM tickets')

    r = await cli.json_post(url('event-delete', pk=factory.event_id))
    assert r.status == 200, await r.text()

    assert 1 == await db_conn.fetchval('SELECT count(*) FROM events')
    assert 1 == await db_conn.fetchval('SELECT count(*) FROM ticket_types')
    assert 1 == await db_conn.fetchval('SELECT count(*) FROM tickets')


async def test_delete_event_host(cli, url, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await factory.create_event()
    await login()
    await factory.create_reservation()

    assert 1 == await db_conn.fetchval('SELECT count(*) FROM events')

    r = await cli.json_post(url('event-delete', pk=factory.event_id))
    assert r.status == 403, await r.text()

    assert 1 == await db_conn.fetchval('SELECT count(*) FROM events')


async def test_secondary_image(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()

    data = FormData()
    data.add_field('image', create_image(), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('event-set-image-secondary', id=factory.event_id),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        }
    )
    assert r.status == 200, await r.text()

    img_path = await db_conn.fetchval('SELECT secondary_image FROM events')
    assert img_path == RegexStr(
        r'https://testingbucket.example.org/tests/testing/supper-clubs/the-event-name/secondary/\w+/main.png'
    )

    assert dummy_server.app['log'] == [
        RegexStr(r'PUT aws_endpoint_url/testingbucket.example.org/tests/testing/'
                 r'supper-clubs/the-event-name/secondary/\w+/main.png'),
    ]


async def test_secondary_image_exists(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()
    event_path = 'testingbucket.example.org/tests/testing/supper-clubs/the-event-name'
    img_url = f'https://{event_path}/secondary/xxx123/main.png'
    await db_conn.execute('update events set secondary_image=$1', img_url)

    data = FormData()
    data.add_field('image', create_image(), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('event-set-image-secondary', id=factory.event_id),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        }
    )
    assert r.status == 200, await r.text()

    assert sorted(dummy_server.app['log']) == [
        f'DELETE aws_endpoint_url/{event_path}/secondary/xxx123/main.png',
        f'DELETE aws_endpoint_url/{event_path}/secondary/xxx123/thumb.png',
        RegexStr(rf'PUT aws_endpoint_url/{event_path}/secondary/\w+/main.png'),
    ]


async def test_remove_secondary_image_(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()
    event_path = 'testingbucket.example.org/tests/testing/supper-clubs/the-event-name'
    img_url = f'https://{event_path}/secondary/xxx123/main.png'
    await db_conn.execute('update events set secondary_image=$1', img_url)

    r = await cli.json_post(url('event-remove-image-secondary', id=factory.event_id))
    assert r.status == 200, await r.text()

    assert sorted(dummy_server.app['log']) == [
        f'DELETE aws_endpoint_url/{event_path}/secondary/xxx123/main.png',
        f'DELETE aws_endpoint_url/{event_path}/secondary/xxx123/thumb.png',
    ]
    assert None is await db_conn.fetchval('select secondary_image from events where id=$1', factory.event_id)

    r = await cli.json_post(url('event-remove-image-secondary', id=factory.event_id))
    assert r.status == 200, await r.text()

    assert sorted(dummy_server.app['log']) == [
        f'DELETE aws_endpoint_url/{event_path}/secondary/xxx123/main.png',
        f'DELETE aws_endpoint_url/{event_path}/secondary/xxx123/thumb.png',
    ]
    assert None is await db_conn.fetchval('select secondary_image from events where id=$1', factory.event_id)
