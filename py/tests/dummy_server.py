import base64
from email import message_from_bytes

from aiohttp import web
from aiohttp.web_response import Response


async def email_send_endpoint(request):
    data = await request.post()
    raw_email = base64.b64decode(data['RawMessage.Data'])
    email = message_from_bytes(raw_email)
    # debug(raw_email.decode(), dict(email))

    request.app['log'].append(('email_send_endpoint', 'Subject: "{Subject}", To: "{To}"'.format(**email)))
    return Response(text='<MessageId>testing</MessageId>')


async def create_dummy_server(loop, create_server):
    app = web.Application(loop=loop)
    app.add_routes([
        web.post('/send/email/', email_send_endpoint),
    ])
    server = await create_server(app)
    app.update(
        log=[],
        server_name=f'http://localhost:{server.port}'
    )
    return server
