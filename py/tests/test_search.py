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
    assert vector == "'doe':2A 'example.com':5 'john':1A 'test':4 'testing@example.com':3B"
    assert await db_conn.fetchval('select company from search where user_id=$1', user_id) == company_id

    await db_conn.execute('update users set last_name=$1 where id=$2', 'DiffErent', user_id)

    assert await db_conn.fetchval('select count(*) from search') == 1
    new_label, new_vector = await db_conn.fetchrow('select label, vector from search where user_id=$1', user_id)
    assert new_label == 'John DiffErent (testing@example.com)'
    assert new_vector == "'differ':2A 'example.com':5 'john':1A 'test':4 'testing@example.com':3B"
    assert await db_conn.fetchval('select company from search where user_id=$1', user_id) == company_id

    await db_conn.execute('delete from users where id=$1', user_id)
    assert await db_conn.fetchval('select count(*) from search') == 0

    await db_conn.execute("INSERT INTO users (company, role) VALUES ($1, 'guest')", company_id)
    assert await db_conn.fetchval('select count(*) from search') == 0

    await db_conn.execute("INSERT INTO users (company, role, email) VALUES ($1, 'guest', 'x@y')", company_id)
    assert await db_conn.fetchval('select count(*) from search') == 1
    assert await db_conn.fetchval('select vector from search') == "'x':1A,3B,5 'y':2A,4B,6"
    await db_conn.execute('delete from users')

    await db_conn.execute("INSERT INTO users (company, role, first_name) VALUES ($1, 'guest', 'xx')", company_id)
    assert await db_conn.fetchval('select count(*) from search') == 1
    assert await db_conn.fetchval('select vector from search') == "'xx':1A"
    assert await db_conn.fetchval('select company from search') == company_id


async def test_create_update_event(factory: Factory, db_conn):
    assert await db_conn.fetchval('select count(*) from search') == 0
    company_id = await factory.create_company()
    await factory.create_company(name='Other Company', domain='example.org')
    await factory.create_cat()
    await factory.create_user()
    assert await db_conn.fetchval('select count(*) from search') == 1
    event_id = await factory.create_event(
        name='Foo Event',
        short_description='Foo Event Appleton',
        long_description='sausage',
    )
    assert await db_conn.fetchval('select count(*) from search') == 2
    user, label, vector = await db_conn.fetchrow('select user_id, label, vector from search where event=$1', event_id)
    assert user is None
    assert label == 'Foo Event'
    assert vector == "'appleton':5B 'event':2A,4B 'foo':1A,3B 'sausag':6"
    assert await db_conn.fetchval('select company from search where event=$1', event_id) == company_id

    await db_conn.execute('delete from events')
    assert await db_conn.fetchval('select count(*) from search') == 1


async def test_search_for_users(factory: Factory, db_conn, cli, url, login):
    assert await db_conn.fetchval('select count(*) from search') == 0
    await factory.create_company()
    user_id = await factory.create_user(first_name='John', last_name='Doe', email='testing@example.com')

    await login(email='testing@example.com')

    for query in ('john', 'doe', 'john doe', 'testing@example.com', 'testing', '@example.com', 'example.com'):
        r = await cli.get(url('search', query={'q': query}))
        assert r.status == 200, await r.text()
        assert await r.json() == [{'id': user_id, 'label': 'John Doe (testing@example.com)', 'type': 'user'}], query

    r = await cli.get(url('search', query={'q': 'missing'}))
    assert r.status == 200, await r.text()
    assert await r.json() == []


async def test_search_for_users_order(factory: Factory, db_conn, cli, url, login):
    assert await db_conn.fetchval('select count(*) from search') == 0
    await factory.create_company()
    user_id = await factory.create_user(first_name='John', last_name='Doe', email='foobar@example.com')
    user2_id = await factory.create_user(first_name='foobar', last_name='xxx', email=None)

    await login(email='foobar@example.com')

    r = await cli.get(url('search', query={'q': 'foobar'}))
    assert r.status == 200, await r.text()
    assert await r.json() == [
        {'id': user2_id, 'label': 'foobar xxx', 'type': 'user'},
        {'id': user_id, 'label': 'John Doe (foobar@example.com)', 'type': 'user'},
    ]


async def test_search_for_users_company(factory: Factory, db_conn, cli, url, login):
    assert await db_conn.fetchval('select count(*) from search') == 0
    await factory.create_company()
    user_id = await factory.create_user(first_name='John', last_name='Doe')

    company2_id = await factory.create_company(name='2', domain='2')
    await factory.create_user(first_name='John', last_name='Doe', company_id=company2_id)

    await login()

    r = await cli.get(url('search', query={'q': 'John'}))
    assert r.status == 200, await r.text()
    assert await r.json() == [{'id': user_id, 'label': 'John Doe (frank@example.org)', 'type': 'user'}]


async def test_search_for_event(factory: Factory, db_conn, cli, url, login):
    assert await db_conn.fetchval('select count(*) from search') == 0
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    assert await db_conn.fetchval('select count(*) from search') == 1
    event_id = await factory.create_event(name='Foobar', short_description='Foo Event Appleton')

    await login()

    r = await cli.get(url('search', query={'q': 'Foobar'}))
    assert r.status == 200, await r.text()
    assert await r.json() == [{'id': event_id, 'label': 'Foobar', 'type': 'event'}]

    r = await cli.get(url('search', query={'q': 'apple'}))
    assert r.status == 200, await r.text()
    assert await r.json() == [{'id': event_id, 'label': 'Foobar', 'type': 'event'}]
