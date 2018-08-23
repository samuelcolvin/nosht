import json

from pytest_toolbox.comparison import AnyInt, CloseToNow, RegexStr

from .conftest import Factory


async def test_donate_with_gift_aid(cli, url, dummy_server, factory: Factory, login, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event()
    await factory.create_donation_option()

    u2 = await factory.create_user(first_name='other', last_name='person', email='other.person@example.org')
    await login('other.person@example.org')

    data = dict(
        stripe=dict(
            token='tok_visa',
            client_ip='0.0.0.0',
            card_ref='4242-32-01',
        ),
        donation_option_id=factory.donation_option_id,
        event_id=factory.event_id,
        gift_aid=True,
        address='Testing Street',
        city='Testingville',
        postcode='TE11 0ST',
        grecaptcha_token='__ok__',
    )
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')

    r = await cli.json_post(url('donate'), data=data)
    assert r.status == 200, await r.text()

    assert dummy_server.app['log'] == [
        ('grecaptcha', '__ok__'),
        ('grecaptcha', '__ok__'),
        'POST stripe_root_url/customers',
        'POST stripe_root_url/charges',
        ('email_send_endpoint', 'Subject: "Thanks for your donation", To: "other person <other.person@example.org>"')
    ]
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')
    r = await db_conn.fetchrow('SELECT * FROM donations')
    assert dict(r) == {
        'id': AnyInt(),
        'donation_option': factory.donation_option_id,
        'amount': 20,
        'gift_aid': True,
        'address': 'Testing Street',
        'city': 'Testingville',
        'postcode': 'TE11 0ST',
        'action': AnyInt(),
    }
    action = await db_conn.fetchrow('SELECT * FROM actions WHERE id= $1', r['action'])
    assert dict(action) == {
        'id': AnyInt(),
        'company': factory.company_id,
        'user_id': u2,
        'event': factory.event_id,
        'ts': CloseToNow(),
        'type': 'donate',
        'extra': RegexStr('{.*}'),
    }
    assert json.loads(action['extra']) == {
        'new_card': True,
        'charge_id': 'charge-id',
        'brand': 'Visa',
        'card_last4': '1234',
        'card_expiry': '12/32',
        'new_customer': True,
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

    data = dict(
        stripe=dict(
            token='tok_visa',
            client_ip='0.0.0.0',
            card_ref='4242-32-01',
        ),
        donation_option_id=factory.donation_option_id,
        event_id=factory.event_id,
        gift_aid=False,
        grecaptcha_token='__ok__',
    )
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')

    r = await cli.json_post(url('donate'), data=data)
    assert r.status == 200, await r.text()

    assert dummy_server.app['log'] == [
        ('grecaptcha', '__ok__'),
        ('grecaptcha', '__ok__'),
        'POST stripe_root_url/customers',
        'POST stripe_root_url/charges',
        ('email_send_endpoint', 'Subject: "Thanks for your donation", To: "Frank Spencer <frank@example.org>"')
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
