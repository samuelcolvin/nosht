import pytest

from shared.emails import EmailActor, Triggers
from shared.settings import Settings

from .conftest import Factory


@pytest.fixture
async def email_actor(settings: Settings, db_pool, loop, dummy_server):
    settings.aws_ses_endpoint = dummy_server.app['server_name'] + '/send/email/'
    emails = EmailActor(settings=settings, pg=db_pool, loop=loop, concurrency_enabled=False)
    await emails.startup()
    yield emails
    await emails.shutdown()
    await emails.close()


async def test_send_email(email_actor: EmailActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user()

    await email_actor.send_emails(factory.company_id, Triggers.confirmation_buyer, [factory.user_id])

    assert dummy_server.app['log'] == [
        ('email_send_endpoint', 'Subject: "Testing Ticket Confirmation", To: "Frank Spencer <frank@example.com>"'),
    ]
