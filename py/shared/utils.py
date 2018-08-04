import hashlib
import hmac
import json
import random
import re
import string
from datetime import timedelta
from enum import Enum
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


def slugify(title):
    name = title.replace(' ', '-').lower()
    name = URI_NOT_ALLOWED.sub('', name)
    name = re.sub('-{2,}', '-', name)
    return name.strip('_-')


def mk_password(password: str, settings: Settings) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=settings.bcrypt_work_factor)).decode()


class RequestError(RuntimeError):
    def __init__(self, status, url, *, info=None):
        self.status = status
        self.url = url
        self.info = info

    def __str__(self):
        return f'response {self.status} from "{self.url}"' + (f':\n{self.info[:400]}' if self.info else '')

    def extra(self):
        return self.info


def unsubscribe_sig(user_id, settings: Settings):
    # md5 is fine here as it doesn't have to be especially secure and md5 will yield a shorter signature
    return hmac.new(settings.auth_key.encode(), b'unsub:%d' % user_id, digestmod=hashlib.md5).hexdigest()


def display_cash(amount, currency):
    symbol = CURRENCY_LOOKUP[currency]
    return f'{symbol}{amount:0,.2f}'


def display_cash_free(amount, currency):
    return display_cash(amount, currency) if amount else 'Free'


def static_map_link(lat, lng, *, settings: Settings, size=(500, 300), zoom=13):
    loc = f'{lat:0.7f},{lng:0.7f}'
    return 'https://maps.googleapis.com/maps/api/staticmap?' + urlencode({
        'center': loc,
        'zoom': zoom,
        'size': '{}x{}'.format(*size),
        'markers': 'size:mid|{}'.format(loc),
        'key': settings.google_maps_static_key,
        'scale': 2,
    })


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


def iso_timedelta(dt: timedelta):
    """
    ISO 8601 encoding
    """
    dt = dt or timedelta(days=1)
    seconds = dt.total_seconds()
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    days, hours, minutes = map(int, (days, hours, minutes))
    seconds = round(seconds, 6)
    return f'P{days}DT{hours}H{minutes}M{seconds:0.0f}S'


def encrypt_json(data, *, auth_fernet) -> str:
    return auth_fernet.encrypt(json.dumps(data).encode()).decode()


def password_reset_link(user_id, *, auth_fernet):
    return '/set-password/?sig=' + encrypt_json(user_id, auth_fernet=auth_fernet)


def pseudo_random_str(length=10):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))
