import json
import re

import pytest
from buildpg import Values
from pytest_toolbox.comparison import RegexStr

from shared.emails import EmailActor, UserEmail, Triggers
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
        'event_name': 'Testing Event',
    }
    await email_actor.send_emails(factory.company_id, Triggers.ticket_buyer,
                                  [UserEmail(id=factory.user_id, ctx=ctx)])

    assert dummy_server.app['log'] == [
        ('email_send_endpoint', 'Subject: "Testing Event Ticket Confirmation (Testing)", '
                                'To: "Frank Spencer <testing@scolvin.com>"'),
    ]


async def test_with_def(email_actor: EmailActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_user(email='testing@scolvin.com')

    await db_conn.execute_b(
        'INSERT INTO email_definitions (:values__names) VALUES :values RETURNING id',
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
