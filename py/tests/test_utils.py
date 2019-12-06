import json
from datetime import datetime, timedelta

import pytest
from aiohttp.test_utils import make_mocked_request

from shared.utils import RequestError, format_duration, ticket_id_signed
from web.utils import (
    JsonErrors,
    clean_markdown,
    get_ip,
    get_offset,
    prepare_search_query,
    pretty_lenient_json,
    split_name,
)


def test_pretty_json():
    a = {'foo': datetime(1970, 1, 2)}
    assert pretty_lenient_json(a) == '{\n  "foo": "1970-01-02T00:00:00"\n}\n'


def test_pretty_json_bytes():
    a = {'foo': b'xxx'}
    assert pretty_lenient_json(a) == '{\n  "foo": "xxx"\n}\n'


def test_invalid_json():
    with pytest.raises(TypeError):
        pretty_lenient_json({1: pytest})


@pytest.mark.parametrize(
    'input,output',
    [
        (timedelta(minutes=10), '10 mins'),
        (timedelta(hours=1), '1 hour'),
        (timedelta(hours=1, minutes=1), '1 hour 1 mins'),
        (timedelta(hours=2), '2 hours'),
        (timedelta(hours=2, minutes=3), '2 hours 3 mins'),
    ],
)
def test_duration_formats(input, output):
    assert format_duration(input) == output


def test_request_error():
    r = RequestError(500, 'xxx', text='hello')
    assert str(r) == 'response 500 from "xxx":\nhello'
    assert r.extra() == 'hello'


@pytest.mark.parametrize(
    'input,first_name,last_name', [('', None, None), ('Foobar', None, 'Foobar'), ('Foo Bar', 'Foo', 'Bar')]
)
def test_split_name(input, first_name, last_name):
    assert split_name(input) == (first_name, last_name)


def test_get_ip():
    req = make_mocked_request('GET', '/', headers={'X-Forwarded-For': ' 1.2.3.4, 5.6.7.8'})
    assert get_ip(req) == '1.2.3.4'


@pytest.mark.parametrize(
    'input,output',
    [
        ('something <a href="/asdf/">with a link</a>', 'something with a link'),
        ('with __bold__ here', 'with bold here'),
        ('with _italics_ here', 'with italics here'),
        ('with **bold** here', 'with bold here'),
        ('with **bold**', 'with bold'),
        ('**bold** here', 'bold here'),
        ('with *italics* here', 'with italics here'),
        ('including [a link](/foobar/)', 'including a link'),
        ('including a\n# title', 'including a title'),
        ('including a\n* bullet 1', 'including a bullet 1'),
        ('including a\n- bullet 2', 'including a bullet 2'),
        ('including an\n  * indented bullet', 'including an indented bullet'),
        ('including a\n42. numbered list', 'including a 42. numbered list'),
        ('including some `code`', 'including some code'),
    ],
)
def test_clean_markdown(input, output):
    assert clean_markdown(input) == output


@pytest.mark.parametrize('input', ['with *in a line', 'with **in a line', 'with **in* a line', 'with _italics* here'])
def test_clean_markdown_unchanged(input):
    assert clean_markdown(input) == input


@pytest.mark.parametrize('ticket_id,expected', [(1, 'hzjsbsm-1'), (123, 'irorchu-123'), (321654, 'admuo35-321654')])
def test_ticket_id_signed(ticket_id, expected, settings):
    assert expected == ticket_id_signed(ticket_id, settings)


class Request:
    def __init__(self, **query):
        self.query = query


def test_get_offset():
    assert get_offset(Request()) == 0
    assert get_offset(Request(page='1')) == 0
    assert get_offset(Request(page='2')) == 100
    assert get_offset(Request(page='3')) == 200

    with pytest.raises(JsonErrors.HTTPBadRequest) as exc_info:
        get_offset(Request(page='-1'))
    assert json.loads(exc_info.value.text) == {'message': "invalid page '-1'"}

    with pytest.raises(JsonErrors.HTTPBadRequest) as exc_info:
        get_offset(Request(page='foo'))
    assert json.loads(exc_info.value.text) == {'message': "invalid page 'foo'"}


@pytest.mark.parametrize(
    'input,output',
    [
        (dict(q='foobar'), 'foobar:*'),
        (dict(q='foobar:*'), 'foobar:*'),
        (dict(q='foo bar'), 'foo & bar:*'),
        (dict(q='@@@@'), '@@@@:*'),
        (dict(q='apple & pie'), 'apple & pie:*'),
        (dict(q='(apple pie)'), 'apple & pie:*'),
        (dict(), None),
        (dict(q=''), None),
        (dict(q='&&&&'), None),
        (dict(q='!!!'), None),
    ],
)
def test_prepare_search_query(input, output):
    assert prepare_search_query(Request(**input)) == output
