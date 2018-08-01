import datetime
import json
from decimal import Decimal
from typing import Any, Type, TypeVar
from uuid import UUID

from aiohttp.web import HTTPRequestEntityTooLarge, Response
from aiohttp.web_exceptions import HTTPClientError
from cryptography.fernet import InvalidToken
from pydantic import BaseModel, ValidationError
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
            return super().default(obj)
        return encoder(obj)


def pretty_lenient_json(data):
    return json.dumps(data, indent=2, cls=UniversalEncoder) + '\n'


def pretty_json(data):
    return json.dumps(data, indent=2) + '\n'


def raw_json_response(json_str, status_=200):
    return Response(
        body=json_str.encode() + b'\n',
        status=status_,
        content_type=JSON_CONTENT_TYPE,
    )


def json_response(*, status_=200, list_=None, headers_=None, **data):
    return Response(
        body=json.dumps(data if list_ is None else list_).encode(),
        status=status_,
        content_type=JSON_CONTENT_TYPE,
        headers=headers_
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

    raise JsonErrors.HTTPBadRequest(
        message=error_msg,
        details=error_details,
        headers_=headers_
    )


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
        def __init__(self, headers_=None, **data):
            super().__init__(
                text=pretty_lenient_json(data),
                content_type=JSON_CONTENT_TYPE,
                headers=headers_,
            )

    class HTTPBadRequest(_HTTPClientErrorJson):
        status_code = 400

    class HTTPUnauthorized(_HTTPClientErrorJson):
        status_code = 401

    class HTTPForbidden(_HTTPClientErrorJson):
        status_code = 403

    class HTTPNotFound(_HTTPClientErrorJson):
        status_code = 404

    class HTTP470(_HTTPClientErrorJson):
        status_code = 470


def encrypt_json(app, data: Any) -> str:
    return _encrypt_json(data, auth_fernet=app['auth_fernet'])


def decrypt_json(app, token: bytes, *, ttl: int=None, headers_=None) -> Any:
    try:
        return json.loads(app['auth_fernet'].decrypt(token, ttl=ttl).decode())
    except InvalidToken:
        raise JsonErrors.HTTPBadRequest(message='invalid token', headers_=headers_)


def to_json_if(obj):
    obj_ = {k: v for k, v in obj.items() if v}
    if obj_:
        return json.dumps(obj_, default=pydantic_encoder)


def split_name(raw_name):
    if not raw_name:
        return None, None
    raw_name = raw_name.strip(' ')
    if ' ' not in raw_name:
        # assume just last_name
        return None, raw_name
    else:
        return [n.strip(' ') or None for n in raw_name.split(' ', 1)]


async def request_image(request):
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
        check_image_size(content)
    except ValueError as e:
        raise JsonErrors.HTTPBadRequest(message=str(e))
    return content
