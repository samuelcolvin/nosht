import json
import re
from datetime import timedelta

import pytest
from buildpg import Values
from pytest_toolbox.comparison import RegexStr

from shared.emails import EmailActor, Triggers, UserEmail
from shared.settings import Settings

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
        'foo': 'bar',
    }
    await email_actor.send_emails(factory.company_id, Triggers.admin_notification,
                                  [UserEmail(id=factory.user_id, ctx=ctx)])

    assert dummy_server.app['log'] == [
        ('email_send_endpoint', 'Subject: "Testing notification", '
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
            body='DEBUG:\n```\n{{{ __print_debug_context__ }}}\n```',
        )
    )

    await email_actor.send_emails(factory.company_id, Triggers.password_reset, [UserEmail(id=factory.user_id)])

    assert dummy_server.app['log'] == [
        ('email_send_endpoint', 'Subject: "Testing Password Reset", To: "Frank Spencer <testing@scolvin.com>"'),
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

    res = await factory.create_reservation()
    paid_action_id = await factory.buy_tickets(res)

    await email_actor.send_event_conf(paid_action_id)

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
    paid_action_id = await factory.buy_tickets(res)

    await email_actor.send_event_conf(paid_action_id)

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
