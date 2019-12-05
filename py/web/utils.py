import datetime
import json
import re
from decimal import Decimal
from typing import Any, Optional, Type, TypeVar
from uuid import UUID

from aiohttp.web import HTTPRequestEntityTooLarge, Response
from aiohttp.web_exceptions import HTTPClientError
from cryptography.fernet import InvalidToken
from pydantic import BaseModel, ValidationError, validate_model
from pydantic.json import pydantic_encoder

from shared.images import check_image_size
from shared.utils import encrypt_json as _encrypt_json

JSON_CONTENT_TYPE = 'application/json'
HEADER_CROSS_ORIGIN = {'Access-Control-Allow-Origin': 'null'}


class ImageModel(BaseModel):
    image: str


def isoformat(o):
    return o.isoformat()


class UniversalEncoder(json.JSONEncoder):
    ENCODER_BY_TYPE = {
        UUID: str,
        datetime.datetime: isoformat,
        datetime.date: isoformat,
        datetime.time: isoformat,
        set: list,
        frozenset: list,
        bytes: lambda o: o.decode(),
        Decimal: str,
    }

    def default(self, obj):
        try:
            encoder = self.ENCODER_BY_TYPE[type(obj)]
        except KeyError:
            return pydantic_encoder(obj)
        return encoder(obj)


def pretty_lenient_json(data):
    return json.dumps(data, indent=2, cls=UniversalEncoder) + '\n'


def raw_json_response(json_str, status_=200):
    return Response(body=json_str.encode() + b'\n', status=status_, content_type=JSON_CONTENT_TYPE)


def json_response(*, status_=200, list_=None, headers_=None, **data):
    return Response(
        body=json.dumps(data if list_ is None else list_).encode(),
        status=status_,
        content_type=JSON_CONTENT_TYPE,
        headers=headers_,
    )


T = TypeVar('Model', bound=BaseModel)


async def parse_request(request, model: Type[T], *, headers_=None) -> T:
    error_details = None
    try:
        data = await request.json()
    except ValueError:
        error_msg = 'Error decoding JSON'
    else:
        try:
            return model.parse_obj(data)
        except ValidationError as e:
            error_msg = 'Invalid Data'
            error_details = e.errors()

    raise JsonErrors.HTTPBadRequest(message=error_msg, details=error_details, headers_=headers_)


async def parse_request_ignore_missing(request, model: Type[T], *, headers_=None) -> T:
    try:
        raw_data = await request.json()
    except ValueError:
        raise JsonErrors.HTTPBadRequest(message='Error decoding JSON', headers_=headers_)
    if not isinstance(raw_data, dict):
        raise JsonErrors.HTTPBadRequest(message='data not a dictionary', headers_=headers_)

    data, fields_set, e = validate_model(model, raw_data)
    if e:
        errors = [e for e in e.errors() if not (e['type'] == 'value_error.missing' and len(e['loc']) == 1)]
        if errors:
            raise JsonErrors.HTTPBadRequest(message='Invalid Data', details=errors, headers_=headers_)

    return model.construct(_fields_set=fields_set, **data)


IP_HEADER = 'X-Forwarded-For'


def get_ip(request):
    ips = request.headers.get(IP_HEADER)
    if ips:
        return ips.split(',', 1)[0].strip(' ')
    else:
        return request.remote


def request_root(request):
    # request.url.scheme doesn't work as https is terminated, could use https forward header or referer
    scheme = 'https' if request.app['settings'].on_heroku else 'http'
    return f'{scheme}://{request.host}'


class JsonErrors:
    class _HTTPClientErrorJson(HTTPClientError):
        custom_reason = None

        def __init__(self, headers_=None, **data):
            super().__init__(
                text=pretty_lenient_json(data),
                content_type=JSON_CONTENT_TYPE,
                headers=headers_,
                reason=self.custom_reason,
            )

    class HTTPBadRequest(_HTTPClientErrorJson):
        status_code = 400

    class HTTPUnauthorized(_HTTPClientErrorJson):
        status_code = 401

    class HTTPPaymentRequired(_HTTPClientErrorJson):
        status_code = 402

    class HTTPForbidden(_HTTPClientErrorJson):
        status_code = 403

    class HTTPNotFound(_HTTPClientErrorJson):
        status_code = 404

    class HTTPConflict(_HTTPClientErrorJson):
        status_code = 409

    class HTTP470(_HTTPClientErrorJson):
        status_code = 470
        custom_reason = 'Invalid user input'


def encrypt_json(app, data: Any) -> str:
    return _encrypt_json(data, auth_fernet=app['auth_fernet'])


def decrypt_json(app, token: bytes, *, ttl: int = None, headers_=None) -> Any:
    try:
        return json.loads(app['auth_fernet'].decrypt(token, ttl=ttl).decode())
    except InvalidToken:
        raise JsonErrors.HTTPBadRequest(message='invalid token', headers_=headers_)


def split_name(raw_name):
    if not raw_name:
        return None, None
    raw_name = raw_name.strip(' ')
    if ' ' not in raw_name:
        # assume just last_name
        return None, raw_name
    else:
        return tuple(n.strip(' ') or None for n in raw_name.split(' ', 1))


async def request_image(request, *, expected_size=None):
    try:
        p = await request.post()
    except ValueError:
        raise HTTPRequestEntityTooLarge
    try:
        image = p['image']
    except KeyError:
        raise JsonErrors.HTTPBadRequest(message='image missing')
    content = image.file.read()
    try:
        check_image_size(content, expected_size=expected_size)
    except ValueError as e:
        raise JsonErrors.HTTPBadRequest(message=str(e))
    return content


_simplify = [
    (re.compile(r'\<.*?\>', flags=re.S), ''),
    (re.compile(r'(^| )([_\*]{1,2})(\w.*?\w)\2($| )'), r'\1\3\4'),
    (re.compile(r'\[(.+?)\]\(:?.*?\)'), r'\1'),
    (re.compile(r'^#+ ', flags=re.M), ''),
    (re.compile(r'^ *[*\-] ', flags=re.M), ''),
    (re.compile(r'^ *(\d+\.) ', flags=re.M), r'\1 '),
    (re.compile(r'`'), ''),
    (re.compile(r'\n+'), ' '),
]


def clean_markdown(md):
    text = md
    for regex, p in _simplify:
        text = regex.sub(p, text)
    return text


def get_offset(request, paginate_by=100):
    page = request.query.get('page')
    if not page:
        return 0

    try:
        p = int(page)
        if p < 1:
            raise ValueError()
    except ValueError:
        raise JsonErrors.HTTPBadRequest(message=f"invalid page '{page}'")
    else:
        return (p - 1) * paginate_by


min_length = 3
max_length = 100
re_null = re.compile('\x00')
# characters that cause syntax errors in to_tsquery and/or should be used to split
pg_tsquery_split = ''.join((':', '&', '|', '%', '"', "'", '<', '>', '!', '*', '(', ')', r'\s'))
re_tsquery = re.compile(f'[^{pg_tsquery_split}]{{2,}}')


def prepare_search_query(request) -> Optional[str]:
    query = request.query.get('q', '')

    query = re_null.sub('', query)[:max_length]
    if len(query) < min_length:
        return None

    words = re_tsquery.findall(query)
    if not words:
        return None

    # just using a "foo & bar:*"
    return ' & '.join(words) + ':*'
