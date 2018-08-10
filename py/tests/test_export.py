from csv import DictReader
from datetime import timedelta
from io import StringIO

from pytest_toolbox.comparison import RegexStr

from .conftest import Factory


async def test_event_export(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(
        price=12.34,
        status='published',
        location_name='Testing Location',
        location_lat=51.5,
        location_lng=-0.5,
        duration=timedelta(hours=2, minutes=45),
    )

    # two tickets
    await factory.buy_tickets(await factory.create_reservation())
    await factory.buy_tickets(await factory.create_reservation())

    await login()

    r = await cli.get(url('export', type='events'))
    assert r.status == 200
    assert r.headers['Content-Disposition'] == RegexStr('attachment;filename=nosht_events_\d{4}-\d\d-\d\dT.+\.csv')
    text = await r.text()
    data = [dict(r) for r in DictReader(StringIO(text))]
    assert data == [
        {
            'id': str(factory.event_id),
            'name': 'The Event Name',
            'slug': 'the-event-name',
            'status': 'published',
            'start_time': '2020-01-28T19:00:00',
            'duration_hours': '2.75',
            'short_description': RegexStr('.*'),
            'long_description': RegexStr('.*'),
            'is_public': 'true',
            'location_name': 'Testing Location',
            'location_lat': '51.5000000',
            'location_lng': '-0.5000000',
            'ticket_limit': '',
            'image': '',
            'ticket_price': '12.34,12.34',
            'tickets_booked': '2',
            'total_raised': '24.68',
            'category_id': str(factory.category_id),
            'category_slug': 'supper-clubs',
        },
    ]


async def test_export_as_host(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await factory.create_event()

    await login()

    r = await cli.get(url('export', type='events'))
    assert r.status == 403


async def test_export_no_events(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await login()

    r = await cli.get(url('export', type='events'))
    assert r.status == 200
    text = await r.text()
    data = [dict(r) for r in DictReader(StringIO(text))]
    assert data == [{'message': 'no events found'}]


async def test_cat_export(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await login()

    r = await cli.get(url('export', type='categories'))
    assert r.status == 200
    text = await r.text()
    data = [dict(r) for r in DictReader(StringIO(text))]
    assert data == [
        {
            'id': str(factory.category_id),
            'name': 'Supper Clubs',
            'slug': 'supper-clubs',
            'live': 'true',
            'description': '',
            'sort_index': '',
            'event_content': '',
            'host_advice': '',
            'ticket_extra_title': '',
            'ticket_extra_help_text': '',
            'suggested_price': '',
            'image': 'https://www.example.org/co.png',
        },
    ]


async def test_user_export(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(receive_emails=False)
    await factory.create_event(price=10)
    await factory.buy_tickets(await factory.create_reservation())
    await factory.buy_tickets(await factory.create_reservation())
    await login()

    r = await cli.get(url('export', type='users'))
    assert r.status == 200
    text = await r.text()
    data = [dict(r) for r in DictReader(StringIO(text))]
    assert data == [
        {
            'id': str(factory.user_id),
            'role': 'admin',
            'status': 'active',
            'first_name': 'Frank',
            'last_name': 'Spencer',
            'email': 'frank@example.org',
            'phone_number': '',
            'stripe_customer_id': 'customer-id',
            'receive_emails': 'false',
            'allow_marketing': 'false',
            'created_ts': RegexStr('\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d'),
            'active_ts': RegexStr('\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d'),
            'tickets': '2',
        },
    ]


async def test_ticket_export(cli, url, login, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(
        price=12.34,
        status='published',
        location_name='Testing Location',
        location_lat=51.5,
        location_lng=-0.5,
        duration=timedelta(hours=2, minutes=45),
    )
    await factory.buy_tickets(await factory.create_reservation())
    await factory.buy_tickets(await factory.create_reservation())
    await login()
    ticket_id = await db_conn.fetchval('SELECT id FROM tickets ORDER BY id DESC LIMIT 1')
    await db_conn.execute('UPDATE tickets SET user_id=NULL WHERE id=$1', ticket_id)

    r = await cli.get(url('export', type='tickets'))
    assert r.status == 200
    text = await r.text()
    data = sorted([dict(r) for r in DictReader(StringIO(text))], key=lambda d: int(d['id']))
    ticket_type = str(await db_conn.fetchval('SELECT id FROM ticket_types'))
    assert data == [
        {
            'id': RegexStr('\d+'),
            'ticket_first_name': '',
            'ticket_last_name': '',
            'status': 'booked',
            'price': '12.34',
            'created_ts': RegexStr('\d{4}.*'),
            'extra_info': '',
            'ticket_type_id': ticket_type,
            'ticket_type_name': 'Standard',
            'event_id': str(factory.event_id),
            'event_slug': 'the-event-name',
            'guest_user_id': str(factory.user_id),
            'guest_first_name': 'Frank',
            'guest_last_name': 'Spencer',
            'buyer_user_id': str(factory.user_id),
            'buyer_first_name': 'Frank',
            'buyer_last_name': 'Spencer',
        },
        {
            'id': RegexStr('\d+'),
            'ticket_first_name': '',
            'ticket_last_name': '',
            'status': 'booked',
            'price': '12.34',
            'created_ts': RegexStr('\d{4}.*'),
            'extra_info': '',
            'ticket_type_id': ticket_type,
            'ticket_type_name': 'Standard',
            'event_id': str(factory.event_id),
            'event_slug': 'the-event-name',
            'guest_user_id': '',
            'guest_first_name': '',
            'guest_last_name': '',
            'buyer_user_id': str(factory.user_id),
            'buyer_first_name': 'Frank',
            'buyer_last_name': 'Spencer',
        },
    ]
