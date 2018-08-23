import hashlib
import json
import os

import pytest
from aiohttp import BasicAuth
from pytest_toolbox.comparison import CloseToNow, RegexStr

from web.stripe import Reservation, StripeBuyModel, stripe_buy, stripe_request
from web.utils import encrypt_json

from .conftest import Factory

stripe_public_key = 'pk_test_PMjnIfWjalY8jr4pkm1pexwR'
stripe_secret_key = 'sk_test_WZT0Ntpze4QB8oeQIGeXAYsG'
# real_stripe_test is also used in the settings fixture to change stripe_root_url
real_stripe_test = pytest.mark.skipif(not os.getenv('REAL_STRIPE_TESTS'), reason='requires REAL_STRIPE_TESTS env var')


@real_stripe_test
async def test_stripe_successful(cli, db_conn, factory: Factory):
    await factory.create_company(stripe_public_key=stripe_public_key, stripe_secret_key=stripe_secret_key)
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(ticket_limit=10, price=10)

    res: Reservation = await factory.create_reservation()
    app = cli.app['main_app']

    m = StripeBuyModel(
        stripe=dict(
            token='tok_visa',
            client_ip='0.0.0.0',
            card_ref='4242-32-01',
        ),
        booking_token=encrypt_json(app, res.dict()),
        grecaptcha_token='__ok__',
    )
    await db_conn.execute('SELECT check_tickets_remaining($1, 10)', res.event_id)
    customer_id = await db_conn.fetchval('SELECT stripe_customer_id FROM users WHERE id=$1', factory.user_id)
    assert customer_id is None

    ticket_limit, tickets_taken = await db_conn.fetchrow(
        'SELECT ticket_limit, tickets_taken FROM events where id=$1',
        factory.event_id
    )
    assert (ticket_limit, tickets_taken) == (10, 1)

    action_id, new_source_hash = await stripe_buy(m, factory.company_id, factory.user_id, app, db_conn)

    customer_id = await db_conn.fetchval('SELECT stripe_customer_id FROM users WHERE id=$1', factory.user_id)
    assert customer_id is not None
    assert customer_id.startswith('cus_')

    ticket_limit, tickets_taken = await db_conn.fetchrow(
        'SELECT ticket_limit, tickets_taken FROM events where id=$1',
        factory.event_id
    )
    assert (ticket_limit, tickets_taken) == (10, 1)

    booked_action = await db_conn.fetchrow("SELECT * FROM actions WHERE type='buy-tickets'")

    assert booked_action['id'] == action_id
    assert new_source_hash is not None
    assert booked_action['company'] == factory.company_id
    assert booked_action['user_id'] == factory.user_id
    assert booked_action['ts'] == CloseToNow(delta=10)
    extra = json.loads(booked_action['extra'])
    assert extra == {
        'new_card': True,
        'new_customer': True,
        'charge_id': RegexStr('ch_.+'),
        'brand': 'Visa',
        'card_expiry': RegexStr('\d+/\d+'),
        'card_last4': '4242',
    }

    charge = await stripe_request(app, BasicAuth(stripe_secret_key), 'get', f'charges/{extra["charge_id"]}')
    # debug(d)
    assert charge['amount'] == 10_00
    assert charge['description'] == f'1 tickets for Foobar ({factory.event_id})'
    assert charge['metadata'] == {
        'purpose': 'buy-tickets',
        'event': str(factory.event_id),
        'tickets_bought': '1',
        'booked_action': str(booked_action['id']),
        'reserve_action': str(res.action_id),
    }
    assert charge['source']['last4'] == '4242'


@real_stripe_test
async def test_stripe_existing_customer_card(cli, db_conn, factory: Factory):
    await factory.create_company(stripe_public_key=stripe_public_key, stripe_secret_key=stripe_secret_key)
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(ticket_limit=10, price=10)

    res: Reservation = await factory.create_reservation()
    app = cli.app['main_app']

    customers = await stripe_request(app, BasicAuth(stripe_secret_key), 'get', 'customers?limit=1')
    customer = customers['data'][0]
    customer_id = customer['id']
    await db_conn.execute('UPDATE users SET stripe_customer_id=$1 WHERE id=$2', customer_id, factory.user_id)

    m = StripeBuyModel(
        stripe=dict(
            token='tok_visa',
            client_ip='0.0.0.0',
            card_ref='{last4}-{exp_year}-{exp_month}'.format(**customer['sources']['data'][0]),
        ),
        booking_token=encrypt_json(app, res.dict()),
        grecaptcha_token='__ok__',
    )

    await stripe_buy(m, factory.company_id, factory.user_id, app, db_conn)

    new_customer_id = await db_conn.fetchval('SELECT stripe_customer_id FROM users WHERE id=$1', factory.user_id)
    assert new_customer_id == customer_id

    extra = await db_conn.fetchval("SELECT extra FROM actions WHERE type='buy-tickets'")

    extra = json.loads(extra)
    assert extra == {
        'new_card': False,
        'new_customer': False,
        'charge_id': RegexStr('ch_.+'),
        'brand': 'Visa',
        'card_expiry': RegexStr('\d+/\d+'),
        'card_last4': '4242',
    }


