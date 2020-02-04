from datetime import datetime, timezone

from pytest_toolbox.comparison import CloseToNow

from .conftest import Factory


async def test_create_update_user(factory: Factory, db_conn):
    assert await db_conn.fetchval('select count(*) from search') == 0
    company_id = await factory.create_company()
    await factory.create_company(name='Other Company', domain='example.org')
    user_id = await factory.create_user(first_name='John', last_name='Doe', email='testing@example.com')
    assert await db_conn.fetchval('select count(*) from search') == 1
    event, label, vector = await db_conn.fetchrow('select event, label, vector from search where user_id=$1', user_id)
    assert event is None
    assert label == 'John Doe (testing@example.com)'
    assert vector == "'activ':4C 'admin':5C 'doe':2A 'example.com':7 'john':1A 'test':6 'testing@example.com':3B"
    assert await db_conn.fetchval('select company from search where user_id=$1', user_id) == company_id

    await db_conn.execute('update users set last_name=$1 where id=$2', 'DiffErent', user_id)

    assert await db_conn.fetchval('select count(*) from search') == 1
    r = await db_conn.fetchrow('select label, vector, company, active_ts from search where user_id=$1', user_id)
    assert r['label'] == 'John DiffErent (testing@example.com)'
    assert r['vector'] == (
        "'activ':4C 'admin':5C 'differ':2A 'example.com':7 'john':1A 'test':6 'testing@example.com':3B"
    )
    assert r['company'] == company_id
    assert r['active_ts'] == CloseToNow()

    await db_conn.execute('delete from users where id=$1', user_id)
    assert await db_conn.fetchval('select count(*) from search') == 0

    await db_conn.execute("INSERT INTO users (company, role) VALUES ($1, 'guest')", company_id)
    assert await db_conn.fetchval('select count(*) from search') == 0

    await db_conn.execute("INSERT INTO users (company, role, email) VALUES ($1, 'guest', 'x@y')", company_id)
    assert await db_conn.fetchval('select count(*) from search') == 1
    assert await db_conn.fetchval('select vector from search') == "'guest':6C 'pend':5C 'x':1A,3B,7 'y':2A,4B,8"
    await db_conn.execute('delete from users')

    await db_conn.execute("INSERT INTO users (company, role, first_name) VALUES ($1, 'guest', 'xx')", company_id)
    assert await db_conn.fetchval('select count(*) from search') == 1
    assert await db_conn.fetchval('select vector from search') == "'guest':3C 'pend':2C 'xx':1A"
    assert await db_conn.fetchval('select company from search') == company_id


async def test_active_ts_updated(factory: Factory, db_conn):
    assert await db_conn.fetchval('select count(*) from search') == 0
    company_id = await factory.create_company()
    user_id = await factory.create_user(first_name='John', last_name='Doe', email='testing@example.com')
    assert await db_conn.fetchval('select count(*) from search') == 1
    assert await db_conn.fetchval('select active_ts from search where user_id=$1', user_id) == CloseToNow()
    await db_conn.execute(
        "insert into actions (company, user_id, ts, type) values ($1, $2, '2032-01-01', 'login')", company_id, user_id,
    )
    new_ts = await db_conn.fetchval('select active_ts from search where user_id=$1', user_id)
    assert new_ts == datetime(2032, 1, 1, tzinfo=timezone.utc)


async def test_create_update_event(factory: Factory, db_conn):
    assert await db_conn.fetchval('select count(*) from search') == 0
    company_id = await factory.create_company()
    await factory.create_company(name='Other Company', domain='example.org')
    await factory.create_cat()
    await factory.create_user()
    assert await db_conn.fetchval('select count(*) from search') == 1
    event_id = await factory.create_event(
        name='Foo Event', short_description='Foo Event Appleton', long_description='sausage',
    )
    assert await db_conn.fetchval('select count(*) from search') == 2
    user, label, vector = await db_conn.fetchrow('select user_id, label, vector from search where event=$1', event_id)
    assert user is None
    assert label == 'Foo Event'
    assert vector == "'appleton':5B 'club':8C 'event':2A,4B 'foo':1A,3B 'pend':6C 'sausag':9 'supper':7C"
    assert await db_conn.fetchval('select company from search where event=$1', event_id) == company_id

    await db_conn.execute('delete from events')
    assert await db_conn.fetchval('select count(*) from search') == 1


