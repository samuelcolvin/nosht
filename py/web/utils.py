import datetime
import json
import re
from decimal import Decimal
from uuid import UUID

from aiohttp import ClientSession
from aiohttp.web import Response
from aiohttp.web_exceptions import HTTPClientError
from google.auth import jwt as google_jwt
from google.oauth2.id_token import _GOOGLE_OAUTH2_CERTS_URL

from shared.settings import Settings

CERTS = None


async def google_certs():
    global CERTS
    if not CERTS:
        async with ClientSession(conn_timeout=10, read_timeout=10) as session:
            async with session.get(_GOOGLE_OAUTH2_CERTS_URL) as r:
                assert r.status == 200, r.status
                CERTS = await r.json()
    return CERTS


async def google_get_details(settings: Settings, id_token):
    certs = await google_certs()
    id_info = google_jwt.decode(id_token, certs=certs, audience=settings.google_siw_client_key)

    # this should happen very rarely, if it does someone is doing something nefarious or things have gone very wrong
    assert id_info['iss'] in {'accounts.google.com', 'https://accounts.google.com'}, 'wrong google iss'
    assert id_info['email_verified'], 'google email not verified'
    email = id_info['email'].lower()

    return {
        'email': email,
        'first_name': id_info.get('given_name'),
        'last_name': id_info.get('family_name'),
    }


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


def json_response(request, *, status_=200, list_=None, **data):
    if JSON_CONTENT_TYPE in request.headers.get('Accept', ''):
        to_json = json.dumps
    else:
        to_json = pretty_json

    return Response(
        body=to_json(data if list_ is None else list_).encode(),
        status=status_,
        content_type=JSON_CONTENT_TYPE,
    )


class JsonErrors:
    class _HTTPClientErrorJson(HTTPClientError):
        def __init__(self, **data):
            super().__init__(
                text=pretty_lenient_json(data),
                content_type=JSON_CONTENT_TYPE,
            )

    class HTTPBadRequest(_HTTPClientErrorJson):
        status_code = 400

    class HTTPUnauthorized(_HTTPClientErrorJson):
        status_code = 401

    class HTTPForbidden(_HTTPClientErrorJson):
        status_code = 403

    class HTTPNotFound(_HTTPClientErrorJson):
        status_code = 404
