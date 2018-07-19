import base64
from email import message_from_bytes

from aiohttp import web
from aiohttp.web_middlewares import middleware
from aiohttp.web_response import Response, json_response


async def aws_ses(request):
    data = await request.post()
    raw_email = base64.b64decode(data['RawMessage.Data'])
    email = message_from_bytes(raw_email)
    d = dict(email)
    for part in email.walk():
        payload = part.get_payload(decode=True)
        if payload:
            d[f'part:{part.get_content_type()}'] = payload.decode().replace('\r\n', '\n')

    request.app['log'][-1] = ('email_send_endpoint', 'Subject: "{Subject}", To: "{To}"'.format(**email))
    request.app['emails'].append(d)
    return Response(text='<MessageId>testing</MessageId>')


async def grecaptcha(request):
    data = await request.post()
    request.app['log'][-1] = ('grecaptcha', data['response'])
    if data['response'] == '__ok__':
        return json_response(dict(success=True, score=1, action='testing', hostname='127.0.0.1'))
    elif data['response'] == '__low_score__':
        return json_response(dict(success=True, score=0.1))
    else:
        return json_response(dict(success=False))


async def google_siw(request):
    return json_response({'certs': 'testing'})


async def facebook_siw(request):
    return json_response({
        'id': '123456',
        'email': 'facebook-auth@EXAMPLE.com',
        'first_name': None,
        'last_name': 'Book',
    })


async def stripe_get_customer_sources(request):
    return json_response('TODO')


async def stripe_post_customer_sources(request):
    return json_response('TODO')


async def stripe_post_customers(request):
    return json_response({
        'id': 'customer-id',
        'sources': {
            'data': [
                {
                    'id': 'source-id-1'
                }
            ]
        }
    })


async def stripe_post_charges(request):
    return json_response({
        'id': 'charge-id',
        'source': {
            'id': 'source-id',
            'last4': '1234',
            'exp_month': '12',
            'exp_year': 2032,
        }
    })


@middleware
async def log_middleware(request, handler):
    request.app['log'].append(request.path.strip('/'))
    return await handler(request)


async def create_dummy_server(loop, create_server):
    app = web.Application(loop=loop, middlewares=(log_middleware,))
    app.add_routes([
        web.post('/aws_ses_endpoint/', aws_ses),
        web.post('/grecaptcha_url/', grecaptcha),
        web.get('/google_siw_url/', google_siw),
        web.get('/facebook_siw_url/', facebook_siw),

        web.get('/stripe_root_url/customers/{stripe_customer_id}/sources', stripe_get_customer_sources),
        web.post('/stripe_root_url/customers/{stripe_customer_id}/sources', stripe_post_customer_sources),
        web.post('/stripe_root_url/customers', stripe_post_customers),
        web.post('/stripe_root_url/charges', stripe_post_charges),
    ])
    server = await create_server(app)
    app.update(
        log=[],
        emails=[],
        server_name=f'http://localhost:{server.port}'
    )
    return server
