import json

from aiohttp import FormData
from pytest_toolbox.comparison import AnyInt, CloseToNow, RegexStr

from shared.actions import ActionTypes

from .conftest import Factory, create_image


async def test_donation_options(cli, url, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_donation_option()

    r = await cli.get(url('donation-options', cat_id=factory.category_id))
    assert r.status == 200, await r.text()

    data = await r.json()
    assert data == {
        'donation_options': [
            {
                'id': factory.donation_option_id,
                'name': 'testing donation option',
                'amount': 20.0,
                'image': None,
                'short_description': 'This is the short_description.',
                'long_description': 'This is the long_description.',
            },
        ],
        'post_booking_message': None,
    }

    await db_conn.execute("UPDATE categories SET post_booking_message='this is a test'")
    r = await cli.get(url('donation-options', cat_id=factory.category_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data['post_booking_message'] == 'this is a test'


async def test_donate_with_gift_aid(cli, url, dummy_server, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await factory.create_donation_option()

    factory.user_id = await factory.create_user(
        first_name='other', last_name='person', email='other.person@example.org'
    )
    await login('other.person@example.org')

    r = await cli.json_post(
        url('donation-after-prepare', don_opt_id=factory.donation_option_id, event_id=factory.event_id)
    )
    assert r.status == 200, await r.text()
    action_id = await db_conn.fetchval('select id from actions where type=$1', ActionTypes.donate_prepare)
    data = await r.json()
    assert data == {
        'client_secret': f'payment_intent_secret_{action_id}',
        'action_id': action_id,
    }
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

    assert dummy_server.app['log'] == [
        'POST stripe_root_url/customers',
        'POST stripe_root_url/payment_intents',
        ('email_send_endpoint', 'Subject: "Thanks for your donation", To: "other person <other.person@example.org>"'),
    ]
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')
    r = await db_conn.fetchrow('SELECT * FROM donations')
    assert dict(r) == {
        'id': AnyInt(),
        'donation_option': factory.donation_option_id,
        'ticket_type': None,
        'amount': 20,
        'gift_aid': True,
        'title': 'Mr',
        'first_name': 'Joe',
        'last_name': 'Blogs',
        'address': 'Testing Street',
        'city': 'Testingville',
        'postcode': 'TE11 0ST',
        'action': AnyInt(),
    }
    action = await db_conn.fetchrow('SELECT * FROM actions WHERE id= $1', r['action'])
    assert dict(action) == {
        'id': AnyInt(),
        'company': factory.company_id,
        'user_id': factory.user_id,
        'event': factory.event_id,
        'ts': CloseToNow(delta=3),
        'type': 'donate',
        'extra': RegexStr(r'{.*}'),
    }
    assert json.loads(action['extra']) == {
        'charge_id': 'charge-id',
        'stripe_balance_transaction': 'txn_charge-id',
        '3DS': True,
        'brand': 'Visa',
        'card_last4': '1234',
        'card_expiry': '12/32',
        'payment_metadata': {
            'purpose': 'donate',
            'user_id': factory.user_id,
            'event_id': factory.event_id,
            'reserve_action_id': action_id,
        },
    }
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    assert email['To'] == 'other person <other.person@example.org>'
    assert email['part:text/plain'] == (
        'Hi other,\n'
        '\n'
        'Thanks for your donation to testing donation option of £20.00.\n'
        '\n'
        'You have allowed us to collect gift aid meaning we can collect %25 on top of your original donation.\n'
        '\n'
        '_(Card Charged: Visa 12/32 - ending 1234)_\n'
    )


async def test_donate_no_gift_aid(cli, url, dummy_server, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await factory.create_donation_option()

    await login()

    r = await cli.json_post(
        url('donation-after-prepare', don_opt_id=factory.donation_option_id, event_id=factory.event_id)
    )
    assert r.status == 200, await r.text()
    action_id = (await r.json())['action_id']

    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')
    await factory.fire_stripe_webhook(action_id, amount=20_00, purpose='donate')

    assert dummy_server.app['log'] == [
        'POST stripe_root_url/customers',
        'POST stripe_root_url/payment_intents',
        ('email_send_endpoint', 'Subject: "Thanks for your donation", To: "Frank Spencer <frank@example.org>"'),
    ]
    r = await db_conn.fetchrow('SELECT donation_option, amount, gift_aid, address, city, postcode FROM donations')
    assert dict(r) == {
        'donation_option': factory.donation_option_id,
        'amount': 20,
        'gift_aid': False,
        'address': None,
        'city': None,
        'postcode': None,
    }
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    assert email['To'] == 'Frank Spencer <frank@example.org>'
    assert email['part:text/plain'] == (
        'Hi Frank,\n'
        '\n'
        'Thanks for your donation to testing donation option of £20.00.\n'
        '\n'
        'You did not enable gift aid.\n'
        '\n'
        '_(Card Charged: Visa 12/32 - ending 1234)_\n'
    )


async def test_bread_browse(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_donation_option()

    await login()

    r = await cli.get(url('donation-options-browse'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'items': [
            {
                'id': factory.donation_option_id,
                'name': 'testing donation option',
                'category_name': 'Supper Clubs',
                'live': True,
                'amount': 20.0,
            },
        ],
        'count': 1,
        'pages': 1,
    }


async def test_bread_retrieve(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_donation_option()

    await login()

    r = await cli.get(url('donation-options-retrieve', pk=factory.donation_option_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'id': factory.donation_option_id,
        'name': 'testing donation option',
        'category_name': 'Supper Clubs',
        'live': True,
        'amount': 20.0,
        'category': factory.category_id,
        'sort_index': None,
        'short_description': 'This is the short_description.',
        'long_description': 'This is the long_description.',
        'image': None,
    }


async def test_bread_add(cli, url, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()

    await login()

    data = {
        'category': factory.category_id,
        'name': 'Testing Donation Options',
        'amount': 25,
        'short_description': 'short_description',
        'long_description': 'long_description',
    }
    r = await cli.json_post(url('donation-options-add'), data=data)
    assert r.status == 201, await r.text()
    data = await r.json()
    pk = data['pk']
    d = await db_conn.fetchrow('SELECT * FROM donation_options WHERE id=$1', pk)
    assert dict(d) == {
        'id': pk,
        'category': factory.category_id,
        'name': 'Testing Donation Options',
        'amount': 25,
        'sort_index': None,
        'live': True,
        'image': None,
        'short_description': 'short_description',
        'long_description': 'long_description',
    }


async def test_bread_edit(cli, url, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_donation_option()

    await login()

    data = {
        'amount': 123,
        'long_description': 'this is different',
    }
    r = await cli.json_post(url('donation-options-edit', pk=factory.donation_option_id), data=data)
    assert r.status == 200, await r.text()
    d = await db_conn.fetchrow('SELECT amount, long_description FROM donation_options')
    assert dict(d) == {
        'amount': 123,
        'long_description': 'this is different',
    }


async def test_bread_delete(cli, url, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_donation_option()

    await login()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM donation_options')
    r = await cli.json_post(url('donation-options-delete', pk=factory.donation_option_id))
    assert r.status == 200, await r.text()
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM donation_options')


async def test_add_image(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_donation_option()
    await login()
    assert None is await db_conn.fetchval('SELECT image FROM donation_options')
    data = FormData()
    data.add_field('image', create_image(700, 500), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('donation-image-upload', pk=factory.donation_option_id),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        },
    )
    assert r.status == 200, await r.text()
    assert sorted(dummy_server.app['images']) == [
        (
            RegexStr(r'/aws_endpoint_url/testingbucket.example.org/tests/testing/supper-clubs/\d+/\w+/main.png'),
            672,
            480,
        ),
        (
            RegexStr(r'/aws_endpoint_url/testingbucket.example.org/tests/testing/supper-clubs/\d+/\w+/thumb.png'),
            400,
            200,
        ),
    ]
    assert None is not await db_conn.fetchval('SELECT image FROM donation_options')
    assert sum('DELETE aws_endpoint_url/' in e for e in dummy_server.app['log']) == 0


async def test_add_image_delete_old(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_donation_option()
    await login()
    await db_conn.execute("UPDATE donation_options SET image='testing'")
    data = FormData()
    data.add_field('image', create_image(700, 500), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('donation-image-upload', pk=factory.donation_option_id),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        },
    )
    assert r.status == 200, await r.text()
    assert sum('DELETE aws_endpoint_url/' in e for e in dummy_server.app['log']) == 2


async def test_add_image_wrong_id(cli, url, factory: Factory, db_conn, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await login()
    assert None is await db_conn.fetchval('SELECT image FROM donation_options')
    data = FormData()
    data.add_field('image', create_image(700, 500), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('donation-image-upload', pk=999),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        },
    )
    assert r.status == 404, await r.text()


async def test_list_donations(cli, url, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await factory.create_donation_option()
    await factory.create_donation()
    await login()

    r = await cli.get(url('donation-opt-donations', pk=factory.donation_option_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'donations': [
            {
                'id': factory.donation_id,
                'amount': 20.0,
                'first_name': 'Foo',
                'last_name': 'Bar',
                'address': None,
                'city': None,
                'postcode': None,
                'gift_aid': False,
                'user_id': factory.user_id,
                'user_first_name': 'Frank',
                'user_last_name': 'Spencer',
                'user_email': 'frank@example.org',
                'ts': CloseToNow(delta=3),
                'event_id': factory.event_id,
                'event_name': 'The Event Name',
            },
        ],
    }


async def test_list_donations_wrong_id(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await login()

    r = await cli.get(url('donation-opt-donations', pk=999))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {'donations': []}


async def test_list_donations_wrong_role(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(role='host')
    await factory.create_event()
    await login()

    r = await cli.get(url('donation-opt-donations', pk=999))
    assert r.status == 403, await r.text()
    data = await r.json()
    assert data == {'message': 'role must be: admin'}


async def test_wrong_donation_option(factory: Factory, cli, url, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await factory.create_event(price=10)
    await login()

    r = await cli.json_post(url('donation-after-prepare', don_opt_id=999, event_id=factory.event_id))
    assert r.status == 400, await r.text()
    assert {'message': 'donation option not found'} == await r.json()


async def test_wrong_event(factory: Factory, cli, url, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await factory.create_donation_option()
    await login()
    cat2 = await factory.create_cat(slug='cat2')
    await factory.create_event(price=10, category_id=cat2)

    r = await cli.json_post(
        url('donation-after-prepare', don_opt_id=factory.donation_option_id, event_id=factory.event_id)
    )
    assert r.status == 400, await r.text()
    assert {'message': 'event not found on the same category as donation_option'} == await r.json()


async def test_donate_gift_aid_no_name(factory: Factory, cli, url, login):
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
    data = await r.json()

    post_data = dict(title='Mr', first_name='Joe', address='Testing Street', city='Testingville', postcode='TE11 0ST')
    r = await cli.json_post(url('donation-gift-aid', action_id=data['action_id']), data=post_data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'Invalid Data',
        'details': [{'loc': ['last_name'], 'msg': 'field required', 'type': 'value_error.missing'}],
    }


async def test_gift_aid_good(factory: Factory, cli, url, login, db_conn):
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

    extra = json.loads(await db_conn.fetchval('select extra from actions where id=$1', action_id))
    assert extra.keys() == {'ip', 'ua', 'url', 'donation_option_id'}

    post_data = dict(title='0', first_name='1', last_name='2', address='3', city='4', postcode='5')
    r = await cli.json_post(url('donation-gift-aid', action_id=action_id), data=post_data)
    assert r.status == 200, await r.text()

    extra = json.loads(await db_conn.fetchval('select extra from actions where id=$1', action_id))
    assert extra.keys() == {'ip', 'ua', 'url', 'donation_option_id', 'gift_aid'}
    assert extra['gift_aid'] == {
        'title': '0',
        'first_name': '1',
        'last_name': '2',
        'address': '3',
        'city': '4',
        'postcode': '5',
    }


async def test_gift_aid_no_action(factory: Factory, cli, url, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await factory.create_event(price=10)
    await factory.create_donation_option()
    await login()

    post_data = dict(title='0', first_name='1', last_name='2', address='3', city='4', postcode='5')
    r = await cli.json_post(url('donation-gift-aid', action_id=0), data=post_data)
    assert r.status == 404, await r.text()
    assert await r.json() == {'message': 'action not found'}


async def test_gift_aid_wrong_user(factory: Factory, cli, url, login):
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

    await factory.create_user(email='other@example.com')
    await login(email='other@example.com')

    post_data = dict(title='0', first_name='1', last_name='2', address='3', city='4', postcode='5')
    r = await cli.json_post(url('donation-gift-aid', action_id=action_id), data=post_data)
    assert r.status == 404, await r.text()
    assert await r.json() == {'message': 'action not found'}
