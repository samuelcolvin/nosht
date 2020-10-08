import json
from datetime import datetime, timezone

import pytest
from pytest_toolbox.comparison import AnyInt, CloseToNow

from shared.emails import Triggers

from .conftest import Factory


async def create_email(factory, db_conn):
    return await db_conn.fetchval(
        """
        insert into emails (company, user_id, ext_id, trigger, subject, address)
        values ($1, $2, $3, $4, 'Testing', 'testing@example.org')
        returning id
        """,
        factory.company_id,
        factory.user_id,
        '123456789',
        Triggers.ticket_buyer,
    )


async def test_send_webhook(factory: Factory, db_conn, cli):
    await factory.create_company()
    await factory.create_user(email='testing@example.org')

    email_id = await create_email(factory, db_conn)
    data = {
        'Type': 'Notification',
        'Message': json.dumps(
            {'eventType': 'Send', 'mail': {'messageId': '123456789', 'timestamp': '2032-10-16T12:00:00.000Z'}}
        ),
    }

    r = await cli.post('/api/ses-webhook/', json=data, headers={'Authorization': 'Basic cHc6dGVzdHM='})
    assert r.status == 204, await r.text()
    assert 1 == await db_conn.fetchval('select count(*) from emails')

    dt = datetime(2032, 10, 16, 12, 0, tzinfo=timezone.utc)
    assert ('Send', dt) == await db_conn.fetchrow('select status, update_ts from emails')
    assert 1 == await db_conn.fetchval('select count(*) from email_events')
    evt = await db_conn.fetchrow('select * from email_events')
    assert dict(evt) == {
        'id': AnyInt(),
        'email': email_id,
        'ts': dt,
        'status': 'Send',
        'extra': None,
    }


async def test_delivery(factory: Factory, db_conn, cli):
    await factory.create_company()
    await factory.create_user(email='testing@example.org')

    email_id = await create_email(factory, db_conn)
    data = {
        'Type': 'Notification',
        'Message': json.dumps(
            {'eventType': 'Delivery', 'mail': {'messageId': '123456789'}, 'delivery': {'processingTimeMillis': 789}}
        ),
    }

    r = await cli.post('/api/ses-webhook/', json=data, headers={'Authorization': 'Basic cHc6dGVzdHM='})
    assert r.status == 204, await r.text()
    assert 'Delivery' == await db_conn.fetchval('select status from emails')
    evt = await db_conn.fetchrow('select * from email_events')
    assert dict(evt) == {
        'id': AnyInt(),
        'email': email_id,
        'ts': CloseToNow(delta=3),
        'status': 'Delivery',
        'extra': '{"delivery_time": 789}',
    }


@pytest.mark.parametrize('status', ['Send', 'Delivery', 'Open', 'Click', 'Bounce', 'Complaint', 'Unknown-status'])
async def test_all(status, factory: Factory, db_conn, cli):
    await factory.create_company()
    await factory.create_user(email='testing@example.org')

    await create_email(factory, db_conn)
    data = {
        'Type': 'Notification',
        'Message': json.dumps(
            {
                'eventType': status,
                'mail': {'messageId': '123456789'},
                status.lower(): {
                    'timestamp': '2032-10-16T12:00:00.000Z',
                    # wrong for actual events, but good enough
                    'ipAddress': '195.224.18.3',
                    'userAgent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)',
                },
            }
        ),
    }

    r = await cli.post('/api/ses-webhook/', json=data, headers={'Authorization': 'Basic cHc6dGVzdHM='})
    assert r.status == 204, await r.text()
    assert 1 == await db_conn.fetchval('select count(*) from emails')
    assert status == await db_conn.fetchval('select status from emails')
    assert 1 == await db_conn.fetchval('select count(*) from email_events')
    assert status == await db_conn.fetchval('select status from email_events')


