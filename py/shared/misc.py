import hashlib
import hmac
from datetime import timedelta
from urllib.parse import urlencode

from .settings import Settings


def unsubscribe_sig(user_id, settings: Settings):
    # md5 is fine here as it doesn't have to be especially secure and md5 will yield a shorter signature
    return hmac.new(settings.auth_key.encode(), b'unsub:%d' % user_id, digestmod=hashlib.md5).hexdigest()


CURRENCY_LOOKUP = {
  'gbp': '£',
  'usd': '$',
  'eur': '€',
}


def display_cash(amount, currency):
    symbol = CURRENCY_LOOKUP[currency]
    return f'{symbol}{amount:0,.2f}'


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
        return f'{minutes} mins'

    hours = minutes // 60
    minutes = minutes % 60
    if hours == 1:
        return f'1 hour {minutes} mins'

    if minutes == 0:
        return f'{hours} hours'
    else:
        return f'{hours} hours {minutes} mins'
