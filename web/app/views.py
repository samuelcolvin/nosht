import logging
from datetime import datetime

from .utils import json_response

logger = logging.getLogger('events.web')


async def foobar(request):
    return json_response(request, text=f'this is foobar: {datetime.now():%H:%M:%S}')
