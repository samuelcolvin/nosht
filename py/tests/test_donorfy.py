import json

import pytest
from buildpg import Values
from pytest import fixture
from pytest_toolbox.comparison import CloseToNow, RegexStr

from shared.actions import ActionTypes
from shared.donorfy import DonorfyActor
from shared.utils import RequestError
from web.utils import encrypt_json

from .conftest import Factory


@fixture(name='donorfy')
async def create_donorfy(settings, db_pool):
    settings.donorfy_api_key = 'standard'
    settings.donorfy_access_key = 'donorfy-access-key'
    don = DonorfyActor(settings=settings, pg=db_pool, concurrency_enabled=False)
    await don.startup()
    redis = await don.get_redis()
    await redis.flushdb()

    yield don

    await don.close(shutdown=True)


async def test_create_host_existing(donorfy: DonorfyActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user()

    await donorfy.host_signuped(factory.user_id)
    await donorfy.host_signuped(factory.user_id)
    assert dummy_server.app['log'] == [
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
    ]


async def test_create_host_new(donorfy: DonorfyActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user()
    donorfy.settings.donorfy_api_key = 'new-user'

    await donorfy.host_signuped(factory.user_id)
    assert dummy_server.app['log'] == [
        f'GET donorfy_api_root/new-user/constituents/ExternalKey/nosht_{factory.user_id}',
        f'GET donorfy_api_root/new-user/constituents/EmailAddress/frank@example.org',
        f'POST donorfy_api_root/new-user/constituents',
    ]


async def test_create_event(donorfy: DonorfyActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await factory.create_event(long_description='test ' * 100)

    await donorfy.event_created(factory.event_id)
    assert dummy_server.app['log'] == [
        f'GET donorfy_api_root/standard/System/LookUpTypes/Campaigns',
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
        f'GET donorfy_api_root/standard/constituents/123456',
        f'POST donorfy_api_root/standard/constituents/123456/AddActiveTags',
        f'POST donorfy_api_root/standard/activities',
    ]
    activity_data = dummy_server.app['data']['/donorfy_api_root/standard/activities 201']
    assert activity_data['Code1'] == '/supper-clubs/the-event-name/'
    assert activity_data['Code3'] == 'test test test test test test test test test...'
    assert 'Code2' not in activity_data


async def test_create_event_no_duration(donorfy: DonorfyActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await factory.create_event(price=10, duration=None)
    donorfy.settings.donorfy_api_key = 'no-users'

    await donorfy.event_created(factory.event_id)
    assert dummy_server.app['log'] == [
        f'GET donorfy_api_root/no-users/System/LookUpTypes/Campaigns',
        f'GET donorfy_api_root/no-users/constituents/ExternalKey/nosht_{factory.user_id}',
        f'GET donorfy_api_root/no-users/constituents/EmailAddress/frank@example.org',
        f'POST donorfy_api_root/no-users/constituents',
        f'POST donorfy_api_root/no-users/constituents/456789/AddActiveTags',
        f'POST donorfy_api_root/no-users/activities',
    ]


async def test_book_tickets(donorfy: DonorfyActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await factory.create_event(price=10)

    res = await factory.create_reservation()
    await factory.buy_tickets(res)

    assert dummy_server.app['log'] == [
        f'GET donorfy_api_root/standard/System/LookUpTypes/Campaigns',
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
        f'GET donorfy_api_root/standard/constituents/123456',
        f'POST donorfy_api_root/standard/activities',
        f'GET stripe_root_url/balance/history/txn_charge-id',
        f'POST donorfy_api_root/standard/transactions',
        (
            'email_send_endpoint',
            'Subject: "The Event Name Ticket Confirmation", To: "Frank Spencer <frank@example.org>"',
        ),
    ]


async def test_book_tickets_free(donorfy: DonorfyActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await factory.create_event()

    action_id = await factory.book_free(await factory.create_reservation())

    await donorfy.tickets_booked(action_id)
    assert dummy_server.app['log'] == [
        f'GET donorfy_api_root/standard/System/LookUpTypes/Campaigns',
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
        f'GET donorfy_api_root/standard/constituents/123456',
        f'POST donorfy_api_root/standard/activities',
    ]


async def test_book_tickets_multiple(donorfy: DonorfyActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await factory.create_event(duration=None)
    donorfy.settings.donorfy_api_key = 'no-users'

    ben = await factory.create_user(first_name='ben', email='ben@example.org')
    charlie = await factory.create_user(first_name='charlie', email='charlie@example.org')
    danial = await factory.create_user(first_name='danial', email='danial@example.org')
    res = await factory.create_reservation(factory.user_id, ben, charlie, danial)
    action_id = await factory.book_free(res)
    v = await db_conn.execute('update tickets set user_id=null where user_id=$1', danial)
    assert v == 'UPDATE 1'

    await donorfy.tickets_booked(action_id)
    assert set(dummy_server.app['log']) == {
        f'GET donorfy_api_root/no-users/System/LookUpTypes/Campaigns',
        f'GET donorfy_api_root/no-users/constituents/ExternalKey/nosht_{factory.user_id}',
        f'GET donorfy_api_root/no-users/constituents/EmailAddress/frank@example.org',
        f'POST donorfy_api_root/no-users/constituents',
        f'POST donorfy_api_root/no-users/activities',
        f'GET donorfy_api_root/no-users/constituents/ExternalKey/nosht_{ben}',
        f'GET donorfy_api_root/no-users/constituents/EmailAddress/charlie@example.org',
        f'GET donorfy_api_root/no-users/constituents/ExternalKey/nosht_{charlie}',
        f'GET donorfy_api_root/no-users/constituents/EmailAddress/ben@example.org',
    }


async def test_book_tickets_extra(donorfy: DonorfyActor, factory: Factory, dummy_server, db_conn):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat(cover_costs_percentage=10)
    await factory.create_event(status='published', price=100)

    res = await factory.create_reservation()
    action_id = await db_conn.fetchval_b(
        'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
        values=Values(
            company=factory.company_id,
            user_id=factory.user_id,
            type=ActionTypes.buy_tickets,
            event=factory.event_id,
            extra=json.dumps({'stripe_balance_transaction': 'txn_testing'}),
        ),
    )
    await db_conn.execute(
        "UPDATE tickets SET status='booked', booked_action=$1 WHERE reserve_action=$2", action_id, res.action_id,
    )
    await db_conn.execute('update tickets set extra_donated=10')

    await donorfy.tickets_booked(action_id)
    assert set(dummy_server.app['log']) == {
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
        f'GET donorfy_api_root/standard/constituents/123456',
        f'POST donorfy_api_root/standard/activities',
        f'GET stripe_root_url/balance/history/txn_testing',
        f'POST donorfy_api_root/standard/transactions',
        f'POST donorfy_api_root/standard/transactions/trans_123/AddAllocation',
        f'GET donorfy_api_root/standard/System/LookUpTypes/Campaigns',
    }


async def test_book_multiple(donorfy: DonorfyActor, factory: Factory, dummy_server, cli, url, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await factory.create_user(first_name='T', last_name='B', email='ticket.buyer@example.org')
    await factory.create_event(status='published', price=10)
    await login(email='ticket.buyer@example.org')

    data = {
        'tickets': [
            {'t': True, 'email': 'ticket.buyer@example.org'},
            {'t': True, 'email': 'ticket.buyer@example.org'},
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    action_id = (await r.json())['action_id']
    await factory.fire_stripe_webhook(action_id)

    trans_data = dummy_server.app['post_data']['POST donorfy_api_root/standard/transactions']
    assert len(trans_data) == 1
    assert trans_data[0] == {
        'ExistingConstituentId': '123456',
        'Channel': 'nosht-supper-clubs',
        'Currency': 'gbp',
        'Campaign': 'supper-clubs:the-event-name',
        'PaymentMethod': 'Payment Card via Stripe',
        'Product': 'Event Ticket(s)',
        'Fund': 'Unrestricted General',
        'Department': '220 Ticket Sales',
        'BankAccount': 'Unrestricted Account',
        'DatePaid': CloseToNow(delta=4),
        'Amount': 20.0,
        'ProcessingCostsAmount': 0.5,
        'Quantity': 2,
        'Acknowledgement': 'supper-clubs-thanks',
        'AcknowledgementText': RegexStr('Ticket ID: .*'),
        'Reference': 'Events.HUF:supper-clubs the-event-name',
        'AddGiftAidDeclaration': False,
        'GiftAidClaimed': False,
    }


async def test_book_offline(donorfy: DonorfyActor, factory: Factory, dummy_server, cli, url, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await factory.create_event(price=10)

    await login()

    res = await factory.create_reservation()
    app = cli.app['main_app']

    data = dict(booking_token=encrypt_json(app, res.dict()), book_action='buy-tickets-offline')
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 200, await r.text()
    assert 'POST donorfy_api_root/standard/transactions' not in dummy_server.app['post_data']


async def test_donate(donorfy: DonorfyActor, factory: Factory, dummy_server, db_conn, cli, url, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await factory.create_event(price=10)
    await factory.create_donation_option()
    await login()

    r = await cli.json_post(
        url('donation-after-prepare', don_opt_id=factory.donation_option_id, event_id=factory.event_id)
    )
    assert r.status == 200, await r.text()
    action_id = (await r.json())['action_id']

    post_data = dict(
        title='Mr',
        first_name='Joe',
        last_name='Blogs',
        address='Testing Street',
        city='Testingville',
        postcode='TE11 0ST',
    )
    r = await cli.json_post(url('donation-gift-aid', action_id=action_id), data=post_data)
    assert r.status == 200, await r.text()

    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')

    await factory.fire_stripe_webhook(action_id, amount=20_00, purpose='donate')

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')

    assert dummy_server.app['log'] == [
        'POST stripe_root_url/customers',
        'POST stripe_root_url/payment_intents',
        'GET donorfy_api_root/standard/System/LookUpTypes/Campaigns',
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
        'GET donorfy_api_root/standard/constituents/123456',
        'GET stripe_root_url/balance/history/txn_charge-id',
        'POST donorfy_api_root/standard/transactions',
        'POST donorfy_api_root/standard/constituents/123456/GiftAidDeclarations',
        ('email_send_endpoint', 'Subject: "Thanks for your donation", To: "Frank Spencer <frank@example.org>"'),
    ]


async def test_donate_no_gift_aid(donorfy: DonorfyActor, factory: Factory, dummy_server, db_conn, cli, url, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await factory.create_event(price=10)
    await factory.create_donation_option()
    await login()

    r = await cli.json_post(
        url('donation-after-prepare', don_opt_id=factory.donation_option_id, event_id=factory.event_id)
    )
    assert r.status == 200, await r.text()
    action_id = (await r.json())['action_id']

    await factory.fire_stripe_webhook(action_id, amount=20_00, purpose='donate')

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')

    assert dummy_server.app['log'] == [
        'POST stripe_root_url/customers',
        'POST stripe_root_url/payment_intents',
        'GET donorfy_api_root/standard/System/LookUpTypes/Campaigns',
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
        'GET donorfy_api_root/standard/constituents/123456',
        'GET stripe_root_url/balance/history/txn_charge-id',
        'POST donorfy_api_root/standard/transactions',
        ('email_send_endpoint', 'Subject: "Thanks for your donation", To: "Frank Spencer <frank@example.org>"'),
    ]


async def test_update_user(donorfy: DonorfyActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user()

    await donorfy.update_user(factory.user_id)
    assert set(dummy_server.app['log']) == {
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
        'PUT donorfy_api_root/standard/constituents/123456',
        'POST donorfy_api_root/standard/constituents/123456/Preferences',
    }


async def test_update_user_neither(donorfy: DonorfyActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user()

    await donorfy.update_user(factory.user_id, update_user=False, update_marketing=False)
    assert dummy_server.app['log'] == [
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
    ]


async def test_update_user_no_user(donorfy: DonorfyActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user()
    donorfy.settings.donorfy_api_key = 'no-user'

    await donorfy.update_user(factory.user_id)
    assert set(dummy_server.app['log']) == {
        f'GET donorfy_api_root/no-user/constituents/ExternalKey/nosht_{factory.user_id}',
        'GET donorfy_api_root/no-user/constituents/EmailAddress/frank@example.org',
        'POST donorfy_api_root/no-user/constituents',
        'POST donorfy_api_root/no-user/constituents/456789/Preferences',
    }


async def test_get_user_update(donorfy: DonorfyActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user()
    donorfy.settings.donorfy_api_key = 'no-ext-id'

    const_id = await donorfy._get_constituent(user_id=factory.user_id, email='foobar@example.com')
    assert const_id == '456789'
    assert dummy_server.app['log'] == [
        f'GET donorfy_api_root/no-ext-id/constituents/ExternalKey/nosht_{factory.user_id}',
        f'GET donorfy_api_root/no-ext-id/constituents/EmailAddress/foobar@example.com',
        'PUT donorfy_api_root/no-ext-id/constituents/456789',
    ]


async def test_get_user_wrong_id(donorfy: DonorfyActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user()
    donorfy.settings.donorfy_api_key = 'wrong-ext-id'

    const_id = await donorfy._get_constituent(user_id=factory.user_id, email='foobar@example.com')
    assert const_id is None
    assert dummy_server.app['log'] == [
        f'GET donorfy_api_root/wrong-ext-id/constituents/ExternalKey/nosht_{factory.user_id}',
        f'GET donorfy_api_root/wrong-ext-id/constituents/EmailAddress/foobar@example.com',
    ]


async def test_bad_response(donorfy: DonorfyActor, dummy_server):
    with pytest.raises(RequestError):
        await donorfy.client.get('/foobar')
    assert dummy_server.app['log'] == [
        'GET donorfy_api_root/standard/foobar',
    ]


async def test_campaign_exists(donorfy: DonorfyActor, dummy_server):
    await donorfy._get_or_create_campaign('supper-clubs', 'the-event-name')
    assert dummy_server.app['log'] == ['GET donorfy_api_root/standard/System/LookUpTypes/Campaigns']

    await donorfy._get_or_create_campaign('supper-clubs', 'the-event-name')
    assert dummy_server.app['log'] == ['GET donorfy_api_root/standard/System/LookUpTypes/Campaigns']  # cached


async def test_campaign_new(donorfy: DonorfyActor, dummy_server):
    await donorfy._get_or_create_campaign('supper-clubs', 'foobar')
    assert dummy_server.app['log'] == [
        'GET donorfy_api_root/standard/System/LookUpTypes/Campaigns',
        'POST donorfy_api_root/standard/System/LookUpTypes/Campaigns',
    ]

    await donorfy._get_or_create_campaign('supper-clubs', 'foobar')
    assert len(dummy_server.app['log']) == 2


async def test_get_constituent_update_campaign(donorfy: DonorfyActor, dummy_server):
    donorfy.settings.donorfy_api_key = 'default-campaign'

    await donorfy._get_constituent(user_id=123, campaign='foo:bar')

    assert dummy_server.app['log'] == [
        f'GET donorfy_api_root/default-campaign/constituents/ExternalKey/nosht_123',
        'GET donorfy_api_root/default-campaign/constituents/123456',
        'PUT donorfy_api_root/default-campaign/constituents/123456',
    ]


async def test_donate_direct(donorfy: DonorfyActor, factory: Factory, dummy_server, db_conn, cli, url, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await factory.create_event(price=10, allow_donations=True, status='published')
    await login()

    r = await cli.json_post(
        url('donation-direct-prepare', tt_id=factory.donation_ticket_type_id_1), data=dict(custom_amount=123),
    )
    assert r.status == 200, await r.text()
    action_id = (await r.json())['action_id']

    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')

    await factory.fire_stripe_webhook(action_id, amount=20_00, purpose='donate-direct')

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')

    assert dummy_server.app['log'] == [
        'POST stripe_root_url/customers',
        'POST stripe_root_url/payment_intents',
        'GET donorfy_api_root/standard/System/LookUpTypes/Campaigns',
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
        'GET donorfy_api_root/standard/constituents/123456',
        'GET stripe_root_url/balance/history/txn_charge-id',
        'POST donorfy_api_root/standard/transactions',
        ('email_send_endpoint', 'Subject: "Thanks for your donation", To: "Frank Spencer <frank@example.org>"'),
    ]
