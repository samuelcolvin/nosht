import json

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
        'stripe_webhook_secret': 'stripe_webhook_secret_xxx',
        'currency': 'gbp',
        'email_from': None,
        'email_reply_to': None,
        'email_template': None,
        'image': 'https://www.example.org/main.png',
        'logo': None,
        'footer_links': None,
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
    assert 'https://www.example.org/main.png' == await db_conn.fetchval('SELECT image FROM companies')
    data = FormData()
    data.add_field('image', create_image(), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('company-upload', field='image'),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        },
    )
    assert r.status == 200, await r.text()
    # debug(dummy_server.app['log'])
    assert sorted(dummy_server.app['log']) == [
        'DELETE aws_endpoint_url/testingbucket.example.org/main.png',
        'DELETE aws_endpoint_url/testingbucket.example.org/thumb.png',
        RegexStr(r'PUT aws_endpoint_url/testingbucket.example.org/tests/testing/co/image/\w+/main.png'),
        RegexStr(r'PUT aws_endpoint_url/testingbucket.example.org/tests/testing/co/image/\w+/thumb.png'),
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
        },
    )
    assert r.status == 200, await r.text()
    assert dummy_server.app['images'] == [
        (RegexStr(r'/aws_endpoint_url/testingbucket.example.org/tests/testing/co/logo/\w+/main.png'), 341, 256),
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
        },
    )
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'image too small: 100x300 < 256x256'}
    assert dummy_server.app['images'] == []
    assert None is await db_conn.fetchval('SELECT logo FROM companies')


async def test_upload_logo_convert(cli, url, factory: Factory, db_conn, login):
    await factory.create_company()
    await factory.create_user()
    await login()
    assert None is await db_conn.fetchval('SELECT logo FROM companies')
    data = FormData()
    data.add_field('image', create_image(mode='CMYK'), filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        url('company-upload', field='logo'),
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        },
    )
    assert r.status == 200, await r.text()
    assert None is not await db_conn.fetchval('SELECT logo FROM companies')


async def test_set_footer_links(cli, url, factory: Factory, db_conn, login):
    await factory.create_company()
    await factory.create_user()
    await login()
    assert None is await db_conn.fetchval('SELECT footer_links FROM companies')
    data = {
        'links': [
            {'title': 'Foo', 'url': 'https://www.example.com/testing/', 'new_tab': False},
            {'title': 'Bar', 'url': 'http://www.example.com/another/'},
        ]
    }
    r = await cli.json_post(url('company-footer-links'), data=data)
    assert r.status == 200, await r.text()
    links = json.loads(await db_conn.fetchval('SELECT footer_links FROM companies'))
    assert links == [
        {'url': 'https://www.example.com/testing/', 'title': 'Foo', 'new_tab': False},
        {'url': 'http://www.example.com/another/', 'title': 'Bar', 'new_tab': True},
    ]
