import pytest
from aiohttp.test_utils import make_mocked_request
from aiohttp.web_exceptions import HTTPNotFound

from web.views.static import static_handler


async def test_index(cli, setup_static):
    r = await cli.get('/')
    assert r.status == 200, await r.text()
    text = await r.text()
    assert text == 'this is index.html'
    assert r.headers['Content-Type'] == 'text/html'


async def test_file(cli, setup_static):
    r = await cli.get('/test.js')
    assert r.status == 200, await r.text()
    assert r.headers['Content-Type'] == 'application/javascript'
    text = await r.text()
    assert text == 'this is test.js'


async def test_wrong(cli, setup_static):
    request = make_mocked_request('GET', '/D:\path', match_info={'path': '../path'}, app=cli.app)
    with pytest.raises(HTTPNotFound):
        await static_handler(request)


async def test_other(cli, setup_static):
    r = await cli.get('/foobar/')
    assert r.status == 200, await r.text()
    text = await r.text()
    assert text == 'this is index.html'
    assert r.headers['Content-Type'] == 'text/html'


async def test_iframe(cli, setup_static):
    r = await cli.get('/iframes/login.html')
    assert r.status == 200, await r.text()
    text = await r.text()
    assert text == 'this is iframes/login.html'
    assert r.headers['Content-Type'].startswith('text/html')


async def test_iframe_missing(cli, setup_static):
    r = await cli.get('/iframes/xxx.html')
    assert r.status == 200, await r.text()
    text = await r.text()
    assert text == 'this is index.html'
    assert r.headers['Content-Type'] == 'text/html'
