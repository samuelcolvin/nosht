import hashlib
import hmac
import json
import os
from time import time

import pytest
from pytest_toolbox.comparison import AnyInt, RegexStr

from shared.actions import ActionTypes
from shared.stripe_base import get_stripe_processing_fee
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
        'tickets': [{'t': True, 'first_name': 'Ticket', 'last_name': 'Buyer', 'email': 'ticket.buyer@example.org'}],
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

    r = await stripe.post(f'payment_intents/{payment_intent_id}/confirm', payment_method='pm_card_visa')
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


@real_stripe_test
async def test_get_payment_method(cli, url, login, factory: Factory):
    await factory.create_company(stripe_public_key=stripe_public_key, stripe_secret_key=stripe_secret_key)
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', price=10)

    await login()

    r = await cli.get(url('payment-method-details', payment_method='pm_card_amex'))
    assert r.status == 200, await r.text()  # both db customer_id and payment_method customer_id are None
    data = await r.json()
    assert data == {
        'card': {'brand': 'amex', 'exp_month': AnyInt(), 'exp_year': AnyInt(), 'last4': '8431'},
        'address': {'city': None, 'country': None, 'line1': None, 'line2': None, 'postal_code': None, 'state': None},
        'name': None,
    }


@real_stripe_test
async def test_real_webhook(cli, url, login, db_conn, factory: Factory, settings):
    await factory.create_company(stripe_public_key=stripe_public_key, stripe_secret_key=stripe_secret_key)
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', price=100)

    # so we can use the payment method below
    await db_conn.execute('update users set stripe_customer_id=$1 where id=$2', 'cus_FkTgDBtMnWyl3S', factory.user_id)

    await login()
    data = {
        'tickets': [{'t': True, 'email': 'frank@example.org'}],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    data = await r.json()
    client_secret = data['client_secret']
    payment_intent_id = client_secret[: client_secret.index('_secret_')]

    app = cli.app['main_app']
    stripe = StripeClient(app, stripe_secret_key)
    await stripe.post(f'payment_intents/{payment_intent_id}', payment_method='card_1FEzKsC8giHSw9x7rBL3xl0j')
    payment_intent = await stripe.post(f'payment_intents/{payment_intent_id}/confirm')

    data = {'type': 'payment_intent.succeeded', 'data': {'object': payment_intent}}
    body = json.dumps(data)
    t = int(time())
    sig = hmac.new(b'stripe_webhook_secret_xxx', f'{t}.{body}'.encode(), hashlib.sha256).hexdigest()

    assert not await db_conn.fetchval("SELECT id FROM actions WHERE type='buy-tickets'")

    r = await cli.post(url('stripe-webhook'), data=body, headers={'Stripe-Signature': f't={t},v1={sig}'})
    assert r.status == 204, await r.text()

    buy_action_id = await db_conn.fetchval("SELECT id FROM actions WHERE type='buy-tickets'")
    assert buy_action_id

    fee = await get_stripe_processing_fee(buy_action_id, stripe._client, settings, db_conn)
    assert f'{fee:0.2f}' == '1.60'

    await db_conn.execute("update companies set currency='usd'")
    assert 0 == await get_stripe_processing_fee(buy_action_id, stripe._client, settings, db_conn)


async def test_pay_cli(cli, url, login, dummy_server, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', price=10)

    await login()
    data = {
        'tickets': [{'t': True, 'email': 'frank@example.org'}],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    action_id = (await r.json())['action_id']

    assert 1 == await db_conn.fetchval('SELECT count(*) FROM tickets')
    assert 10 == await db_conn.fetchval('SELECT price FROM tickets')

    await factory.fire_stripe_webhook(action_id)

    assert dummy_server.app['log'] == [
        'POST stripe_root_url/customers',
        'POST stripe_root_url/payment_intents',
        (
            'email_send_endpoint',
            'Subject: "The Event Name Ticket Confirmation", To: "Frank Spencer <frank@example.org>"',
        ),
    ]
    assert 1 == await db_conn.fetchval("SELECT count(*) FROM actions WHERE type='buy-tickets'")
    assert 1 == await db_conn.fetchval('SELECT count(*) FROM tickets')
    assert 10 == await db_conn.fetchval('SELECT price FROM tickets')


async def test_webhook_fired_late(factory: Factory, db_conn, settings):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', price=10, ticket_limit=2)

    res = await factory.create_reservation()
    ticket_id = await db_conn.fetchval('select id from tickets where reserve_action=$1', res.action_id)

    assert 1 == await db_conn.fetchval('select check_tickets_remaining($1, $2)', factory.event_id, settings.ticket_ttl)
    await db_conn.execute("update tickets set created_ts=now() - '3600 seconds'::interval where id=$1", ticket_id)
    assert 2 == await db_conn.fetchval('select check_tickets_remaining($1, $2)', factory.event_id, settings.ticket_ttl)

    await factory.fire_stripe_webhook(res.action_id, fire_delay=3590)

    assert await db_conn.fetchval("SELECT id FROM actions WHERE type='buy-tickets'")


async def test_webhook_bought_late(factory: Factory, db_conn, settings):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', price=10, ticket_limit=2)

    res = await factory.create_reservation()
    ticket_id = await db_conn.fetchval('select id from tickets where reserve_action=$1', res.action_id)

    await db_conn.execute("update tickets set created_ts=now() - '3600 seconds'::interval where id=$1", ticket_id)

    assert 2 == await db_conn.fetchval('select check_tickets_remaining($1, $2)', factory.event_id, settings.ticket_ttl)
    r = await factory.fire_stripe_webhook(res.action_id, expected_status=233)
    assert await r.text() == 'ticket bought too late'

    assert not await db_conn.fetchval("SELECT id FROM actions WHERE type='buy-tickets'")


async def test_webhook_ticket_not_found(factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', price=10, ticket_limit=2)

    r = await factory.fire_stripe_webhook(0, expected_status=231)
    assert await r.text() == 'ticket not found'

    assert not await db_conn.fetchval("SELECT id FROM actions WHERE type='buy-tickets'")


async def test_webhook_fired_late_exceeded_limit(factory: Factory, db_conn, settings):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', price=10, ticket_limit=2)

    res = await factory.create_reservation()
    ticket_id = await db_conn.fetchval('select id from tickets where reserve_action=$1', res.action_id)

    await db_conn.execute("update tickets set created_ts=now() - '3600 seconds'::interval where id=$1", ticket_id)
    await factory.create_reservation()
    await factory.create_reservation()
    assert 0 == await db_conn.fetchval('select check_tickets_remaining($1, $2)', factory.event_id, settings.ticket_ttl)

    r = await factory.fire_stripe_webhook(res.action_id, fire_delay=3590, expected_status=234)
    assert await r.text() == 'ticket limit exceeded'

    assert not await db_conn.fetchval("SELECT id FROM actions WHERE type='buy-tickets'")


async def test_existing_customer(cli, url, login, dummy_server, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(stripe_customer_id='xxx')
    await factory.create_event(status='published', price=10)

    await login()
    data = {
        'tickets': [{'t': True, 'email': 'frank@example.org'}],
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
        'tickets': [{'t': True, 'email': 'frank@example.org'}],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()

    assert dummy_server.app['log'] == [
        'GET stripe_root_url/customers/missing',
        'POST stripe_root_url/customers',
        'POST stripe_root_url/payment_intents',
    ]


async def test_buy_webhook_repeat(factory: Factory, cli, url, login, db_conn):
    await factory.create_company()
    await factory.create_cat(cover_costs_message='Help!', cover_costs_percentage=5)
    await factory.create_user()
    await factory.create_event(status='published', price=100)

    await factory.create_user(email='ticket.buyer@example.org')
    await login(email='ticket.buyer@example.org')

    data = {
        'tickets': [{'t': True, 'email': 'ticket.buyer@example.org', 'cover_costs': True}],
        'ticket_type': factory.ticket_type_id,
    }
    r = await cli.json_post(url('event-reserve-tickets', id=factory.event_id), data=data)
    assert r.status == 200, await r.text()
    action_id = (await r.json())['action_id']

    await factory.fire_stripe_webhook(action_id)
    assert 1 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='buy-tickets'")
    assert 'booked' == await db_conn.fetchval('select status from tickets')

    r = await factory.fire_stripe_webhook(action_id, expected_status=232)
    assert await r.text() == 'ticket not reserved'

    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='book-free-tickets'")
    assert 0 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='buy-tickets-offline'")
    assert 1 == await db_conn.fetchval("SELECT COUNT(*) FROM actions WHERE type='buy-tickets'")
    assert 'booked' == await db_conn.fetchval('select status from tickets')


async def test_donate_after_webhook_repeat(factory: Factory, dummy_server, db_conn, cli, url, login):
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

    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')
    await factory.fire_stripe_webhook(action_id, amount=20_00, purpose='donate')

    r = await factory.fire_stripe_webhook(action_id, amount=20_00, purpose='donate', expected_status=240)
    assert await r.text() == 'donation already performed'

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')

    assert dummy_server.app['log'] == [
        'POST stripe_root_url/customers',
        'POST stripe_root_url/payment_intents',
        ('email_send_endpoint', 'Subject: "Thanks for your donation", To: "Frank Spencer <frank@example.org>"'),
    ]


async def test_donate_direct_webhook(factory: Factory, dummy_server, db_conn, cli, url, login):
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

    r = await factory.fire_stripe_webhook(action_id, amount=20_00, purpose='donate-direct', expected_status=240)
    assert await r.text() == 'donation already performed'

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM donations')

    assert dummy_server.app['log'] == [
        'POST stripe_root_url/customers',
        'POST stripe_root_url/payment_intents',
        ('email_send_endpoint', 'Subject: "Thanks for your donation", To: "Frank Spencer <frank@example.org>"'),
    ]


async def test_donate_webhook_missing_action(factory: Factory, fire_stripe_webhook):
    await factory.create_company()

    r = await fire_stripe_webhook(
        user_id=1,
        event_id=1,
        reserve_action_id=1,
        amount=123,
        purpose='donate-direct',
        webhook_type='payment_intent.succeeded',
        charge_id='charge-id',
        expected_status=240,
        fire_delay=0,
        metadata=None,
    )
    assert await r.text() == 'action not found'


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


async def test_get_payment_method_good(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(stripe_customer_id='cus_123')
    await factory.create_event(status='published', price=10)

    await login()

    r = await cli.get(url('payment-method-details', payment_method='good'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'card': {'brand': 'Visa', 'exp_month': 12, 'exp_year': 2032, 'last4': 1234},
        'address': {'line1': 'hello,'},
        'name': 'Testing Calls',
    }


async def test_get_payment_method_expired(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(stripe_customer_id='cus_123')
    await factory.create_event(status='published', price=10)

    await login()

    r = await cli.get(url('payment-method-details', payment_method='expired'))
    assert r.status == 404, await r.text()
    data = await r.json()
    assert data == {'message': 'payment method expired'}


async def test_get_payment_method_wrong_customer(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user(stripe_customer_id='other')
    await factory.create_event(status='published', price=10)

    await login()

    r = await cli.get(url('payment-method-details', payment_method='good'))
    assert r.status == 404, await r.text()
    data = await r.json()
    assert data == {'message': 'payment method not found for this customer'}


async def test_get_payment_method_404(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published', price=10)

    await login()

    r = await cli.get(url('payment-method-details', payment_method='missing'))
    assert r.status == 404, await r.text()
    data = await r.json()
    assert data == {'message': 'payment method not found'}


async def test_webhook_bad_signature1(cli, url, factory: Factory):
    await factory.create_company()
    r = await cli.post(url('stripe-webhook'), data='testing')
    assert r.status == 403, await r.text()
    assert await r.json() == {'message': 'Invalid signature'}


async def test_webhook_bad_signature2(cli, url, factory: Factory):
    await factory.create_company()
    r = await cli.post(url('stripe-webhook'), data='testing', headers={'Stripe-Signature': 'foobar'})
    assert r.status == 403, await r.text()
    assert await r.json() == {'message': 'Invalid signature'}


async def test_webhook_bad_signature3(cli, url, factory: Factory):
    await factory.create_company()
    r = await cli.post(url('stripe-webhook'), data='testing', headers={'Stripe-Signature': f't=x,v1=y,v5=a'})
    assert r.status == 403, await r.text()
    assert await r.json() == {'message': 'Invalid signature'}


async def test_webhook_bad_signature4(cli, url, factory: Factory, settings, db_conn):
    await factory.create_company()

    body = 'whatever'
    t = 123456
    stripe_webhook_secret = await db_conn.fetchval('select stripe_webhook_secret from companies')
    sig = hmac.new(stripe_webhook_secret.encode(), f'{t}.{body}'.encode(), hashlib.sha256).hexdigest()

    r = await cli.post(url('stripe-webhook'), data=body, headers={'Stripe-Signature': f't={t},v1={sig}'})
    assert r.status == 400, await r.text()
    assert await r.json() == {'message': 'webhook too old', 'age': AnyInt()}


async def test_webhook_not_configured(factory: Factory, db_conn):
    await factory.create_company()

    await db_conn.execute('update companies set stripe_webhook_secret=null')

    r = await factory.fire_stripe_webhook(1, expected_status=400)
    assert await r.json() == {'message': 'stripe webhooks not configured'}


async def test_webhook_bad_type(factory: Factory):
    await factory.create_company()

    r = await factory.fire_stripe_webhook(123, webhook_type='payment_intent.other', expected_status=230)
    assert await r.text() == 'unknown webhook type'


async def test_webhook_no_metadata(factory: Factory):
    await factory.create_company()

    r = await factory.fire_stripe_webhook(123, metadata={}, expected_status=240)
    assert await r.text() == 'no purpose in metadata'


async def test_webhook_invalid_metadata(factory: Factory):
    await factory.create_company()

    r = await factory.fire_stripe_webhook(123, metadata={'purpose': 'foobar'}, expected_status=250)
    assert (await r.text()).startswith('invalid metadata: 4 validation errors')
