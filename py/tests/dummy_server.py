import base64
from email import message_from_bytes
from io import BytesIO

from aiohttp import web
from aiohttp.web_middlewares import middleware
from aiohttp.web_response import Response, json_response
from PIL import Image, ImageDraw


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
        'email': 'facebook-auth@example.org',
        'first_name': None,
        'last_name': 'Book',
    })


async def stripe_get_customer_sources(request):
    return json_response({
        'object': 'list',
        'data': [
            {
                'last4': '4242',
                'brand': 'Visa',
                'exp_month': 8,
                'exp_year': 2019,
            },
        ],
        'has_more': False,
        'url': '/v1/customers/xxx/sources',
    })


async def stripe_post_customer_sources(request):
    return json_response({
        'id': 'src_id_123456',
    })


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
    data = await request.post()
    if 'decline' in data['description']:
        return json_response({
          'error': {
            'code': 'card_declined',
            'message': 'Your card was declined.',
            'type': 'card_error'
          }
        }, status=402)
    else:
        return json_response({
            'id': 'charge-id',
            'source': {
                'id': 'source-id',
                'last4': '1234',
                'brand': 'Visa',
                'exp_month': '12',
                'exp_year': 2032,
            }
        })


s3_response = """\
<?xml version="1.0" ?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
    <Name>testingbucket.example.org</Name>
    <Prefix>co-slug/cat-slug/option</Prefix>
    <KeyCount>14</KeyCount>
    <MaxKeys>1000</MaxKeys>
    <IsTruncated>false</IsTruncated>
    <Contents>
        <Key>co-slug/cat-slug/option/randomkey1/main.png</Key>
        <LastModified>2032-07-31T18:12:48.000Z</LastModified>
        <ETag>&quot;d9028601438a5f3f6b21f2ddb171182f&quot;</ETag>
        <Size>1930930</Size>
        <StorageClass>STANDARD</StorageClass>
    </Contents>
    <Contents>
        <Key>co-slug/cat-slug/option/randomkey1/thumb.png</Key>
        <LastModified>2032-07-31T18:12:48.000Z</LastModified>
        <ETag>&quot;f0f075450aca93b87356c580a34d3f80&quot;</ETag>
        <Size>53866</Size>
        <StorageClass>STANDARD</StorageClass>
    </Contents>
    <Contents>
        <Key>co-slug/cat-slug/option/randomkey2/main.png</Key>
        <LastModified>2032-07-31T19:05:00.000Z</LastModified>
        <ETag>&quot;e058658dc289ffc656fbaa761f653b0a&quot;</ETag>
        <Size>1269965</Size>
        <StorageClass>STANDARD</StorageClass>
    </Contents>
    <Contents>
        <Key>co-slug/cat-slug/option/randomkey2/thumb.png</Key>
        <LastModified>2032-07-31T19:05:00.000Z</LastModified>
        <ETag>&quot;395ab74b92338d76e5f185fd5b8135de&quot;</ETag>
        <Size>32279</Size>
        <StorageClass>STANDARD</StorageClass>
    </Contents>

</ListBucketResult>"""


async def aws_endpoint(request):
    # very VERY simple mock of s3
    if request.method == 'GET':
        return Response(text=s3_response)
    elif request.method == 'PUT':
        image_data = await request.read()
        img = Image.open(BytesIO(image_data))
        request.app['images'].append((request.path, img.width, img.height))
    return Response(text='')


async def s3_demo_image(request):
    width, height = 2000, 1200
    stream = BytesIO()
    image = Image.new('RGB', (width, height), (50, 100, 150))
    ImageDraw.Draw(image).line((0, 0) + image.size, fill=128)
    image.save(stream, format='JPEG', optimize=True)
    return Response(body=stream.getvalue())


@middleware
async def log_middleware(request, handler):
    request.app['log'].append(request.method + ' ' + request.path.strip('/'))
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

        web.route('*', '/aws_endpoint_url/{extra:.*}', aws_endpoint),
        web.get('/s3_demo_image_url/{image:.*}', s3_demo_image),
    ])
    server = await create_server(app)
    app.update(
        log=[],
        emails=[],
        images=[],
        server_name=f'http://localhost:{server.port}'
    )
    return server
