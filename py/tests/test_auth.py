import json

from .conftest import Factory


async def test_login_successful(cli, url, factory: Factory):
    await factory.create_company()
    await factory.create_user()

    r = await cli.get(url('event-categories'))
    assert r.status == 401, await r.text()

    assert len(cli.session.cookie_jar) == 0

    data = dict(
        email='frank@example.com',
        password='testing',
    )
    r = await cli.post(url('login'), data=json.dumps(data))
    assert r.status == 200, await r.text()
    data = await r.json()
    r = await cli.post(url('auth-token'), data=json.dumps({'token': data['auth_token']}))
    assert r.status == 200, await r.text()

    assert len(cli.session.cookie_jar) == 1

    r = await cli.get(url('event-categories'))
    assert r.status == 200, await r.text()
