import json
import os

import pytest
from aiohttp import BasicAuth
from buildpg import Values
from pytest_toolbox.comparison import CloseToNow, RegexStr

from web.utils import encrypt_json
from web.stripe import Reservation, StripePayModel, stripe_pay, stripe_request
from .conftest import Factory

stripe_public_key = 'pk_test_PMjnIfWjalY8jr4pkm1pexwR'
stripe_secret_key = 'sk_test_WZT0Ntpze4QB8oeQIGeXAYsG'
real_stripe_test = pytest.mark.skipif(not os.getenv('REAL_STRIPE_TESTS'), reason='requires REAL_STRIPE_TESTS env var')


@pytest.fixture
def stripe_factory(factory, db_conn):
    async def create_reservation():
        action_id = await db_conn.fetchval_b(
            'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
            values=Values(
                company=factory.company_id,
                user_id=factory.user_id,
                type='reserve-tickets'
            )
        )
        await db_conn.execute_b(
            'INSERT INTO tickets (:values__names) VALUES :values',
            values=Values(
                event=factory.event_id,
                user_id=factory.user_id,
                reserve_action=action_id,
            )
        )
        return Reservation(
            user_id=factory.user_id,
            action_id=action_id,
            event_id=factory.event_id,
            price_cent=10_00,
            ticket_count=1,
            event_name='Foobar',
        )

    factory.create_reservation = create_reservation
    return factory


@real_stripe_test
async def test_stripe_successful(cli, db_conn, stripe_factory: Factory):
    await stripe_factory.create_company(stripe_public_key=stripe_public_key, stripe_secret_key=stripe_secret_key)
    await stripe_factory.create_cat()
    await stripe_factory.create_user()
    await stripe_factory.create_event(ticket_limit=10)

    res: Reservation = await stripe_factory.create_reservation()
    app = cli.app['main_app']

    m = StripePayModel(
        stripe_token='tok_visa',
        stripe_client_ip='0.0.0.0',
        stripe_card_ref='4242-32-01',
        booking_token=encrypt_json(app, res.dict()),
    )
    await db_conn.execute('SELECT check_tickets_remaining($1)', res.event_id)
    customer_id = await db_conn.fetchval('SELECT stripe_customer_id FROM users WHERE id=$1', stripe_factory.user_id)
    assert customer_id is None

    ticket_limit, tickets_taken = await db_conn.fetchrow(
        'SELECT ticket_limit, tickets_taken FROM events where id=$1',
        stripe_factory.event_id
    )
    assert (ticket_limit, tickets_taken) == (10, 1)

    await stripe_pay(m, stripe_factory.company_id, stripe_factory.user_id, app, db_conn)

    customer_id = await db_conn.fetchval('SELECT stripe_customer_id FROM users WHERE id=$1', stripe_factory.user_id)
    assert customer_id is not None
    assert customer_id.startswith('cus_')

    ticket_limit, tickets_taken = await db_conn.fetchrow(
        'SELECT ticket_limit, tickets_taken FROM events where id=$1',
        stripe_factory.event_id
    )
    assert (ticket_limit, tickets_taken) == (10, 1)

    paid_action = await db_conn.fetchrow("SELECT * FROM actions WHERE type='buy-tickets'")

    assert paid_action['company'] == stripe_factory.company_id
    assert paid_action['user_id'] == stripe_factory.user_id
    assert paid_action['ts'] == CloseToNow(delta=10)
    extra = json.loads(paid_action['extra'])
    assert extra == {
        'new_card': True,
        'new_customer': True,
        'charge_id': RegexStr('ch_.+')
    }

    charge = await stripe_request(app, BasicAuth(stripe_secret_key), 'get', f'charges/{extra["charge_id"]}')
    # debug(d)
    assert charge['amount'] == 10_00
    assert charge['description'] == f'1 tickets for Foobar ({stripe_factory.event_id})'
    assert charge['metadata'] == {
        'event': str(stripe_factory.event_id),
        'tickets_bought': '1',
        'paid_action': str(paid_action['id']),
        'reserve_action': str(res.action_id),
    }
    assert charge['source']['last4'] == '4242'


@real_stripe_test
async def test_stripe_existing_customer_card(cli, db_conn, stripe_factory: Factory):
    await stripe_factory.create_company(stripe_public_key=stripe_public_key, stripe_secret_key=stripe_secret_key)
    await stripe_factory.create_cat()
    await stripe_factory.create_user()
    await stripe_factory.create_event(ticket_limit=10)

    res: Reservation = await stripe_factory.create_reservation()
    app = cli.app['main_app']

    customers = await stripe_request(app, BasicAuth(stripe_secret_key), 'get', 'customers?limit=1')
    customer = customers['data'][0]
    customer_id = customer['id']
    await db_conn.execute('UPDATE users SET stripe_customer_id=$1 WHERE id=$2', customer_id, stripe_factory.user_id)

    m = StripePayModel(
        stripe_token='tok_visa',
        stripe_client_ip='0.0.0.0',
        stripe_card_ref='{last4}-{exp_year}-{exp_month}'.format(**customer['sources']['data'][0]),
        booking_token=encrypt_json(app, res.dict()),
    )

    await stripe_pay(m, stripe_factory.company_id, stripe_factory.user_id, app, db_conn)

    new_customer_id = await db_conn.fetchval('SELECT stripe_customer_id FROM users WHERE id=$1', stripe_factory.user_id)
    assert new_customer_id == customer_id

    extra = await db_conn.fetchval("SELECT extra FROM actions WHERE type='buy-tickets'")

    extra = json.loads(extra)
    assert extra == {
        'new_card': False,
        'new_customer': False,
        'charge_id': RegexStr('ch_.+')
    }
