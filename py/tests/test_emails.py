import json
import re
from datetime import datetime, timedelta

import pytest
from buildpg import Values
from pytest_toolbox.comparison import RegexStr

from shared.emails import EmailActor, Triggers, UserEmail
from shared.settings import Settings
from shared.utils import ticket_ref

from .conftest import Factory


@pytest.fixture
async def email_actor(settings: Settings, db_pool, loop):
    emails = EmailActor(settings=settings, pg=db_pool, loop=loop, concurrency_enabled=False)
    await emails.startup()
    yield emails
    await emails.shutdown()
    await emails.close()


async def test_send_email(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user(email='testing@scolvin.com')
    ctx = {
        'summary': 'testing',
    }
    await email_actor.send_emails(factory.company_id, Triggers.admin_notification,
                                  [UserEmail(id=factory.user_id, ctx=ctx)])

    assert dummy_server.app['log'] == [
        ('email_send_endpoint', 'Subject: "Update: testing", '
                                'To: "Frank Spencer <testing@scolvin.com>"'),
    ]


async def test_with_def(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_user(email='testing@scolvin.com')

    await db_conn.execute_b(
        'INSERT INTO email_definitions (:values__names) VALUES :values',
        values=Values(
            company=factory.company_id,
            trigger=Triggers.password_reset.value,
            subject='{{{ company_name}}} xxx',
            body='DEBUG:\n```\n{{{ __print_debug_context__ }}}\n```',
        )
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


async def test_send_ticket_email(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(email='testing@scolvin.com')
    await factory.create_event(price=10, location_name='The Location', location_lat=51.5, location_lng=-0.2)

    res = await factory.create_reservation(factory.user_id, None)
    booked_action_id = await factory.buy_tickets(res)

    await email_actor.send_event_conf(booked_action_id)

    assert dummy_server.app['log'] == [
        'POST stripe_root_url/customers',
        'POST stripe_root_url/charges',
        ('email_send_endpoint', 'Subject: "The Event Name Ticket Confirmation", '
                                'To: "Frank Spencer <testing@scolvin.com>"'),
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
    assert '<p><a href="https://www.google.com/maps/place/' in html
    assert '<li>Duration: <strong>All day</strong></li>' in html


async def test_send_ticket_email_duration(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(email='testing@scolvin.com')
    await factory.create_event(price=10, location_name='The Location',
                               location_lat=51.5, location_lng=-0.2, duration=timedelta(hours=1.5))

    res = await factory.create_reservation()
    booked_action_id = await factory.buy_tickets(res)

    await email_actor.send_event_conf(booked_action_id)

    assert dummy_server.app['log'] == [
        'POST stripe_root_url/customers',
        'POST stripe_root_url/charges',
        ('email_send_endpoint', 'Subject: "The Event Name Ticket Confirmation", '
                                'To: "Frank Spencer <testing@scolvin.com>"'),
    ]
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    html = email['part:text/html']
    assert (
        '<div class="button">\n'
        '  <a href="https://127.0.0.1/supper-clubs/the-event-name/"><span>View Event</span></a>\n'
        '</div>\n'
    ) in html
    assert '<p><a href="https://www.google.com/maps/place/' in html
    assert '<li>Duration: <strong>1 hour 30 mins</strong></li>' in html


async def test_send_ticket_name_on_ticket(email_actor: EmailActor, factory: Factory, dummy_server, db_conn, settings):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(first_name=None, last_name=None)
    await factory.create_event(price=10)

    res = await factory.create_reservation()
    assert 'UPDATE 1' == await db_conn.execute("UPDATE tickets SET first_name='Cat', last_name='Dig'")
    booked_action_id = await factory.buy_tickets(res)

    await email_actor.send_event_conf(booked_action_id)

    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    assert email['To'] == 'Cat Dig <frank@example.org>'
    assert email['part:text/plain'].startswith(
        'Hi Cat,\n'
        '\n'
        'Thanks for booking your ticket for **The Event Name**.\n'
    )
    ticket_id = await db_conn.fetchval('SELECT id FROM tickets')
    ref = ticket_ref(ticket_id, settings)
    assert ref.endswith(f'-{ticket_id}')
    assert f'* Ticket Ref: **{ref}**\n' in email['part:text/plain']
    assert f'<li>Ticket Ref: <strong>{ref}</strong></li>\n' in email['part:text/html']


async def test_unsubscribe(email_actor: EmailActor, factory: Factory, dummy_server, db_conn, cli):
    await factory.create_company()
    await factory.create_user(email='testing@scolvin.com')
    await email_actor.send_emails(factory.company_id, Triggers.admin_notification,
                                  [UserEmail(id=factory.user_id, ctx={})])

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
    await factory.create_event(start_ts=datetime.now() + timedelta(hours=25), price=10)

    res = await factory.create_reservation()
    await factory.buy_tickets(res)

    assert 0 == await email_actor.send_event_reminders.direct()


async def test_event_reminder(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(first_name=None, last_name=None)
    await factory.create_event(
        start_ts=datetime.now() + timedelta(hours=12),
        price=10,
        status='published',
        location_name='Tower Block',
        location_lat=51.5,
        location_lng=-0.5,
    )

    res = await factory.create_reservation()
    await factory.buy_tickets(res)
    assert 'UPDATE 1' == await db_conn.execute("UPDATE tickets SET first_name='Cat', last_name='Dog'")

    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='event-guest-reminder'")
    assert 1 == await email_actor.send_event_reminders.direct()
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    assert email['To'] == 'Cat Dog <frank@example.org>'
    text = email['part:text/plain']
    assert text.startswith(
        f'Hi Cat,\n'
        f'\n'
        f'You\'re booked in to attend **The Event Name**, the event will start in a day\'s time.\n'
        f'\n'
        f'<div class="button">\n'
        f'  <a href="https://127.0.0.1/supper-clubs/the-event-name/"><span>View Event</span></a>\n'
        f'</div>\n'
        f'\n'
        f'Event:\n'
        f'\n'
        f'* Start Time: **{datetime.now() + timedelta(hours=12):%d %b %y}**\n'
        f'* Duration: **All day**\n'
        f'* Location: **Tower Block**\n'
        f'\n'
    ), text
    assert 'www.google.com/maps' in text
    a = await db_conn.fetchrow("SELECT company, user_id, event FROM actions WHERE type='event-guest-reminder'")
    assert a == (factory.company_id, None, factory.event_id)


async def test_event_reminder_many(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat()

    anne = await factory.create_user(first_name='anne', email='anne@example.org')
    ben = await factory.create_user(first_name='ben', email='ben@example.org')
    charlie = await factory.create_user(first_name='charlie', email='charlie@example.org')

    e1 = await factory.create_event(start_ts=datetime.now() + timedelta(hours=12),
                                    duration=timedelta(hours=1), price=10, status='published', name='event1')
    await factory.buy_tickets(await factory.create_reservation(anne, ben, event_id=e1), anne)
    await factory.buy_tickets(await factory.create_reservation(charlie, event_id=e1), charlie)

    e2 = await factory.create_event(start_ts=datetime.now() + timedelta(hours=12), price=10,
                                    status='published', name='event2', slug='event2')
    await factory.buy_tickets(await factory.create_reservation(charlie, event_id=e2), charlie)

    await factory.create_event(start_ts=datetime.now() + timedelta(hours=12), price=10,
                               status='published', name='event3', slug='event3')

    assert 4 == await db_conn.fetchval('SELECT COUNT(*) FROM tickets')

    assert 4 == await email_actor.send_event_reminders.direct()

    assert len(dummy_server.app['emails']) == 4
    assert {(e['To'], e['Subject']) for e in dummy_server.app['emails']} == {
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
    await factory.buy_tickets(await factory.create_reservation(anne, None), anne)

    data = dict(
        grecaptcha_token='__ok__',
        subject='This is a test email & whatever',
        message='this is the **message**.'
    )

    r = await cli.json_post(url('event-send-update', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()

    assert len(dummy_server.app['emails']) == 1

    email = dummy_server.app['emails'][0]
    assert email['Subject'] == 'This is a test email & whatever'
    assert email['To'] == 'anne Spencer <anne@example.org>'
    html = email['part:text/html']
    assert (
        '<p>Hi anne,</p>\n'
        '\n'
        '<p>this is the <strong>message</strong>.</p>\n'
    ) in html

    assert '  <a href="https://127.0.0.1/supper-clubs/the-event-name/"><span>View Event</span></a>\n' in html


async def test_event_host_updates(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()

    await factory.create_user()
    await factory.create_event(
        start_ts=datetime.now() + timedelta(days=5),
        price=10,
        status='published',
    )

    anne = await factory.create_user(first_name='anne', email='anne@example.org')
    await factory.buy_tickets(await factory.create_reservation(anne), anne)

    assert 1 == await email_actor.send_event_host_updates.direct()
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
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

    assert RegexStr(
        '.*The Event Name is coming up in <strong>5</strong> days on <strong>.*'
    ) == html


async def test_event_host_updates_full(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_cat()

    await factory.create_user()
    await factory.create_event(
        start_ts=datetime.now() + timedelta(days=5),
        price=10,
        status='published',
        ticket_limit=1
    )

    anne = await factory.create_user(first_name='anne', email='anne@example.org')
    await factory.buy_tickets(await factory.create_reservation(anne), anne)
    await db_conn.execute("UPDATE tickets SET created_ts=now() - '2 days'::interval")

    assert 1 == await email_actor.send_event_host_updates.direct()
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    html = email['part:text/html']
    assert '<strong>Congratulations, all tickets have been booked - your event is full.</strong>' in html
    assert '<span class="large">1</span> of 1.\n' in html
    assert 'Total made from ticket sales' in html


async def test_event_host_updates_free(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()

    await factory.create_user()
    await factory.create_event(start_ts=datetime.now() + timedelta(days=5), status='published')

    anne = await factory.create_user(first_name='anne', email='anne@example.org')
    await factory.book_free(await factory.create_reservation(anne), anne)

    await email_actor.send_event_host_updates()
    assert len(dummy_server.app['emails']) == 1
    assert 'Total made from ticket sales' not in dummy_server.app['emails'][0]['part:text/html']


async def test_event_host_updates_none(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(start_ts=datetime.now() + timedelta(days=5))

    assert 0 == await email_actor.send_event_host_updates.direct()
    assert len(dummy_server.app['emails']) == 0


async def test_event_host_updates_today(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(start_ts=datetime.now(), status='published')
    assert 0 == await email_actor.send_event_host_updates.direct()
    assert len(dummy_server.app['emails']) == 0


async def test_event_host_updates_cache(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(start_ts=datetime.now() + timedelta(days=5), status='published')
    assert 1 == await email_actor.send_event_host_updates.direct()
    assert len(dummy_server.app['emails']) == 1
    assert 0 == await email_actor.send_event_host_updates.direct()
    assert len(dummy_server.app['emails']) == 1


async def test_event_host_final_updates(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(start_ts=datetime.now() + timedelta(hours=3, minutes=30), status='published')

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
    await factory.create_event(start_ts=datetime.now() + timedelta(hours=3, minutes=30), status='published')

    assert 1 == await email_actor.send_event_host_updates_final.direct()
    assert len(dummy_server.app['emails']) == 1
    html = dummy_server.app['emails'][0]['part:text/html']
    assert '<p>You have <strong>0</strong> bookings confirmed' in html


async def test_event_host_final_updates_wrong_time(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(start_ts=datetime.now() + timedelta(hours=4, minutes=30), status='published')

    assert 0 == await email_actor.send_event_host_updates_final.direct()
    assert len(dummy_server.app['emails']) == 0
