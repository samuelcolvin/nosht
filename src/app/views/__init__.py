import logging
from datetime import datetime

from app.utils import json_response

logger = logging.getLogger('events.web')


async def foobar(request):
    worker = request.app['worker']
    await worker.testing()
    return json_response(request, text=f'this is foobar: {datetime.now():%H:%M:%S.%f}')
