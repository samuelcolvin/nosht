from aiohttp_session import get_session

from web.utils import json_response


async def login(request):
    session = await get_session(request)
    session['user'] = 123
    return json_response(message='hello')
