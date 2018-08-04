from aiohttp import FormData
from pytest_toolbox.comparison import RegexStr

from .conftest import Factory, create_image


async def test_company_details(cli, url, login, factory: Factory):
    await factory.create_company()
    await factory.create_user()
    await login()

    r = await cli.get(url('company-retrieve', pk=0))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'id': factory.company_id,
        'name': 'Testing',
        'slug': 'testing',
        'domain': '127.0.0.1',
        'stripe_public_key': 'stripe_key_xxx',
        'stripe_secret_key': 'stripe_secret_xxx',
        'currency': 'gbp',
        'email_from': None,
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
    data.add_field('image', create_image(300, 300), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('company-upload', field='logo'),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        }
    )
    assert r.status == 200, await r.text()
    assert sorted(dummy_server.app['log'][1:]) == [
        RegexStr(r'PUT aws_endpoint_url/testingbucket.example.org/tests/testing/co/logo/\w+/main.jpg'),
    ]
    assert None is not await db_conn.fetchval('SELECT logo FROM companies')
