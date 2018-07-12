import hashlib
import hmac
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