@real_stripe_test
async def test_stripe_saved_card(cli, db_conn, factory: Factory):
    await factory.create_company(stripe_public_key=stripe_public_key, stripe_secret_key=stripe_secret_key)
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=10)

    res: Reservation = await factory.create_reservation()
    app = cli.app['main_app']

    customers = await stripe_request(app, BasicAuth(stripe_secret_key), 'get', 'customers?limit=1')
    customer = customers['data'][0]
    customer_id = customer['id']
    await db_conn.execute('UPDATE users SET stripe_customer_id=$1 WHERE id=$2', customer_id, factory.user_id)
    source_id = customer['sources']['data'][0]['id']
    source_hash = hashlib.sha1(source_id.encode()).hexdigest()

    m = StripeBuyModel(
        stripe=dict(
            source_hash=source_hash,
        ),
        booking_token=encrypt_json(app, res.dict()),
        grecaptcha_token='__ok__',
    )

    action_id, new_source_hash = await stripe_buy(m, factory.company_id, factory.user_id, app, db_conn)

    new_customer_id = await db_conn.fetchval('SELECT stripe_customer_id FROM users WHERE id=$1', factory.user_id)
    assert new_customer_id == customer_id

    assert action_id == await db_conn.fetchval("SELECT id FROM actions WHERE type='buy-tickets'")
    assert new_source_hash is None


async def test_pay_cli(cli, url, dummy_server, factory: Factory):
    await factory.create_company(stripe_public_key=stripe_public_key, stripe_secret_key=stripe_secret_key)
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=12.5)

    res: Reservation = await factory.create_reservation()
    app = cli.app['main_app']
    data = dict(
        stripe=dict(
            token='tok_visa',
            client_ip='0.0.0.0',
            card_ref='4242-32-01',
        ),
        booking_token=encrypt_json(app, res.dict()),
        grecaptcha_token='__ok__',
    )

    r = await cli.json_post(url('event-buy-tickets'), data=data)
    assert r.status == 200, await r.text()

    assert dummy_server.app['log'] == [
        ('grecaptcha', '__ok__'),
        'POST stripe_root_url/customers',
        'POST stripe_root_url/charges',
        (
            'email_send_endpoint',
            'Subject: "The Event Name Ticket Confirmation", To: "Frank Spencer <frank@example.org>"',
        ),
    ]


async def test_existing_customer_fake(cli, url, dummy_server, factory: Factory):
    await factory.create_company(stripe_public_key=stripe_public_key, stripe_secret_key=stripe_secret_key)
    await factory.create_cat()
    await factory.create_user(stripe_customer_id='xxx')
    await factory.create_event(price=12.5)

    res: Reservation = await factory.create_reservation(factory.user_id, None)
    app = cli.app['main_app']
    data = dict(
        stripe=dict(
            token='tok_visa',
            client_ip='0.0.0.0',
            card_ref='4242-32-01',
        ),
        booking_token=encrypt_json(app, res.dict()),
        grecaptcha_token='__ok__',
    )

    r = await cli.json_post(url('event-buy-tickets'), data=data)
    assert r.status == 200, await r.text()

    assert dummy_server.app['log'] == [
        ('grecaptcha', '__ok__'),
        'GET stripe_root_url/customers/xxx/sources',
        'POST stripe_root_url/customers/xxx/sources',
        'POST stripe_root_url/charges',
        (
            'email_send_endpoint',
            'Subject: "The Event Name Ticket Confirmation", To: "Frank Spencer <frank@example.org>"',
        ),
    ]


async def test_pay_no_price(cli, url, factory: Factory):
    await factory.create_company(stripe_public_key=stripe_public_key, stripe_secret_key=stripe_secret_key)
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=None)

    res: Reservation = await factory.create_reservation()
    app = cli.app['main_app']
    data = dict(
        stripe=dict(
            token='tok_visa',
            client_ip='0.0.0.0',
            card_ref='4242-32-01',
        ),
        booking_token=encrypt_json(app, res.dict()),
        grecaptcha_token='__ok__',
    )

    r = await cli.json_post(url('event-buy-tickets'), data=data)
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'booking price cent < 100',
    }


async def test_book_free(cli, url, dummy_server, factory: Factory):
    await factory.create_company(stripe_public_key=stripe_public_key, stripe_secret_key=stripe_secret_key)
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=None)

    res: Reservation = await factory.create_reservation()
    app = cli.app['main_app']

    data = dict(
        booking_token=encrypt_json(app, res.dict()),
        grecaptcha_token='__ok__',
    )
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 200, await r.text()

    assert dummy_server.app['log'] == [
        ('grecaptcha', '__ok__'),
        (
            'email_send_endpoint',
            'Subject: "The Event Name Ticket Confirmation", To: "Frank Spencer <frank@example.org>"',
        ),
    ]


async def test_book_free_with_price(cli, url, factory: Factory):
    await factory.create_company(stripe_public_key=stripe_public_key, stripe_secret_key=stripe_secret_key)
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=10)

    res: Reservation = await factory.create_reservation()
    app = cli.app['main_app']

    data = dict(
        booking_token=encrypt_json(app, res.dict()),
        grecaptcha_token='__ok__',
    )
    r = await cli.json_post(url('event-book-tickets'), data=data)
    assert r.status == 400, await r.text()

    data = await r.json()
    assert data == {
        'message': 'booking not free',
    }
