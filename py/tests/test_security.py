from .conftest import Factory


async def test_preflight_ok(cli, url, factory: Factory):
    await factory.create_company()

    headers = {
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type',
    }
    r = await cli.options(url('login'), headers=headers)
    assert r.status == 200, await r.text()
    assert r.headers['Access-Control-Allow-Headers'] == 'Content-Type'
    assert r.headers['Access-Control-Allow-Origin'] == 'null'
    t = await r.text()
    assert t == 'ok'


async def test_preflight_failed(cli, url, factory: Factory):
    await factory.create_company()

    headers = {
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'xxx',
    }
    r = await cli.options(url('login'), headers=headers)
    assert r.status == 403, await r.text()
    assert 'Access-Control-Allow-Headers' not in r.headers
    assert r.headers['Access-Control-Allow-Origin'] == 'null'
    obj = await r.json()
    assert obj == {
        'error': 'Access-Control checks failed',
    }


async def test_post_csrf(cli, url, factory: Factory):
    await factory.create_company()

    r = await cli.post(url('login'))
    assert r.status == 403, await r.text()
    obj = await r.json()
    assert obj == {
        'error': 'CSRF failure',
    }
