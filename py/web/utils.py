import datetime
import json
from decimal import Decimal
from typing import Type, TypeVar
from uuid import UUID

from aiohttp.web import Response
from aiohttp.web_exceptions import HTTPClientError
from pydantic import BaseModel, ValidationError


JSON_CONTENT_TYPE = 'application/json'


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


async def parse_request(request, model: Type[T], *, error_headers=None) -> T:
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
        headers_=error_headers
    )


IP_HEADER = 'X-Forwarded-For'


def get_ip(request):
    ips = request.headers.get(IP_HEADER)
    if ips:
        return ips.split(',', 1)[0].strip(' ')
    else:
        return request.remote


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
