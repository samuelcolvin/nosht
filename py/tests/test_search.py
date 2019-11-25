from .conftest import Factory


async def test_create_update_user(factory: Factory, db_conn):
    assert await db_conn.fetchval('select count(*) from search') == 0
    company_id = await factory.create_company()
    user_id = await factory.create_user(first_name='John', last_name='Doe', email='testing@example.com')
    assert await db_conn.fetchval('select count(*) from search') == 1
    event, label, vector = await db_conn.fetchrow('select event, label, vector from search where user_id=$1', user_id)
    assert event is None
    assert label == 'John Doe'
    assert vector == "'doe':2A 'example.com':5 'john':1A 'test':4 'testing@example.com':3B"

    await db_conn.execute('update users set last_name=$1 where id=$2', 'DiffErent', user_id)

    assert await db_conn.fetchval('select count(*) from search') == 1
    new_label, new_vector = await db_conn.fetchrow('select label, vector from search where user_id=$1', user_id)
    assert new_label == 'John DiffErent'
    assert new_vector == "'differ':2A 'example.com':5 'john':1A 'test':4 'testing@example.com':3B"

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


async def test_create_update_event(factory: Factory, db_conn):
    assert await db_conn.fetchval('select count(*) from search') == 0
    await factory.create_company()
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

    await db_conn.execute('delete from events')
    assert await db_conn.fetchval('select count(*) from search') == 1

