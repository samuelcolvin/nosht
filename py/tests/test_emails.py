import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from buildpg import Values
from pytest_toolbox.comparison import AnyInt, CloseToNow, RegexStr

from shared.actions import ActionTypes
from shared.emails import EmailActor, Triggers, UserEmail
from shared.settings import Settings
from shared.utils import format_dt, ticket_id_signed

from .conftest import Factory, london


def offset_from_now(**kwargs):
    return (datetime.utcnow() + timedelta(**kwargs)).replace(tzinfo=timezone.utc)


@pytest.fixture
async def email_actor(settings: Settings, db_pool, loop, redis):
    emails = EmailActor(settings=settings, pg=db_pool, loop=loop, concurrency_enabled=False)
    await emails.startup()
    yield emails
    await emails.shutdown()
    await emails.close()


async def test_send_email(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_user(email='testing@example.org')
    u2 = await factory.create_user(email='other@example.org', receive_emails=False)
    ctx = {
        'summary': 'testing',
    }
    await email_actor.send_emails(
        factory.company_id,
        Triggers.admin_notification,
        [UserEmail(id=factory.user_id, ctx=ctx), UserEmail(id=u2, ctx=ctx)],
    )

    assert dummy_server.app['log'] == [
        ('email_send_endpoint', 'Subject: "Update: testing", To: "Frank Spencer <testing@example.org>"'),
    ]
    assert 1 == await db_conn.fetchval('select count(*) from emails')
    email = await db_conn.fetchrow('select * from emails')
    assert dict(email) == {
        'id': AnyInt(),
        'company': factory.company_id,
        'user_id': factory.user_id,
        'ext_id': 'testing',
        'send_ts': CloseToNow(delta=3),
        'update_ts': CloseToNow(delta=3),
        'status': 'pending',
        'trigger': 'admin-notification',
        'subject': 'Update: testing',
        'address': 'testing@example.org',
    }


async def test_with_def(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_user(email='testing@scolvin.com')

    await db_conn.execute_b(
        'INSERT INTO email_definitions (:values__names) VALUES :values',
        values=Values(
            company=factory.company_id,
            trigger=Triggers.password_reset.value,
            subject='{{{ company_name}}} xxx',
            body='DEBUG:\n{{{ __debug_context__ }}}',
        ),
    )

    await email_actor.send_emails(factory.company_id, Triggers.password_reset, [UserEmail(id=factory.user_id)])

    assert dummy_server.app['log'] == [
        ('email_send_endpoint', 'Subject: "Testing xxx", To: "Frank Spencer <testing@scolvin.com>"'),
    ]
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    # debug(email)
    email_context = json.loads(re.search('```(.*?)```', email['part:text/plain'], flags=re.S).group(1))
    assert email_context == {
        'company_name': 'Testing',
        'company_logo': None,
        'base_url': 'https://127.0.0.1',
        'first_name': 'Frank',
        'full_name': 'Frank Spencer',
        'unsubscribe_link': RegexStr(r'https://127\.0\.0\.1/api/unsubscribe/\d+/\?sig=[0-9a-f]+'),
    }


async def test_send_ticket_email(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(email='testing@scolvin.com')
    await factory.create_event(
        price=10,
        location_name='The Location',
        location_lat=51.5,
        location_lng=-0.2,
        start_ts=london.localize(datetime(2032, 6, 3)),
        duration=None,
    )

    res = await factory.create_reservation(factory.user_id)
    await factory.buy_tickets(res)

    assert dummy_server.app['log'] == [
        (
            'email_send_endpoint',
            'Subject: "The Event Name Ticket Confirmation", To: "Frank Spencer <testing@scolvin.com>"',
        ),
    ]
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    # debug(email)
    html = email['part:text/html']
    assert (
        '<div class="button">\n'
        '  <a href="https://127.0.0.1/supper-clubs/the-event-name/"><span>View Event</span></a>\n'
        '</div>\n'
    ) in html
    assert (
        '<li>Ticket Price: <strong>£10.00</strong></li>\n'
        '<li>Tickets Purchased: <strong>1</strong></li>\n'
        '<li>Total Amount Charged: <strong>£10.00</strong></li>\n'
    ) in html
    assert '<p><a href="https://www.google.com/maps/place/' in html
    assert '<li>Start Time: <strong>3rd Jun 2032</strong></li>\n' in html
    assert '<li>Duration: <strong>All day</strong></li>' in html
    attachment = email['part:text/calendar']
    assert attachment.startswith(
        'BEGIN:VCALENDAR\n'
        'VERSION:2.0\n'
        'PRODID:-//nosht//events//EN\n'
        'CALSCALE:GREGORIAN\n'
        'METHOD:PUBLISH\n'
        'BEGIN:VEVENT\n'
        'SUMMARY:The Event Name\n'
    )


async def test_send_ticket_email_duration(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(email='testing@scolvin.com')
    await factory.create_event(
        price=10, location_name='The Location', location_lat=51.5, location_lng=-0.2, duration=timedelta(hours=1.5)
    )

    res = await factory.create_reservation()
    await factory.buy_tickets(res)

    assert dummy_server.app['log'] == [
        (
            'email_send_endpoint',
            'Subject: "The Event Name Ticket Confirmation", To: "Frank Spencer <testing@scolvin.com>"',
        ),
    ]
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    html = email['part:text/html']
    assert (
        '<div class="button">\n'
        '  <a href="https://127.0.0.1/supper-clubs/the-event-name/"><span>View Event</span></a>\n'
        '</div>\n'
    ) in html
    print(html)
    assert '<p><a href="https://www.google.com/maps/place/' in html
    assert '<li>Duration: <strong>1 hour 30 mins</strong></li>' in html
    assert '<li>Start Time: <strong>07:00pm, 28th Jun 2032</strong></li>\n' in html


async def test_send_ticket_name_on_ticket(email_actor: EmailActor, factory: Factory, dummy_server, db_conn, settings):
    await factory.create_company()
    await factory.create_cat(ticket_extra_title='Foo Bar')
    await factory.create_user()
    await factory.create_event()

    anne = await factory.create_user(first_name=None, last_name=None, email='anne@example.org')
    res = await factory.create_reservation(anne)
    assert 'UPDATE 1' == await db_conn.execute("UPDATE tickets SET first_name='Cat', last_name='Dog'")
    booked_action_id = await factory.book_free(res, anne)

    await email_actor.send_event_conf(booked_action_id)

    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    assert email['To'] == 'Cat Dog <anne@example.org>'
    assert email['part:text/plain'].startswith(
        'Hi Cat,\n'
        '\n'
        'Thanks for booking your ticket for Supper Clubs, **The Event Name** hosted by Frank Spencer.\n'
        '\n'
        'Foo Bar not provided, please let the event host Frank Spencer know if you have any special requirements.\n'
    )
    assert 'Card Charged' not in email['part:text/plain']
    tid = await db_conn.fetchval('SELECT id FROM tickets')
    ticket_id_s = ticket_id_signed(tid, settings)
    assert ticket_id_s.endswith(f'-{tid}')
    assert f'* Ticket ID: **{ticket_id_s}**\n' in email['part:text/plain']
    assert f'<li>Ticket ID: <strong>{ticket_id_s}</strong></li>\n' in email['part:text/html']


async def test_send_ticket_other(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat(ticket_extra_title='Foo Bar')
    await factory.create_user()

    anne = await factory.create_user(first_name='anne', last_name='anne', email='anne@example.org')
    ben = await factory.create_user(first_name='ben', last_name='ben', email='ben@example.org')

    await factory.create_event(status='published')
    booked_action_id = await factory.book_free(await factory.create_reservation(anne, ben), anne)

    assert 2 == await email_actor.send_event_conf.direct(booked_action_id)
    assert len(dummy_server.app['emails']) == 2
    # debug(dummy_server.app['emails'])
    anne_email, ben_email = dummy_server.app['emails']
    assert anne_email['To'] == 'anne anne <anne@example.org>'
    assert (
        'Thanks for booking your tickets for Supper Clubs, **The Event Name** hosted by Frank Spencer.\n'
    ) in anne_email['part:text/plain']

    assert ben_email['To'] == 'ben ben <ben@example.org>'
    assert (
        'Great news! anne anne has bought you a ticket for Supper Clubs, '
        '**The Event Name** hosted by Frank Spencer.\n'
    ) in ben_email['part:text/plain']


async def test_send_ticket_not_buyer(factory: Factory, dummy_server, login, cli, url):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published')

    await factory.create_user(first_name='anne', last_name='anne', email='anne@example.org')
    await factory.create_user(first_name='ben', last_name='ben', email='ben@example.org')
    await factory.create_user(first_name='charlie', last_name='charlie', email='charlie@example.org')

    await login('anne@example.org')

    data = {
        'tickets': [
            {'t': True, 'first_name': 'benx', 'last_name': 'benx', 'email': 'ben@example.org'},
            {'t': True, 'email': 'charlie@example.org'},
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    data = await r.json()

    data = dict(booking_token=data['booking_token'], book_action='book-free-tickets')
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 200, await r.text()

    assert len(dummy_server.app['emails']) == 3
    other_emails = [e for e in dummy_server.app['emails'] if 'ticket-other' in e['X-SES-MESSAGE-TAGS']]
    # debug(dummy_server.app['emails'])
    assert {e['To'] for e in other_emails} == {'ben ben <ben@example.org>', 'charlie charlie <charlie@example.org>'}
    assert all(
        'Great news! anne anne has bought you a ticket for Supper Clubs' in e['part:text/html'] for e in other_emails
    )


async def test_send_ticket_email_cover_costs(factory: Factory, dummy_server, cli, url, login):
    await factory.create_company()
    await factory.create_cat(cover_costs_message='Help!', cover_costs_percentage=5)
    await factory.create_user()
    await factory.create_event(status='published', price=100)

    factory.user_id = await factory.create_user(email='ticket.buyer@example.org')
    await login(email='ticket.buyer@example.org')

    data = {
        'tickets': [{'t': True, 'email': 'ticket.buyer@example.org', 'cover_costs': True}, {'t': True}, {'t': True}],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    data = await r.json()
    action_id = data['action_id']
    await factory.fire_stripe_webhook(action_id)

    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    assert email['To'] == 'Frank Spencer <ticket.buyer@example.org>'
    html = email['part:text/html']
    assert (
        '<li>Ticket Price: <strong>£100.00</strong></li>\n'
        '<li>Tickets Purchased: <strong>3</strong></li>\n'
        '<li>Discretionary extra donation: <strong>£15.00</strong></li>\n'
        '<li>Total Amount Charged: <strong>£315.00</strong></li>\n'
    ) in html


async def test_ticket_buyer_not_attendee(factory: Factory, dummy_server, login, cli, url):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', location_name='The Location', location_lat=51.5, location_lng=-0.2)

    await factory.create_user(first_name='anne', last_name='anne', email='anne@example.org')
    await login('anne@example.org')

    data = {
        'tickets': [{'t': True}, {'t': True}],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    data = await r.json()

    data = dict(booking_token=data['booking_token'], book_action='book-free-tickets')
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 200, await r.text()

    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    # debug(email)
    assert (
        '* Start Time: **07:00pm, 28th Jun 2032**\n* Duration: **1 hour**\n* Location: **The Location**\n'
    ) in email['part:text/plain']
    assert 'This is your ticket' not in email['part:text/plain']
    assert email['X-SES-MESSAGE-TAGS'] == 'company=testing, trigger=ticket-buyer'


async def test_unsubscribe(email_actor: EmailActor, factory: Factory, dummy_server, db_conn, cli):
    await factory.create_company()
    await factory.create_user(email='testing@scolvin.com')
    await email_actor.send_emails(
        factory.company_id, Triggers.admin_notification, [UserEmail(id=factory.user_id, ctx={})]
    )

    assert True is await db_conn.fetchval('SELECT receive_emails FROM users where id=$1', factory.user_id)
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    m = re.search(r'https://127.0.0.1(/api/unsubscribe/.+?)"', email['part:text/html'])
    unsub_link = m.group(1)
    r = await cli.get(unsub_link, allow_redirects=False)
    assert r.status == 307, await r.text()
    assert r.headers['Location'].endswith('/unsubscribe-valid/')
    assert False is await db_conn.fetchval('SELECT receive_emails FROM users where id=$1', factory.user_id)


async def test_event_reminder_none(email_actor: EmailActor, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(start_ts=offset_from_now(hours=25), price=10)

    res = await factory.create_reservation()
    await factory.buy_tickets(res)

    assert 0 == await email_actor.send_event_reminders.direct()


async def test_event_reminder(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(
        start_ts=offset_from_now(hours=12),
        duration=None,
        price=10,
        status='published',
        location_name='Tower Block',
        location_lat=51.5,
        location_lng=-0.5,
    )

    u2 = await factory.create_user(first_name=None, last_name=None, email='guest@example.org')
    res = await factory.create_reservation(u2)
    await factory.buy_tickets(res)
    assert 'UPDATE 1' == await db_conn.execute("UPDATE tickets SET first_name='Cat', last_name='Dog'")

    assert len(dummy_server.app['emails']) == 1
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='event-guest-reminder'")
    assert 1 == await email_actor.send_event_reminders.direct()
    assert len(dummy_server.app['emails']) == 2
    email = dummy_server.app['emails'][1]
    assert email['To'] == 'Cat Dog <guest@example.org>'
    text = email['part:text/plain']
    now = datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(london)
    start_time = format_dt((now + timedelta(hours=12)).date())
    assert text.startswith(
        f'Hi Cat,\n'
        f'\n'
        f'You\'re booked in to attend **The Event Name** hosted by Frank Spencer, '
        f'the event will start in a day\'s time.\n'
        f'\n'
        f'<div class="button">\n'
        f'  <a href="https://127.0.0.1/supper-clubs/the-event-name/"><span>View Event</span></a>\n'
        f'</div>\n'
        f'\n'
        f'Event:\n'
        f'\n'
        f'* Start Time: **{start_time}**\n'
        f'* Duration: **All day**\n'
        f'* Location: **Tower Block**\n'
        f'\n'
    ), (text + '___' + start_time)
    assert 'www.google.com/maps' in text
    a = await db_conn.fetchrow("SELECT company, user_id, event FROM actions WHERE type='event-guest-reminder'")
    assert a == (factory.company_id, None, factory.event_id)


async def test_event_reminder_many(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat()

    anne = await factory.create_user(first_name='anne', email='anne@example.org')
    ben = await factory.create_user(first_name='ben', email='ben@example.org')
    charlie = await factory.create_user(first_name='charlie', email='charlie@example.org')

    e1 = await factory.create_event(
        start_ts=offset_from_now(hours=12), duration=timedelta(hours=1), price=10, status='published', name='event1'
    )
    await factory.buy_tickets(await factory.create_reservation(anne, ben, event_id=e1))
    await factory.buy_tickets(await factory.create_reservation(charlie, event_id=e1))

    e2 = await factory.create_event(
        start_ts=offset_from_now(hours=12), price=10, status='published', name='event2', slug='event2'
    )
    tt = await db_conn.fetchval('SELECT id FROM ticket_types WHERE event=$1', e2)
    await factory.buy_tickets(await factory.create_reservation(charlie, event_id=e2, ticket_type_id=tt))

    await factory.create_event(
        start_ts=offset_from_now(hours=12), price=10, status='published', name='event3', slug='event3'
    )

    assert 4 == await db_conn.fetchval('SELECT COUNT(*) FROM tickets')

    assert len(dummy_server.app['emails']) == 4
    assert 4 == await email_actor.send_event_reminders.direct()

    assert len(dummy_server.app['emails']) == 8
    assert {(e['To'], e['Subject']) for e in dummy_server.app['emails'][4:]} == {
        ('ben Spencer <ben@example.org>', 'event1 Upcoming'),
        ('anne Spencer <anne@example.org>', 'event1 Upcoming'),
        ('charlie Spencer <charlie@example.org>', 'event1 Upcoming'),
        ('charlie Spencer <charlie@example.org>', 'event2 Upcoming'),
    }


async def test_send_event_update(cli, url, login, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=10)

    await login()

    anne = await factory.create_user(first_name='anne', email='anne@example.org')
    await factory.buy_tickets(await factory.create_reservation(anne, None))
    assert len(dummy_server.app['emails']) == 1

    data = dict(subject='This is a test email & whatever', message='this is the **message**.')

    r = await cli.json_post(url('event-send-update', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()

    assert len(dummy_server.app['emails']) == 2

    email = dummy_server.app['emails'][1]
    assert email['Subject'] == 'This is a test email & whatever'
    assert email['To'] == 'anne Spencer <anne@example.org>'
    html = email['part:text/html']
    assert '<p>Hi anne,</p>\n\n<p>this is the <strong>message</strong>.</p>\n' in html

    assert 'href="https://127.0.0.1/supper-clubs/the-event-name/"><span>View Event</span></a>\n' in html


async def test_event_host_updates(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()

    await factory.create_user()
    await factory.create_event(
        start_ts=offset_from_now(days=5), price=10, status='published',
    )

    anne = await factory.create_user(first_name='anne', email='anne@example.org')
    await factory.buy_tickets(await factory.create_reservation(anne))

    assert len(dummy_server.app['emails']) == 1
    assert 1 == await email_actor.send_event_host_updates.direct()
    assert len(dummy_server.app['emails']) == 2
    email = dummy_server.app['emails'][1]
    # debug(email)
    # from pathlib import Path
    # Path('email.html').write_text(email['part:text/html'])
    assert email['Subject'] == 'The Event Name Update from Testing'
    assert email['To'] == 'Frank Spencer <frank@example.org>'

    html = email['part:text/html']
    assert 'The Event Name is coming up in <strong>5</strong>' in html
    assert (
        '<div class="stat-label">Tickets Booked in the last day</div>\n'
        '<div class="stat-value">\n'
        '  <span class="large">1</span>\n'
        '</div>\n'
        '\n'
        '<div class="stat-label">Tickets Booked Total</div>\n'
        '<div class="stat-value">\n'
        '  <span class="large">1</span>\n'
        '</div>\n'
        '\n'
        '<div class="stat-label">Total made from ticket sales</div>\n'
        '<div class="stat-value">\n'
        '  <span class="large">£10.00</span>\n'
        '</div>\n'
        '\n'
        '<p>Guests can book your event by going to</p>\n'
        '\n'
        '<div class="text-center highlighted">https://127.0.0.1/supper-clubs/the-event-name/</div>\n'
    ) in html
    assert '<strong>Congratulations, all tickets have been booked - your event is full.</strong>' not in html

    assert (
        f'<a href="https://127.0.0.1/dashboard/events/{factory.event_id}/"><span>Event Dashboard</span></a>'
    ) in html

    assert RegexStr('.*The Event Name is coming up in <strong>5</strong> days on <strong>.*') == html


async def test_event_host_updates_full(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat()

    await factory.create_user()
    await factory.create_event(start_ts=offset_from_now(days=5), price=10, status='published', ticket_limit=1)

    anne = await factory.create_user(first_name='anne', email='anne@example.org')
    await factory.buy_tickets(await factory.create_reservation(anne))
    await db_conn.execute("UPDATE tickets SET created_ts=now() - '2 days'::interval")

    assert len(dummy_server.app['emails']) == 1
    assert 1 == await email_actor.send_event_host_updates.direct()
    assert len(dummy_server.app['emails']) == 2
    email = dummy_server.app['emails'][1]
    html = email['part:text/html']
    assert '<strong>Congratulations, all tickets have been booked - your event is full.</strong>' in html
    assert '<span class="large">1</span> of 1.\n' in html
    assert 'Total made from ticket sales' in html


async def test_event_host_updates_free(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()

    await factory.create_user()
    await factory.create_event(start_ts=offset_from_now(days=18), status='published')

    anne = await factory.create_user(first_name='anne', email='anne@example.org')
    await factory.book_free(await factory.create_reservation(anne), anne)

    await email_actor.send_event_host_updates()
    assert len(dummy_server.app['emails']) == 1
    assert 'Total made from ticket sales' not in dummy_server.app['emails'][0]['part:text/html']


async def test_event_host_updates_18_days(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(start_ts=offset_from_now(days=18), status='published')
    assert 0 == await email_actor.send_event_host_updates.direct()
    assert len(dummy_server.app['emails']) == 0


async def test_event_host_updates_none(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(start_ts=offset_from_now(days=5))

    assert 0 == await email_actor.send_event_host_updates.direct()
    assert len(dummy_server.app['emails']) == 0


async def test_event_host_updates_today(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(start_ts=datetime.utcnow(), status='published')
    assert 0 == await email_actor.send_event_host_updates.direct()
    assert len(dummy_server.app['emails']) == 0


async def test_event_host_updates_cache(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(start_ts=offset_from_now(days=5), status='published')
    assert 1 == await email_actor.send_event_host_updates.direct()
    assert len(dummy_server.app['emails']) == 1
    assert 0 == await email_actor.send_event_host_updates.direct()
    assert len(dummy_server.app['emails']) == 1


async def test_event_host_final_updates(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(start_ts=offset_from_now(hours=4, minutes=30), status='published')

    anne = await factory.create_user(first_name='anne', email='anne@example.org')
    await factory.book_free(await factory.create_reservation(anne), anne)

    assert 1 == await email_actor.send_event_host_updates_final.direct()
    assert len(dummy_server.app['emails']) == 1
    assert 0 == await email_actor.send_event_host_updates_final.direct()
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    assert email['Subject'] == 'The Event Name Final Update from Testing'
    assert email['To'] == 'Frank Spencer <frank@example.org>'
    html = email['part:text/html']
    assert '<p>It&#39;s nearly time for your Supper Clubs, The Event Name, which is very exciting.' in html
    assert '<p>You have <strong>1</strong> bookings confirmed' in html


async def test_event_host_final_updates_no_tickets(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(start_ts=offset_from_now(hours=4, minutes=30), status='published')

    assert 1 == await email_actor.send_event_host_updates_final.direct()
    assert len(dummy_server.app['emails']) == 1
    html = dummy_server.app['emails'][0]['part:text/html']
    assert '<p>You have <strong>0</strong> bookings confirmed' in html


async def test_event_host_final_updates_wrong_time(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(start_ts=offset_from_now(hours=5, minutes=30), status='published')

    assert 0 == await email_actor.send_event_host_updates_final.direct()
    assert len(dummy_server.app['emails']) == 0


async def test_custom_template(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat(slug='this-and-that')
    await factory.create_user()
    await factory.create_event()

    await db_conn.execute_b(
        'INSERT INTO email_definitions (:values__names) VALUES :values',
        values=Values(
            company=factory.company_id,
            trigger=Triggers.ticket_buyer.value,
            subject='testing',
            body="""
{{#is_category_this_and_that}}
on this and that.
{{/is_category_this_and_that}}

{{#is_category_other}}
on other category.
{{/is_category_other}}

{{ secondary_button(Testing | {{ events_link }}) }}
""",
        ),
    )

    u2 = await factory.create_user(email='different@example.org')
    res = await factory.create_reservation(u2)
    booked_action_id = await factory.book_free(res, u2)

    await email_actor.send_event_conf(booked_action_id)
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    assert (
        'on this and that.\n'
        '\n'
        '<div class="button">\n'
        '  <a href=""><span class="secondary">Testing</span></a>\n'
        '</div>\n'
    ) == email['part:text/plain']


async def test_event_created(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='admin')

    u2 = await factory.create_user(role='host', email='host@example.org', first_name='ho', last_name='st')
    await factory.create_event(host_user_id=u2)

    action_id = await db_conn.fetchval(
        'INSERT INTO actions (company, user_id, event, type) VALUES ($1, $2, $3, $4) RETURNING id',
        factory.company_id,
        u2,
        factory.event_id,
        ActionTypes.create_event,
    )

    await email_actor.send_event_created(action_id)

    assert len(dummy_server.app['emails']) == 2
    admin_email = next(e for e in dummy_server.app['emails'] if e['To'] == 'Frank Spencer <frank@example.org>')
    assert 'Event "The Event Name" (Supper Clubs) created by "ho st" (host)' in admin_email['part:text/plain']

    host_email = next(e for e in dummy_server.app['emails'] if e['To'] == 'ho st <host@example.org>')
    assert "Great news - you've set up your Supper Clubs in support of Testing." in host_email['part:text/plain']
    assert (
        f'<a href="https://127.0.0.1/dashboard/events/{factory.event_id}/"><span>Event Dashboard</span></a>'
    ) in host_email['part:text/html']


async def test_custom_email_def_ok(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_user(email='testing@example.org')

    body = 'DETAILS: {{{ details }}}'
    await db_conn.execute_b(
        'INSERT INTO email_definitions (:values__names) VALUES :values',
        values=Values(
            company=factory.company_id,
            trigger=Triggers.admin_notification,
            subject='testing',
            body=body,
            title='the title',
        ),
    )

    u2 = await factory.create_user(email='other@example.org', receive_emails=False)
    ctx = {'details': '<h1>details</h1>'}
    await email_actor.send_emails(
        factory.company_id,
        Triggers.admin_notification,
        [UserEmail(id=factory.user_id, ctx=ctx), UserEmail(id=u2, ctx=ctx)],
    )

    assert dummy_server.app['log'] == [
        ('email_send_endpoint', 'Subject: "testing", To: "Frank Spencer <testing@example.org>"'),
    ]
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    assert '<p>DETAILS: <h1>details</h1></p>' in email['part:text/html']


async def test_send_tickets_available(email_actor: EmailActor, factory: Factory, dummy_server, db_conn, cli):
    await factory.create_company()
    await factory.create_cat(ticket_extra_title='Foo Bar')
    await factory.create_user()
    await factory.create_event(start_ts=london.localize(datetime(2032, 6, 28, 19, 0)))

    anne = await factory.create_user(first_name='anne', last_name='anne', email='anne@example.org')
    await db_conn.execute('insert into waiting_list (event, user_id) values ($1, $2)', factory.event_id, anne)
    assert await db_conn.fetchval('select last_notified from waiting_list') == datetime(2000, 1, 1, tzinfo=timezone.utc)

    assert await email_actor.send_tickets_available.direct(factory.event_id) == 'emailed 1 users'
    assert await email_actor.send_tickets_available.direct(factory.event_id) == 'no users in waiting list'
    assert await email_actor.send_tickets_available.direct(factory.event_id) == 'no users in waiting list'
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    assert email['To'] == 'anne anne <anne@example.org>'
    assert 'trigger=event-tickets-available' in email['X-SES-MESSAGE-TAGS']
    plain = email['part:text/plain']
    assert 'Great news! New tickets have become available for **The Event Name**.\n' in plain
    assert '<a href="https://127.0.0.1/supper-clubs/the-event-name/"><span>View Event</span></a>' in plain
    remove_link = re.search(r'(/api/events/.*?/waiting-list/.*?)\)', plain).group(1)
    assert await db_conn.fetchval('select count(*) from actions where type=$1', ActionTypes.email_waiting_list) == 1

    assert await db_conn.fetchval('select count(*) from waiting_list') == 1
    assert await db_conn.fetchval('select last_notified from waiting_list') == CloseToNow(delta=3)
    r = await cli.get(remove_link, allow_redirects=False)
    assert r.status == 307, await r.text()
    assert r.headers['Location'] == f'http://127.0.0.1:{cli.server.port}/waiting-list-removed/'
    assert await db_conn.fetchval('select count(*) from waiting_list') == 0


async def test_send_tickets_available_one_left(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat(ticket_extra_title='Foo Bar')
    await factory.create_user()
    await factory.create_event(start_ts=london.localize(datetime(2032, 6, 28, 19, 0)), ticket_limit=1)

    anne = await factory.create_user(first_name='anne', last_name='anne', email='anne@example.org')
    await db_conn.execute('insert into waiting_list (event, user_id) values ($1, $2)', factory.event_id, anne)
    ben = await factory.create_user(first_name='ben', last_name='ben', email='ben@example.org')
    await db_conn.execute('insert into waiting_list (event, user_id) values ($1, $2)', factory.event_id, ben)

    assert await email_actor.send_tickets_available.direct(factory.event_id) == 'emailed 2 users'
    assert len(dummy_server.app['emails']) == 2
    assert {'anne anne <anne@example.org>', 'ben ben <ben@example.org>'} == {
        e['To'] for e in dummy_server.app['emails']
    }
    assert 'trigger=event-tickets-available' in dummy_server.app['emails'][0]['X-SES-MESSAGE-TAGS']


async def test_tickets_available_none(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat(ticket_extra_title='Foo Bar')
    await factory.create_user()
    await factory.create_event(start_ts=london.localize(datetime(2032, 6, 28, 19, 0)), ticket_limit=1)

    anne = await factory.create_user(first_name='anne', last_name='anne', email='anne@example.org')
    res = await factory.create_reservation(anne)
    await factory.book_free(res, anne)

    ben = await factory.create_user(first_name='ben', last_name='ben', email='ben@example.org')
    await db_conn.execute('insert into waiting_list (event, user_id) values ($1, $2)', factory.event_id, ben)

    assert await email_actor.send_tickets_available.direct(factory.event_id) == 'no tickets remaining'
    assert len(dummy_server.app['emails']) == 0


async def test_send_tickets_available_paste(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat(ticket_extra_title='Foo Bar')
    await factory.create_user()
    await factory.create_event(start_ts=london.localize(datetime(2010, 6, 28, 19, 0)))

    anne = await factory.create_user(first_name='anne', last_name='anne', email='anne@example.org')

    await db_conn.execute('insert into waiting_list (event, user_id) values ($1, $2)', factory.event_id, anne)

    assert await email_actor.send_tickets_available.direct(factory.event_id) == 'event in the past'
    assert len(dummy_server.app['emails']) == 0


async def test_send_tickets_available_no_one(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat(ticket_extra_title='Foo Bar')
    await factory.create_user()
    await factory.create_event(start_ts=london.localize(datetime(2032, 6, 28, 19, 0)))

    assert await email_actor.send_tickets_available.direct(factory.event_id) == 'no users in waiting list'
    assert len(dummy_server.app['emails']) == 0


async def test_send_tickets_available_one_day(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat(ticket_extra_title='Foo Bar')
    await factory.create_user()
    await factory.create_event(start_ts=london.localize(datetime(2032, 6, 28, 19, 0)))

    anne = await factory.create_user(first_name='anne', last_name='anne', email='anne@example.org')
    await db_conn.execute('insert into waiting_list (event, user_id) values ($1, $2)', factory.event_id, anne)

    ben = await factory.create_user(first_name='ben', last_name='ben', email='ben@example.org')
    recently = (datetime.now() - timedelta(hours=12)).replace(tzinfo=timezone.utc)
    await db_conn.execute(
        'insert into waiting_list (event, user_id, last_notified) values ($1, $2, $3)', factory.event_id, ben, recently,
    )

    assert await email_actor.send_tickets_available.direct(factory.event_id) == 'emailed 1 users'
    assert len(dummy_server.app['emails']) == 1
    assert dummy_server.app['emails'][0]['To'] == 'anne anne <anne@example.org>'
    s = await db_conn.fetchval('select last_notified from waiting_list where user_id=$1', anne)
    assert s == CloseToNow(delta=3)
    assert await db_conn.fetchval('select last_notified from waiting_list where user_id=$1', ben) == recently


async def test_waiting_list_add(email_actor: EmailActor, factory: Factory, dummy_server, db_conn, cli):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(start_ts=london.localize(datetime(2032, 6, 28, 19, 0)))

    anne = await factory.create_user(first_name='anne', last_name='anne', email='anne@example.org')
    wl_id = await db_conn.fetchval(
        'insert into waiting_list (event, user_id) values ($1, $2) returning id', factory.event_id, anne
    )

    await email_actor.waiting_list_add.direct(wl_id)
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    assert email['To'] == 'anne anne <anne@example.org>'
    assert 'trigger=waiting-list-add' in email['X-SES-MESSAGE-TAGS']
    plain = email['part:text/plain']
    assert (
        "You've been added to the waiting list for [The Event Name](https://127.0.0.1/supper-clubs/the-event-name/).\n"
    ) in plain
    remove_link = re.search(r'(/api/events/.*?/waiting-list/.*?)\)', plain).group(1)

    assert await db_conn.fetchval('select count(*) from waiting_list') == 1
    r = await cli.get(remove_link, allow_redirects=False)
    assert r.status == 307, await r.text()
    assert r.headers['Location'] == f'http://127.0.0.1:{cli.server.port}/waiting-list-removed/'
    assert await db_conn.fetchval('select count(*) from waiting_list') == 0
