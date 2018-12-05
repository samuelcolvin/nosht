import pytest
from pytest import fixture

from shared.donorfy import DonorfyActor
from shared.utils import RequestError

from .conftest import Factory


@fixture(name='donorfy')
async def create_donorfy(settings, db_pool):
    settings.donorfy_api_key = 'standard'
    settings.donorfy_access_key = 'donorfy-access-key'
    don = DonorfyActor(settings=settings, pg=db_pool, concurrency_enabled=False)
    await don.startup()

    yield don

    await don.client.close()


async def test_create_host_existing(donorfy: DonorfyActor, factory: Factory, dummy_server):
    await factory.create_company()
    await factory.create_user()

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
    await factory.create_event()

    await donorfy.event_created(factory.event_id)
    assert dummy_server.app['log'] == [
        f'GET donorfy_api_root/standard/System/LookUpTypes/Campaigns',
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
        f'POST donorfy_api_root/standard/constituents/123456/AddActiveTags',
        f'POST donorfy_api_root/standard/activities',
    ]


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
    action_id, _ = await factory.buy_tickets(res)

    await donorfy.tickets_booked(action_id)
    assert dummy_server.app['log'] == [
        f'POST stripe_root_url/customers',
        f'POST stripe_root_url/charges',
        f'GET donorfy_api_root/standard/System/LookUpTypes/Campaigns',
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
        f'POST donorfy_api_root/standard/activities',
        f'POST donorfy_api_root/standard/transactions',
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
    await factory.create_cat()
    await factory.create_event(price=10)

    res = await factory.create_reservation()
    action_id, _ = await factory.buy_tickets(res)
    await db_conn.execute('update tickets set extra_donated=10')

    await donorfy.tickets_booked(action_id)
    assert set(dummy_server.app['log']) == {
        f'POST stripe_root_url/customers',
        f'POST stripe_root_url/charges',
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
        f'POST donorfy_api_root/standard/activities',
        f'POST donorfy_api_root/standard/transactions',
        f'GET donorfy_api_root/standard/transactions/trans_123/Allocations',
        f'POST donorfy_api_root/standard/transactions/trans_123/AddAllocation',
        f'PUT donorfy_api_root/standard/transactions/Allocation/123',
        f'GET donorfy_api_root/standard/System/LookUpTypes/Campaigns',
    }


async def test_donate(donorfy: DonorfyActor, factory: Factory, dummy_server, db_conn, cli, url, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await factory.create_event(price=10)
    await factory.create_donation_option()
    await login()

    data = dict(
        stripe=dict(token='tok_visa', client_ip='0.0.0.0', card_ref='4242-32-01'),
        donation_option_id=factory.donation_option_id,
        event_id=factory.event_id,
        gift_aid=True,
        title='Ms',
        first_name='Joe',
        last_name='Blogs',
        address='Testing Street',
        city='Testingville',
        postcode='TE11 0ST',
    )
    r = await cli.json_post(url('donate'), data=data)
    assert r.status == 200, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')
    action_id = await db_conn.fetchval("select id from actions where type='donate'")

    await donorfy.donation(action_id)
    assert dummy_server.app['log'] == [
        'POST stripe_root_url/customers',
        'POST stripe_root_url/charges',
        'GET donorfy_api_root/standard/System/LookUpTypes/Campaigns',
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
        'POST donorfy_api_root/standard/transactions',
        ('email_send_endpoint', 'Subject: "Thanks for your donation", To: "Frank Spencer <frank@example.org>"'),
        f'GET donorfy_api_root/standard/constituents/ExternalKey/nosht_{factory.user_id}',
        'POST donorfy_api_root/standard/transactions',
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
    assert dummy_server.app['log'] == [
        f'GET donorfy_api_root/no-user/constituents/ExternalKey/nosht_{factory.user_id}',
    ]


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
