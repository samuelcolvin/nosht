import os

import pytest
from pytest_toolbox.comparison import AnyInt, RegexStr

from shared.actions import ActionTypes
from web.stripe import Reservation, StripeClient, stripe_buy_intent, stripe_refund
from web.utils import JsonErrors

from .conftest import Factory

stripe_public_key = 'pk_test_PMjnIfWjalY8jr4pkm1pexwR'
stripe_secret_key = 'sk_test_WZT0Ntpze4QB8oeQIGeXAYsG'
# real_stripe_test is also used in the settings fixture to change stripe_root_url
real_stripe_test = pytest.mark.skipif(not os.getenv('REAL_STRIPE_TESTS'), reason='requires REAL_STRIPE_TESTS env var')


@real_stripe_test
async def test_real_intent(cli, url, login, db_conn, factory: Factory):
    await factory.create_company(stripe_public_key=stripe_public_key, stripe_secret_key=stripe_secret_key)
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', price=123.45)

    await login()
    data = {
        'tickets': [
            {'t': True, 'first_name': 'Ticket', 'last_name': 'Buyer', 'email': 'ticket.buyer@example.org'},
            {'t': True, 'email': 'different@example.org'},
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    response_data = await r.json()
    assert response_data == {
        'booking_token': RegexStr(r'.+'),
        'ticket_count': 2,
        'extra_donated': None,
        'item_price': 123.45,
        'total_price': 246.90,
        'timeout': AnyInt(),
        'client_secret': RegexStr(r'pi_.*'),
        'action_id': AnyInt(),
    }
    customer_id = await db_conn.fetchval('SELECT stripe_customer_id FROM users WHERE id=$1', factory.user_id)
    assert customer_id is not None
    assert customer_id.startswith('cus_')

    app = cli.app['main_app']
    r = await StripeClient(app, stripe_secret_key).get(f'payment_intents?limit=3&customer={customer_id}')

    assert len(r['data']) == 1
    payment_intent = r['data'][0]
    assert payment_intent['amount'] == 246_90
    assert payment_intent['description'] == f'2 tickets for The Event Name ({factory.event_id})'
    assert payment_intent['metadata'] == {
        'purpose': 'buy-tickets',
        'event_id': str(factory.event_id),
        'tickets_bought': '2',
        'reserve_action_id': str(response_data['action_id']),
        'user_id': str(factory.user_id),
    }


@real_stripe_test
async def test_real_refund(cli, url, login, db_conn, factory: Factory):
    await factory.create_company(stripe_public_key=stripe_public_key, stripe_secret_key=stripe_secret_key)
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', price=10)

    await login()
    data = {
        'tickets': [
            {'t': True, 'first_name': 'Ticket', 'last_name': 'Buyer', 'email': 'ticket.buyer@example.org'},
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    reserve_action_id = (await r.json())['action_id']
    customer_id = await db_conn.fetchval('SELECT stripe_customer_id FROM users WHERE id=$1', factory.user_id)

    app = cli.app['main_app']
    stripe = StripeClient(app, stripe_secret_key)

    r = await stripe.get(f'payment_intents?limit=3&customer={customer_id}')
    assert len(r['data']) == 1
    payment_intent_id = r['data'][0]['id']

    r = await stripe.post(
        f'payment_intents/{payment_intent_id}/confirm',
        payment_method='pm_card_visa'
    )
    assert r['status'] == 'succeeded'
    charge_id = r['charges']['data'][0]['id']

    await factory.fire_stripe_webhook(reserve_action_id, charge_id=charge_id)

    ticket_id, booking_type, price, ticket_charge_id = await db_conn.fetchrow(
        """
        select t.id, a.type, t.price, a.extra->>'charge_id'
        from tickets as t
        join actions as a on t.booked_action = a.id
        where t.event = $1 and t.status = 'booked' and a.type=$2
        """,
        factory.event_id,
        ActionTypes.buy_tickets,
    )
    assert ticket_charge_id == charge_id
    assert price == 10
    refund = await stripe_refund(
        refund_charge_id=charge_id,
        ticket_id=ticket_id,
        amount=910,
        user_id=factory.user_id,
        company_id=factory.company_id,
        app=app,
        conn=db_conn,
    )
    assert refund['object'] == 'refund'
    assert refund['amount'] == 910
    assert refund['charge'] == charge_id
    assert refund['currency'] == 'gbp'
    assert refund['reason'] == 'requested_by_customer'


async def test_pay_cli(cli, url, login, dummy_server, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', price=10)

    await login()
    data = {
        'tickets': [
            {'t': True, 'email': 'frank@example.org'},
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    action_id = (await r.json())['action_id']

    await factory.fire_stripe_webhook(action_id)

    assert dummy_server.app['log'] == [
        'POST stripe_root_url/customers',
        'POST stripe_root_url/payment_intents',
        (
            'email_send_endpoint',
            'Subject: "The Event Name Ticket Confirmation", To: "Frank Spencer <frank@example.org>"',
        ),
    ]
    assert await db_conn.fetchval("SELECT id FROM actions WHERE type='buy-tickets'")


async def test_existing_customer(cli, url, login, dummy_server, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(stripe_customer_id='xxx')
    await factory.create_event(status='published', price=10)

    await login()
    data = {
        'tickets': [
            {'t': True, 'email': 'frank@example.org'},
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()

    assert dummy_server.app['log'] == [
        'GET stripe_root_url/customers/xxx',
        'POST stripe_root_url/payment_intents',
    ]


async def test_existing_customer_no_customer(cli, url, login, dummy_server, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(stripe_customer_id='missing')
    await factory.create_event(status='published', price=10)

    await login()
    data = {
        'tickets': [
            {'t': True, 'email': 'frank@example.org'},
        ],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()

    assert dummy_server.app['log'] == [
        'GET stripe_root_url/customers/missing',
        'POST stripe_root_url/customers',
        'POST stripe_root_url/payment_intents',
    ]


async def test_price_low(cli, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(price=10)

    res: Reservation = await factory.create_reservation()
    res.price_cent = 1
    with pytest.raises(JsonErrors.HTTPBadRequest) as exc_info:
        await stripe_buy_intent(res, factory.company_id, cli.app['main_app'], db_conn)

    assert exc_info.value.text == '{\n  "message": "booking price cent < 100"\n}\n'
