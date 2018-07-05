import json

from .conftest import Factory


async def test_create_cat(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await login()

    data = dict(
        name='foobar',
        description='I love to party',
        sort_index=42,
    )
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM categories')
    r = await cli.post(url('category-add'), data=json.dumps(data))
    assert r.status == 201, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM categories')
    data = await r.json()
    cat = dict(await db_conn.fetchrow('SELECT * FROM categories'))
    assert data == {
        'status': 'ok',
        'pk': cat.pop('id'),
    }
    assert cat == {
        'company': factory.company_id,
        'name': 'foobar',
        'slug': 'foobar',
        'live': True,
        'description': 'I love to party',
        'sort_index': 42,
        'event_content': None,
        'host_advice': None,
        'event_type': 'ticket_sales',
        'suggested_price': None,
        'image': None,
    }


async def test_edit_cat(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await login()

    await factory.create_cat()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM categories')
    cat = await db_conn.fetchrow('SELECT * FROM categories')
    assert cat['name'] == 'Supper Clubs'
    assert cat['sort_index'] is None
    assert cat['description'] is None

    data = dict(
        description='x',
        sort_index=42,
    )
    r = await cli.put(url('category-edit', pk=factory.category_id), data=json.dumps(data))
    assert r.status == 200, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM categories')
    data = await r.json()
    assert data == {'status': 'ok'}

    cat = await db_conn.fetchrow('SELECT * FROM categories')
    assert cat['name'] == 'Supper Clubs'
    assert cat['sort_index'] == 42
    assert cat['description'] == 'x'


async def test_edit_invalid(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await login()

    data = dict(sort_index='xxx')
    r = await cli.put(url('category-edit', pk=factory.category_id), data=json.dumps(data))
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'Invalid Data',
        'details': [
            {
                'loc': [
                    'sort_index',
                ],
                'msg': 'value is not a valid integer',
                'type': 'type_error.integer',
            },
        ],
    }


async def test_edit_bad_json(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await login()

    r = await cli.put(url('category-edit', pk=factory.category_id), data='xxx')
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'Error decoding JSON'}


async def test_edit_not_dict(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await login()

    r = await cli.put(url('category-edit', pk=factory.category_id), data=json.dumps([1, 2, 3]))
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'data not a dictionary'}
