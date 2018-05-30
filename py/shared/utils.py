import re

URI_NOT_ALLOWED = re.compile(r'[^a-zA-Z0-9_\-/.]')


def slugify(title):
    name = title.replace(' ', '-').lower()
    name = URI_NOT_ALLOWED.sub('', name)
    name = re.sub('-{2,}', '-', name)
    return name.strip('_-')
