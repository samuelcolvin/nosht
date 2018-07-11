import re

import bcrypt

from .settings import Settings

URI_NOT_ALLOWED = re.compile(r'[^a-zA-Z0-9_\-/.]')


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
        return f'response {self.status} from "{self.url}"'
