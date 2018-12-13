import os

import pytest
from aiohttp.test_utils import make_mocked_request
from aiohttp.web_exceptions import HTTPNotFound
from pytest_toolbox.comparison import RegexStr

from web.views.static import get_csp_headers, static_handler


async def test_index(cli, setup_static):
    r = await cli.get('/')
    assert r.status == 200, await r.text()
    text = await r.text()
    assert text == 'this is index.html'
    assert r.headers['Content-Type'] == 'text/html'
    assert r.headers.get('X-Robots-Tag') is None


async def test_file(cli, setup_static):
    r = await cli.get('/test.js')
    assert r.status == 200, await r.text()
    assert r.headers['Content-Type'] == 'application/javascript'
    text = await r.text()
    assert text == 'this is test.js'
    assert r.headers.get('X-Robots-Tag') is None


async def test_wrong(cli, setup_static):
    request = make_mocked_request('GET', '/D:\\path', match_info={'path': '../path'}, app=cli.app)
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


async def test_private(cli, setup_static):
    r = await cli.get('/pvt/foo/bar/')
    assert r.status == 200, await r.text()
    assert r.headers['Content-Type'] == 'text/html'
    assert r.headers.get('X-Robots-Tag') == 'noindex'
    text = await r.text()
    assert text == 'this is index.html'


async def test_sitemap(cli, setup_static):
    r = await cli.get('/sitemap.xml', allow_redirects=False)
    assert r.status == 301, await r.text()
    assert r.headers['location'] == RegexStr(r'https://127.0.0.1:\d+/api/sitemap.xml')


async def test_csp(cli, setup_static):
    r = await cli.get('/')
    assert r.status == 200, await r.text()
    assert 'Content-Security-Policy' in r.headers
    assert r.headers['Content-Security-Policy'].startswith("default-src 'self';")
    assert 'https://nosht.scolvin.com' in r.headers['Content-Security-Policy']
    assert 'report-uri' not in r.headers['Content-Security-Policy']


async def test_csp_iframe(cli, setup_static):
    r = await cli.get('/iframes/login.html')
    assert r.status == 200, await r.text()
    assert 'Content-Security-Policy' not in r.headers


async def test_csp_with_raven(settings):
    os.environ['RAVEN_DSN'] = 'https://123@sentry.io/456'
    h = get_csp_headers(settings)
    assert h['Content-Security-Policy'].endswith('; report-uri https://sentry.io/api/456/security/?sentry_key=123;')
    del os.environ['RAVEN_DSN']


async def test_csp_with_raven_wrong(settings):
    os.environ['RAVEN_DSN'] = 'foobar'
    h = get_csp_headers(settings)
    assert '/security/?sentry_key=' not in h['Content-Security-Policy']
    del os.environ['RAVEN_DSN']