async def test_email_not_found(factory: Factory, db_conn, cli):
    await factory.create_company()
    await factory.create_user(email='testing@example.org')

    await create_email(factory, db_conn)
    data = {
        'Type': 'Notification',
        'Message': json.dumps(
            {'eventType': 'Send', 'mail': {'messageId': 'xxx', 'timestamp': '2032-10-16T12:00:00.000Z'}}
        ),
    }

    r = await cli.post('/api/ses-webhook/', json=data, headers={'Authorization': 'Basic cHc6dGVzdHM='})
    assert r.status == 204, await r.text()
    assert 1 == await db_conn.fetchval('select count(*) from emails')
    assert 'pending' == await db_conn.fetchval('select status from emails')
    assert 0 == await db_conn.fetchval('select count(*) from email_events')


async def test_unsubscribe(factory: Factory, db_conn, cli):
    await factory.create_company()
    await factory.create_user(email='testing@example.org')

    assert await db_conn.fetchval('select receive_emails from users where id=$1', factory.user_id)

    email_id = await create_email(factory, db_conn)
    data = {
        'Type': 'Notification',
        'Message': json.dumps(
            {
                'eventType': 'Complaint',
                'mail': {'messageId': '123456789'},
                'complaint': {'timestamp': '2032-10-16T12:00:00.000Z'},
            }
        ),
    }

    r = await cli.post('/api/ses-webhook/', json=data, headers={'Authorization': 'Basic cHc6dGVzdHM='})
    assert r.status == 204, await r.text()
    assert 'Complaint' == await db_conn.fetchval('select status from emails')
    assert 1 == await db_conn.fetchval('select count(*) from email_events')
    evt = await db_conn.fetchrow('select * from email_events')
    assert dict(evt) == {
        'id': AnyInt(),
        'email': email_id,
        'ts': datetime(2032, 10, 16, 12, 0, tzinfo=timezone.utc),
        'status': 'Complaint',
        'extra': '{"unsubscribe": true}',
    }

    assert not await db_conn.fetchval('select receive_emails from users where id=$1', factory.user_id)


async def test_old_event(factory: Factory, db_conn, cli):
    await factory.create_company()
    await factory.create_user(email='testing@example.org')

    await create_email(factory, db_conn)
    data = {
        'Type': 'Notification',
        'Message': json.dumps(
            {'eventType': 'Send', 'mail': {'messageId': '123456789', 'timestamp': '2000-10-16T12:00:00.000Z'}}
        ),
    }

    r = await cli.post('/api/ses-webhook/', json=data, headers={'Authorization': 'Basic cHc6dGVzdHM='})
    assert r.status == 204, await r.text()

    assert ('pending', CloseToNow(delta=3)) == await db_conn.fetchrow('select status, update_ts from emails')
    assert datetime(2000, 10, 16, 12, 0, tzinfo=timezone.utc) == await db_conn.fetchval('select ts from email_events')


async def test_bad_auth(factory: Factory, cli):
    await factory.create_company()
    await factory.create_user(email='testing@example.org')

    data = {
        'Type': 'Notification',
        'Message': json.dumps(
            {'eventType': 'Send', 'mail': {'messageId': '123456789', 'timestamp': '2000-10-16T12:00:00.000Z'}}
        ),
    }

    r = await cli.post('/api/ses-webhook/', json=data, headers={'Authorization': 'Basic wrong'})
    assert r.status == 401, await r.text()


async def test_subscribe(factory: Factory, db_conn, cli, dummy_server):
    await factory.create_company()
    await factory.create_user(email='testing@example.org')

    await create_email(factory, db_conn)
    data = {'Type': 'SubscriptionConfirmation', 'SubscribeURL': dummy_server.app['server_name'] + '/200/'}

    r = await cli.post('/api/ses-webhook/', json=data, headers={'Authorization': 'Basic cHc6dGVzdHM='})
    assert r.status == 204, await r.text()
    assert 1 == await db_conn.fetchval('select count(*) from emails')
    assert 0 == await db_conn.fetchval('select count(*) from email_events')

    assert dummy_server.app['log'] == [
        'HEAD 200',
    ]
