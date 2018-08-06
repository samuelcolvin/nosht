from datetime import datetime, timedelta

import pytest
from aiohttp.test_utils import make_mocked_request

from shared.utils import RequestError, format_duration
from web.utils import get_ip, pretty_lenient_json, split_name


def test_pretty_json():
    a = {'foo': datetime(1970, 1, 2)}
    assert pretty_lenient_json(a) == (
        '{\n'
        '  "foo": "1970-01-02T00:00:00"\n'
        '}\n'
    )


def test_pretty_json_bytes():
    a = {'foo': b'xxx'}
    assert pretty_lenient_json(a) == (
        '{\n'
        '  "foo": "xxx"\n'
        '}\n'
    )


def test_invalid_json():
    with pytest.raises(TypeError):
        pretty_lenient_json({1: pytest})


@pytest.mark.parametrize('input,output', [
    (timedelta(minutes=10), '10 mins'),
    (timedelta(hours=1), '1 hour'),
    (timedelta(hours=1, minutes=1), '1 hour 1 mins'),
    (timedelta(hours=2), '2 hours'),
    (timedelta(hours=2, minutes=3), '2 hours 3 mins'),
])
def test_duration_formats(input, output):
    assert format_duration(input) == output


def test_request_error():
    r = RequestError(500, 'xxx', info='hello')
    assert str(r) == 'response 500 from "xxx":\nhello'
    assert r.extra() == 'hello'


@pytest.mark.parametrize('input,first_name,last_name', [
    ('', None, None),
    ('Foobar', None, 'Foobar'),
    ('Foo Bar', 'Foo', 'Bar'),
])
def test_split_name(input, first_name, last_name):
    assert split_name(input) == (first_name, last_name)


def test_get_ip():
    req = make_mocked_request('GET', '/', headers={'X-Forwarded-For': ' 1.2.3.4, 5.6.7.8'})
    assert get_ip(req) == '1.2.3.4'
