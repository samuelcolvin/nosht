from aiohttp import FormData
from pytest_toolbox.comparison import RegexStr

from .conftest import Factory, create_image


async def test_company_details(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_user()
    await login()

    r = await cli.get(url('company-retrieve', pk=factory.company_id))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'name': 'Testing',
        'slug': 'testing',
        'domain': '127.0.0.1',
        'stripe_public_key': 'stripe_key_xxx',
        'stripe_secret_key': 'stripe_secret_xxx',
        'currency': 'gbp',
        'email_from': None,
        'email_reply_to': None,
        'email_template': None,
        'image': 'https://www.example.org/co.png',
        'logo': None,
    }


async def test_company_list(cli, login, factory: Factory):
    await factory.create_company()
    await factory.create_user()
    await login()

    r = await cli.get('/api/companies/')
    assert r.status == 404, await r.text()


async def test_company_edit(cli, url, login, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_user()
    await login()

    r = await cli.json_post(url('company-edit', pk=factory.company_id), data={'name': 'New Name'})
    assert r.status == 200, await r.text()
    assert 'New Name' == await db_conn.fetchval('SELECT name FROM companies')


async def test_upload_image(cli, url, factory: Factory, login, db_conn, dummy_server):
    await factory.create_company()
    await factory.create_user()
    await login()
    assert 'https://www.example.org/co.png' == await db_conn.fetchval('SELECT image FROM companies')
    data = FormData()
    data.add_field('image', create_image(), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('company-upload', field='image'),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        }
    )
    assert r.status == 200, await r.text()
    # debug(dummy_server.app['log'])
    assert sorted(dummy_server.app['log'][1:]) == [
        'DELETE aws_endpoint_url/testingbucket.example.org/co.png/main.jpg',
        'DELETE aws_endpoint_url/testingbucket.example.org/co.png/thumb.jpg',
        RegexStr(r'PUT aws_endpoint_url/testingbucket.example.org/tests/testing/co/image/\w+/main.jpg'),
        RegexStr(r'PUT aws_endpoint_url/testingbucket.example.org/tests/testing/co/image/\w+/thumb.jpg'),
    ]
    logo = await db_conn.fetchval('SELECT image FROM companies')
    assert logo.startswith('https://testingbucket.example.org/tests/testing/co/image/')


async def test_upload_logo(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_user()
    await login()
    assert None is await db_conn.fetchval('SELECT logo FROM companies')
    data = FormData()
    data.add_field('image', create_image(400, 300), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('company-upload', field='logo'),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        }
    )
    assert r.status == 200, await r.text()
    assert dummy_server.app['images'] == [
        (
            RegexStr(r'/aws_endpoint_url/testingbucket.example.org/tests/testing/co/logo/\w+/main.jpg'),
            341,
            256,
        ),

    ]
    assert None is not await db_conn.fetchval('SELECT logo FROM companies')


async def test_upload_logo_too_small(cli, url, factory: Factory, db_conn, login, dummy_server):
    await factory.create_company()
    await factory.create_user()
    await login()
    assert None is await db_conn.fetchval('SELECT logo FROM companies')
    data = FormData()
    data.add_field('image', create_image(100, 300), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('company-upload', field='logo'),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        }
    )
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'image too small: 100x300 < 256x256'}
    assert dummy_server.app['images'] == []
    assert None is await db_conn.fetchval('SELECT logo FROM companies')
