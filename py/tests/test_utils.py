from datetime import datetime, timedelta

import pytest

from shared.utils import RequestError, format_duration
from web.utils import pretty_lenient_json


def test_pretty_json():
    a = {'foo': datetime(1970, 1, 2)}
    assert pretty_lenient_json(a) == (
        '{\n'
        '  "foo": "1970-01-02T00:00:00"\n'
        '}\n'
    )


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
