from datetime import datetime

from web.utils import pretty_lenient_json


def test_pretty_json():
    a = {'foo': datetime(1970, 1, 2)}
    assert pretty_lenient_json(a) == (
        '{\n'
        '  "foo": "1970-01-02T00:00:00"\n'
        '}\n'
    )
