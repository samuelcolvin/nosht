import base64
import hashlib
import hmac
import json
import random
import re
import string
import textwrap
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional, Union
from urllib.parse import urlencode

import bcrypt

from .settings import Settings

URI_NOT_ALLOWED = re.compile(r'[^a-zA-Z0-9_\-/.]')


class Currencies(str, Enum):
    gbp = 'gbp'
    usd = 'usd'
    eur = 'eur'


CURRENCY_LOOKUP = {
    Currencies.gbp: '£',
    Currencies.usd: '$',
    Currencies.eur: '€',
}


def slugify(title, max_length: Optional[int] = None):
    name = title.replace(' ', '-').lower()
    name = URI_NOT_ALLOWED.sub('', name)
    name = re.sub(r'-{2,}', '-', name)
    name = name.strip('_-')
    if max_length is None:
        return name
    else:
        return textwrap.shorten(name, width=max_length, placeholder='')


def mk_password(password: str, settings: Settings) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=settings.bcrypt_work_factor)).decode()


class RequestError(RuntimeError):
    def __init__(self, status, url, *, text: str = None):
        self.status = status
        self.url = url
        self.text = text

    def __str__(self):
        return f'response {self.status} from "{self.url}"' + (f':\n{self.text[:400]}' if self.text else '')

    def extra(self):
        return self.text


def unsubscribe_sig(user_id, settings: Settings):
    # md5 is fine here as it doesn't have to be especially secure and md5 will yield a shorter signature
    return hmac.new(settings.auth_key.encode(), b'unsub:%d' % user_id, digestmod=hashlib.md5).hexdigest()


def waiting_list_sig(event_id, user_id, settings: Settings):
    # md5 is fine here as it doesn't have to be especially secure and md5 will yield a shorter signature
    msg = b'waiting-list:%d,%d' % (event_id, user_id)
    return hmac.new(settings.auth_key.encode(), msg, digestmod=hashlib.md5).hexdigest()


def display_cash(amount: Optional[float], currency: Currencies):
    symbol = CURRENCY_LOOKUP[currency]
    return f'{symbol}{amount:0,.2f}'


def display_cash_free(amount: Optional[float], currency: Currencies):
    return display_cash(amount, currency) if amount else 'Free'


def static_map_link(lat, lng, *, settings: Settings, size=(500, 300), zoom=13):
    loc = f'{lat:0.7f},{lng:0.7f}'
    return 'https://maps.googleapis.com/maps/api/staticmap?' + urlencode(
        {
            'center': loc,
            'zoom': zoom,
            'size': '{}x{}'.format(*size),
            'markers': 'size:mid|{}'.format(loc),
            'key': settings.google_maps_static_key,
            'scale': 2,
        }
    )


date_fmt = '{day}{suffix} %b %Y'
datetime_fmt = '%I:%M{ampm}, {day}{suffix} %b %Y'


def format_dt(dt: Union[datetime, date]):
    if 4 <= dt.day <= 20 or 24 <= dt.day <= 30:
        suffix = 'th'
    else:
        suffix = ['st', 'nd', 'rd'][dt.day % 10 - 1]
    fmt = datetime_fmt if isinstance(dt, datetime) else date_fmt
    # ampm is an ugly fix for missing locales on travis
    fmt_ = fmt.format(suffix=suffix, day=dt.day, ampm=f'{dt:%p}'.lower())
    return dt.strftime(fmt_)


def format_duration(td: timedelta):
    """
    should match js/src/utils.js > format_duration
    """
    seconds = td.total_seconds()
    minutes = seconds // 60

    if minutes == 60:
        return '1 hour'

    if minutes < 60:
        return f'{minutes:0.0f} mins'

    hours = minutes // 60
    minutes = minutes % 60
    if hours == 1:
        return f'1 hour {minutes:0.0f} mins'

    if minutes == 0:
        return f'{hours:0.0f} hours'
    else:
        return f'{hours:0.0f} hours {minutes:0.0f} mins'


def encrypt_json(data, *, auth_fernet) -> str:
    return auth_fernet.encrypt(json.dumps(data).encode()).decode()


def password_reset_link(user_id, *, auth_fernet):
    return '/set-password/?sig=' + encrypt_json(user_id, auth_fernet=auth_fernet)


def pseudo_random_str(length=10):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))


def ticket_id_signed(ticket_id, settings: Settings):
    h = hmac.new(settings.auth_key.encode(), b'%d' % ticket_id, digestmod=hashlib.md5)
    check = re.sub(b'[^a-z0-9]', b'', base64.b64encode(h.digest()).lower()).decode()
    return f'{check:.7}-{ticket_id}'


def lenient_json(v):
    if isinstance(v, (str, bytes)):
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            pass
    return v
