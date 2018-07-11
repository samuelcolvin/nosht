import hashlib
import hmac

from .settings import Settings


def unsubscribe_sig(user_id, settings: Settings):
    # md5 is fine here as it doesn't have to be especially secure and md5 will yield a shorter signature
    return hmac.new(settings.auth_key.encode(), b'unsub:%d' % user_id, digestmod=hashlib.md5).hexdigest()
