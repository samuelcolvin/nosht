import json

from pytest_toolbox.comparison import AnyInt, CloseToNow, RegexStr

from shared.actions import ActionTypes

from .conftest import Factory


async def test_donate_direct(cli, url, dummy_server, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat(slug='cat')
    await factory.create_user()
    await factory.create_event(slug='evt', allow_donations=True, suggested_donation=123, status='published')

    factory.user_id = await factory.create_user(first_name='do', last_name='nor', email='donor@example.org')
    await login('donor@example.org')

    r = await cli.get(url('event-donating-info-public', category='cat', event='evt'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'ticket_types': [
            {'id': factory.donation_ticket_type_id_1, 'name': 'Standard', 'amount': 123, 'custom_amount': False},
            {'id': factory.donation_ticket_type_id_2, 'name': 'Custom Amount', 'amount': None, 'custom_amount': True},
        ],
    }

    tt_id = factory.donation_ticket_type_id_1
    r = await cli.json_post(url('donation-direct-prepare', tt_id=tt_id), data=dict(custom_amount=2))
    assert r.status == 200, await r.text()

    action_id, extra = await db_conn.fetchrow(
        'select id, extra from actions where type=$1', ActionTypes.donate_direct_prepare
    )
    data = await r.json()
    assert data == {
        'client_secret': f'payment_intent_secret_{action_id}',
        'action_id': action_id,
    }
    assert json.loads(extra) == {
        'ip': '127.0.0.1',
        'ua': RegexStr('Python.+'),
        'url': RegexStr(r'http://127.0.0.1:\d+/api/donation-prepare/\d+/'),
        'ticket_type_id': factory.donation_ticket_type_id_1,
        'donation_amount': 123,
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

    await factory.fire_stripe_webhook(action_id, amount=123_00, purpose='donate-direct')

    assert dummy_server.app['log'] == [
        'POST stripe_root_url/customers',
        'POST stripe_root_url/payment_intents',
        ('email_send_endpoint', 'Subject: "Thanks for your donation", To: "do nor <donor@example.org>"'),
    ]
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')
    r = await db_conn.fetchrow('SELECT * FROM donations')
    assert dict(r) == {
        'id': AnyInt(),
        'donation_option': factory.donation_option_id,
        'ticket_type': tt_id,
        'amount': 123,
        'gift_aid': True,
        'title': 'Mr',
        'first_name': 'Joe',
        'last_name': 'Blogs',
        'address': 'Testing Street',
        'city': 'Testingville',
        'postcode': 'TE11 0ST',
        'action': AnyInt(),
        'cancel_action': None,
        'status': 'accepted',
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
            'purpose': 'donate-direct',
            'user_id': factory.user_id,
            'event_id': factory.event_id,
            'reserve_action_id': action_id,
        },
    }
    assert len(dummy_server.app['emails']) == 1
    email = dummy_server.app['emails'][0]
    assert email['To'] == 'do nor <donor@example.org>'
    assert email['part:text/plain'] == (
        'Hi do,\n'
        '\n'
        'Thanks for your donation to The Event Name of £123.00.\n'
        '\n'
        'You have allowed us to collect gift aid meaning we can collect %25 on top of your original donation.\n'
        '\n'
        '_(Card Charged: Visa 12/32 - ending 1234)_\n'
    )


async def test_prepare_missing_tt(cli, url, dummy_server, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat(slug='cat')
    await factory.create_user()
    await factory.create_event(slug='evt', allow_donations=True, suggested_donation=123, status='published')

    factory.user_id = await factory.create_user(first_name='do', last_name='nor', email='donor@example.org')
    await login('donor@example.org')

    r = await cli.json_post(url('donation-direct-prepare', tt_id=999), data=dict(custom_amount=2))
    assert r.status == 400, await r.text()
    assert await r.json() == {'message': 'Ticket type not found'}


async def test_prepare_custom_amount(cli, url, dummy_server, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat(slug='cat')
    await factory.create_user()
    await factory.create_event(slug='evt', allow_donations=True, suggested_donation=123, status='published')

    factory.user_id = await factory.create_user(first_name='do', last_name='nor', email='donor@example.org')
    await login('donor@example.org')

    r = await cli.json_post(
        url('donation-direct-prepare', tt_id=factory.donation_ticket_type_id_2), data=dict(custom_amount=55)
    )
    assert r.status == 200, await r.text()

    action_id, extra = await db_conn.fetchrow(
        'select id, extra from actions where type=$1', ActionTypes.donate_direct_prepare
    )
    data = await r.json()
    assert data == {
        'client_secret': f'payment_intent_secret_{action_id}',
        'action_id': action_id,
    }
    assert json.loads(extra) == {
        'ip': '127.0.0.1',
        'ua': RegexStr('Python.+'),
        'url': RegexStr(r'http://127.0.0.1:\d+/api/donation-prepare/\d+/'),
        'ticket_type_id': factory.donation_ticket_type_id_2,
        'donation_amount': 55,
    }

    assert dummy_server.app['log'] == [
        'POST stripe_root_url/customers',
        'POST stripe_root_url/payment_intents',
    ]


async def test_refund_donation(cli, url, dummy_server, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat(slug='cat')
    await factory.create_user()
    await factory.create_event(slug='evt', status='published', allow_donations=True, suggested_donation=123)
    donor = dict(first_name='Joe', last_name='Blogs')
    donor_details = dict(**donor, title='Mr', address='Testing Street', city='Testingville', postcode='TE11 0ST')
    donor_email = 'donor@example.org'
    tt_id = factory.donation_ticket_type_id_1
    donation_amount = 123
    factory.user_id = await factory.create_user(**donor, email=donor_email)
    await login(donor_email)

    # Prepare the donation
    r = await cli.json_post(url('donation-direct-prepare', tt_id=tt_id), data=dict(custom_amount=2))
    assert r.status == 200, await r.text()
    action_id = await db_conn.fetchval('select id from actions where type=$1', ActionTypes.donate_direct_prepare)

    # Pay for donation
    r = await cli.json_post(url('donation-gift-aid', action_id=action_id), data=donor_details)
    assert r.status == 200, await r.text()
    await factory.fire_stripe_webhook(action_id, amount=donation_amount * 100, purpose='donate-direct')
    donation = await db_conn.fetchrow('SELECT * FROM donations WHERE first_name = $1', donor['first_name'])
    assert dict(donation) == {
        'id': AnyInt(),
        'donation_option': factory.donation_option_id,
        'ticket_type': tt_id,
        'amount': donation_amount,
        'gift_aid': True,
        'action': AnyInt(),
        'cancel_action': None,
        'status': 'accepted',
        **donor_details,
    }
    donation_action = await db_conn.fetchrow('SELECT * FROM actions WHERE id= $1', donation['action'])
    assert dict(donation_action) == {
        'id': AnyInt(),
        'company': factory.company_id,
        'user_id': factory.user_id,
        'event': factory.event_id,
        'ts': CloseToNow(delta=3),
        'type': 'donate',
        'extra': RegexStr(r'{.*}'),
    }

    # Refund donation
    r = await cli.json_post(url('donation-refund', tid=donation['id']), data=dict(refund_amount=donation_amount))
    assert r.status == 200

    # Check refund recorded
    assert 'POST stripe_root_url/refunds' in dummy_server.app['log']
    cancel_action = await db_conn.fetchrow('SELECT * FROM actions WHERE type=$1', ActionTypes.donate_refund)
    rd = await db_conn.fetchrow('SELECT * FROM donations AS d WHERE d.cancel_action = $1', cancel_action['id'])
    assert rd['status'] == 'refunded'


async def test_refund_donation_wrong_amount(cli, url, dummy_server, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat(slug='cat')
    await factory.create_user()
    await factory.create_event(slug='evt', status='published', allow_donations=True, suggested_donation=123)
    donor = dict(first_name='Joe', last_name='Blogs')
    donor_details = dict(**donor, title='Mr', address='Testing Street', city='Testingville', postcode='TE11 0ST')
    donor_email = 'donor@example.org'
    tt_id = factory.donation_ticket_type_id_1
    donation_amount = 123
    factory.user_id = await factory.create_user(**donor, email=donor_email)
    await login(donor_email)

    # Prepare the donation
    r = await cli.json_post(url('donation-direct-prepare', tt_id=tt_id), data=dict(custom_amount=2))
    assert r.status == 200, await r.text()
    action_id = await db_conn.fetchval('select id from actions where type=$1', ActionTypes.donate_direct_prepare)

    # Pay for donation
    r = await cli.json_post(url('donation-gift-aid', action_id=action_id), data=donor_details)
    assert r.status == 200, await r.text()
    await factory.fire_stripe_webhook(action_id, amount=donation_amount * 100, purpose='donate-direct')
    donation = await db_conn.fetchrow('SELECT * FROM donations WHERE first_name = $1', donor['first_name'])

    # Refund donation with excess
    r = await cli.json_post(url('donation-refund', tid=donation['id']), data=dict(refund_amount=200))
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': f'Refund amount cannot exceed {donation_amount}.00.'}
