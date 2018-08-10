from aiohttp import FormData
from pytest_toolbox.comparison import RegexStr

from .conftest import Factory, create_image


async def test_cat_event_list(cli, url, db_conn, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published')

    slug = await db_conn.fetchval('SELECT slug FROM categories WHERE id=$1', factory.category_id)
    r = await cli.get(url('category', category=slug))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'events': [
            {
                'id': factory.event_id,
                'name': 'The Event Name',
                'cat_slug': 'supper-clubs',
                'slug': 'the-event-name',
                'image': 'https://www.example.org/co.png',
                'short_description': RegexStr('.*'),
                'location_name': None,
                'start_ts': '2020-01-28T19:00:00',
                'duration': None,
            },
        ],
    }


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
    r = await cli.json_post(url('category-add'), data=data)
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
        'sort_index': 42,
        'event_type': 'ticket_sales',
        'suggested_price': None,
        'image': None,
        'description': 'I love to party',
        'event_content': None,
        'host_advice': None,
        'booking_trust_message': None,
        'terms_and_conditions_message': None,
        'allow_marketing_message': None,
        'ticket_extra_title': None,
        'ticket_extra_help_text': None,

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
    r = await cli.json_post(url('category-edit', pk=factory.category_id), data=data)
    assert r.status == 200, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM categories')
    data = await r.json()
    assert data == {'status': 'ok'}

    cat = await db_conn.fetchrow('SELECT * FROM categories')
    assert cat['name'] == 'Supper Clubs'
    assert cat['sort_index'] == 42
    assert cat['description'] == 'x'


async def test_delete_cat(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await login()

    await factory.create_cat()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM categories')

    r = await cli.json_post(url('category-delete', pk=factory.category_id))
    assert r.status == 200, await r.text()
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM categories')


async def test_delete_cat_wrong(cli, url, db_conn, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await login()
    await factory.create_cat()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM categories')

    r = await cli.json_post(url('category-delete', pk=999))
    assert r.status == 404, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM categories')


async def test_edit_invalid(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await login()

    data = dict(sort_index='xxx')
    r = await cli.json_post(url('category-edit', pk=factory.category_id), data=data)
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

    r = await cli.json_post(url('category-edit', pk=factory.category_id), data='xxx')
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'Error decoding JSON'}


async def test_edit_not_dict(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await login()

    r = await cli.json_post(url('category-edit', pk=factory.category_id), data=[1, 2, 3])
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'data not a dictionary'}


async def test_cats_browse(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await login()

    r = await cli.get(url('category-browse'))
    assert r.status == 200, await r.text()
    data = await r.json()
    # debug(data)
    assert data == {
        'items': [
            {
                'id': factory.category_id,
                'name': 'Supper Clubs',
                'live': True,
                'description': None,
            },
        ],
        'count': 1,
    }


async def test_cats_retrieve(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await login()

    r = await cli.get(url('category-retrieve', pk=factory.category_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'id': factory.category_id,
        'name': 'Supper Clubs',
        'live': True,
        'description': None,
        'sort_index': None,
        'suggested_price': None,
        'event_content': None,
        'host_advice': None,
        'image': 'https://www.example.org/co.png',
        'booking_trust_message': None,
        'terms_and_conditions_message': None,
        'allow_marketing_message': None,
        'ticket_extra_title': None,
        'ticket_extra_help_text': None,

    }


async def test_upload_image(cli, url, factory: Factory, login, dummy_server):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await login()
    data = FormData()
    data.add_field('image', create_image(), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('categories-add-image', cat_id=factory.category_id),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        }
    )
    assert r.status == 200, await r.text()
    # debug(dummy_server.app['log'])
    assert sorted(dummy_server.app['log'][1:]) == [
        RegexStr(r'PUT aws_endpoint_url/testingbucket.example.org/tests/testing/supper-clubs/option/\w+/main.jpg'),
        RegexStr(r'PUT aws_endpoint_url/testingbucket.example.org/tests/testing/supper-clubs/option/\w+/thumb.jpg'),
    ]


async def test_upload_too_large(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await login()
    data = FormData()
    data.add_field('image', b'x' * (1024**2 + 1), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('categories-add-image', cat_id=factory.category_id),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        }
    )
    assert r.status == 413, await r.text()


async def test_upload_no_image(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await login()
    data = FormData()
    data.add_field('wrong', create_image(), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('categories-add-image', cat_id=factory.category_id),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        }
    )
    assert r.status == 400, await r.text()


async def test_upload_image_invalid(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await login()
    data = FormData()
    data.add_field('image', b'xxx', filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('categories-add-image', cat_id=factory.category_id),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        }
    )
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'invalid image',
    }


async def test_upload_image_too_small(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await login()
    data = FormData()
    data.add_field('image', create_image(200, 100), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('categories-add-image', cat_id=factory.category_id),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        }
    )
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {
        'message': 'image too small: 200x100<1920x500',
    }


async def test_list_images(cli, url, factory: Factory, login):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await login()
    r = await cli.get(url('categories-images', cat_id=factory.category_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'images': [
            'https://testingbucket.example.org/co-slug/cat-slug/option/randomkey1',
            'https://testingbucket.example.org/co-slug/cat-slug/option/randomkey2',
        ],
    }


async def test_delete_image(cli, url, factory: Factory, login, dummy_server):
    await factory.create_company()
    await factory.create_user()
    await factory.create_cat()
    await login()
    r = await cli.json_post(
        url('categories-delete-image', cat_id=factory.category_id),
        data={'image': 'https://example.org/tests/testing/supper-clubs/option/whatever'},
    )
    assert r.status == 200, await r.text()
    # debug(dummy_server.app['log'])
    assert sorted(dummy_server.app['log'][1:]) == [
        'DELETE aws_endpoint_url/testingbucket.example.org/tests/testing/supper-clubs/option/whatever/main.jpg',
        'DELETE aws_endpoint_url/testingbucket.example.org/tests/testing/supper-clubs/option/whatever/thumb.jpg',
    ]