async def test_search_for_users(factory: Factory, db_conn, cli, url, login):
    assert await db_conn.fetchval('select count(*) from search') == 0
    await factory.create_company()
    user_id = await factory.create_user(first_name='John', last_name='Doe', email='testing@example.com')

    r = await cli.get(url('event-search', query={'q': 'Foobar'}))
    assert r.status == 401, await r.text()

    await login(email='testing@example.com')

    r = await cli.get(url('user-search', query={'q': 'john'}))
    assert r.status == 200, await r.text()
    assert await r.json() == {
        'items': [
            {
                'id': user_id,
                'name': 'John Doe',
                'role_type': 'admin',
                'status': 'active',
                'email': 'testing@example.com',
                'active_ts': CloseToNow(),
            },
        ],
    }

    for query in (
        'john',
        'doe',
        'john doe',
        'testing@example.com',
        'testing',
        '@example.com',
        'testing@example.com doe',
    ):
        r = await cli.get(url('user-search', query={'q': query}))
        assert r.status == 200, await r.text()
        items = (await r.json())['items']
        assert len(items) == 1, query
        assert items[0]['id'] == user_id, query
        assert items[0]['name'] == 'John Doe', query

    for query in ({'q': 'missing'}, {'q': ''}, None):
        r = await cli.get(url('user-search', query=query))
        assert r.status == 200, await r.text()
        assert await r.json() == {'items': []}, query


async def test_search_for_users_order(factory: Factory, db_conn, cli, url, login):
    assert await db_conn.fetchval('select count(*) from search') == 0
    await factory.create_company()
    user_id = await factory.create_user(first_name='John', last_name='Doe', email='foobar@example.com')
    user2_id = await factory.create_user(first_name='foobar', last_name='xxx', email=None)

    await login(email='foobar@example.com')

    await db_conn.execute("update search set active_ts='2015-01-01' where user_id=$1", user_id)
    r = await cli.get(url('user-search', query={'q': 'foobar'}))
    assert r.status == 200, await r.text()
    assert [v['id'] for v in (await r.json())['items']] == [user2_id, user_id]
    await db_conn.execute("update search set active_ts='2032-01-01' where user_id=$1", user_id)
    r = await cli.get(url('user-search', query={'q': 'foobar'}))
    assert r.status == 200, await r.text()
    assert [v['id'] for v in (await r.json())['items']] == [user_id, user2_id]


async def test_search_for_users_company(factory: Factory, db_conn, cli, url, login):
    assert await db_conn.fetchval('select count(*) from search') == 0
    await factory.create_company()
    user_id = await factory.create_user(first_name='John', last_name='Doe')

    company2_id = await factory.create_company(name='2', domain='2')
    await factory.create_user(first_name='John', last_name='Doe', company_id=company2_id)

    await login()

    r = await cli.get(url('user-search', query={'q': 'John'}))
    assert r.status == 200, await r.text()
    assert await r.json() == {
        'items': [
            {
                'id': user_id,
                'name': 'John Doe',
                'role_type': 'admin',
                'status': 'active',
                'email': 'frank@example.org',
                'active_ts': CloseToNow(),
            },
        ],
    }


async def test_search_for_event(factory: Factory, db_conn, cli, url, login):
    assert await db_conn.fetchval('select count(*) from search') == 0
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    assert await db_conn.fetchval('select count(*) from search') == 1
    event_id = await factory.create_event(name='Foobar', short_description='Foo Event Appleton')

    r = await cli.get(url('event-search', query={'q': 'Foobar'}))
    assert r.status == 401, await r.text()

    await login()

    r = await cli.get(url('event-search'))
    assert r.status == 200, await r.text()
    assert await r.json() == {'items': []}

    r = await cli.get(url('event-search', query={'q': 'Foobar'}))
    assert r.status == 200, await r.text()
    assert await r.json() == {
        'items': [
            {
                'id': event_id,
                'name': 'Foobar',
                'category': 'Supper Clubs',
                'status': 'pending',
                'highlight': False,
                'start_ts': '2032-06-28T18:00:00+00:00',
                'duration': 3600,
            },
        ],
    }

    r = await cli.get(url('event-search', query={'q': 'apple'}))
    assert r.status == 200, await r.text()
    assert len((await r.json())['items']) == 1
