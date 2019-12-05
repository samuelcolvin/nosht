import base64
from datetime import datetime
from email import message_from_bytes
from io import BytesIO

from aiohttp import web
from aiohttp.web_middlewares import middleware
from aiohttp.web_response import Response, json_response
from PIL import Image, ImageDraw


async def return_200(request):
    return Response()


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
        return json_response(dict(success=True, hostname='127.0.0.1'))
    elif data['response'] == '__400__':
        return json_response({}, status=400)
    else:
        return json_response(dict(success=False, hostname='127.0.0.1'))


async def google_siw(request):
    return json_response({'certs': 'testing'})


async def facebook_siw(request):
    access_token = request.query['access_token']
    if access_token == '__ok__':
        return json_response(
            {'id': '123456', 'email': 'facebook-auth@example.org', 'first_name': None, 'last_name': 'Book'}
        )
    elif access_token == '__no_user__':
        return json_response({'id': '123456', 'first_name': None, 'last_name': 'Book'})
    else:
        return json_response({}, status=400)


async def stripe_get_customer(request):
    if request.match_info['stripe_customer_id'] == 'xxx':
        return json_response({'id': 'stripe_customer_id', 'url': '/v1/customers/xxx/sources'})
    else:
        return Response(status=404)


async def stripe_post_customers(request):
    return json_response({'id': 'customer-id', 'sources': {'data': [{'id': 'source-id-1'}]}})


async def stripe_create_payment_intent(request):
    data = await request.post()
    action_id = data['metadata[reserve_action_id]']
    return json_response({'id': f'payment_intent_{action_id}', 'client_secret': f'payment_intent_secret_{action_id}'})


async def stripe_get_payment_methods(request):
    if request.match_info['payment_method_id'] == 'missing':
        return Response(status=404)
    elif request.match_info['payment_method_id'] == 'expired':
        created = datetime(2015, 1, 1)
    else:
        created = datetime.utcnow()

    return json_response(
        {
            'id': f'pm_123',
            'customer': 'cus_123',
            'created': int((created - datetime(1970, 1, 1)).total_seconds()),
            'card': {'brand': 'Visa', 'exp_month': 12, 'exp_year': 2032, 'last4': 1234},
            'billing_details': {'address': {'line1': 'hello,'}, 'name': 'Testing Calls'},
        }
    )


async def stripe_get_transaction(request):
    return json_response(
        {
            'id': request.match_info['transaction_id'],
            'currency': 'gbp',
            'object': 'balance_transaction',
            'amount': -1,
            'fee': 50,
        }
    )


async def stripe_post_refund(request):
    return json_response({'id': 'xyz'})


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


async def donorfy_201(request):
    # debug(await request.json())
    request.app['data'][f'{request.path} 201'] = await request.json()
    return Response(status=201)


async def donorfy_200(request):
    request.app['data'][f'{request.path} 200'] = await request.json()
    return Response(status=200)


async def donorfy_get_con_ext_id(request):
    if request.match_info['api_key'] in {'standard', 'default-campaign'}:
        return json_response([{'ConstituentId': '123456', 'ExternalKey': request.match_info['ext_key']}])
    else:
        return Response(status=404)


async def donorfy_get_con_id(request):
    if request.match_info['api_key'] == 'default-campaign':
        return json_response(
            {'ConstituentId': request.match_info['const_id'], 'ExternalKey': None, 'RecruitmentCampaign': ''}
        )
    elif request.match_info['api_key'] == 'standard':
        return json_response(
            {
                'ConstituentId': request.match_info['const_id'],
                'ExternalKey': None,
                'RecruitmentCampaign': 'supper-clubs:the-event-name',
            }
        )
    else:
        return Response(status=404)


async def donorfy_get_con_email(request):
    if request.match_info['api_key'] == 'no-users':
        return Response(status=404)

    ext_id = 'nosht_9999'
    if request.match_info['api_key'] == 'no-ext-id':
        ext_id = None
    elif request.match_info['api_key'] == 'wrong-ext-id':
        ext_id = 'foobar'
    return json_response(
        [{'ConstituentId': '456789', 'ExternalKey': ext_id, 'RecruitmentCampaign': 'supper-clubs:the-event-name'}]
    )


async def donorfy_create_user(request):
    data = await request.json()
    return json_response({'ConstituentId': '456789', 'ExternalKey': data['ExternalKey']})


async def donorfy_transactions(request):
    return json_response({'Id': 'trans_123'}, status=201)


async def donorfy_allocations(request):
    return json_response({'AllocationsList': [{'AllocationId': '123'}]})


async def donorfy_get_campaigns(request):
    return json_response({'LookUps': [{'LookUpDescription': 'supper-clubs:the-event-name', 'IsActive': True}]})


@middleware
async def log_middleware(request, handler):
    path = request.method + ' ' + request.path.strip('/')
    request.app['log'].append(path)
    if request.method == 'POST':
        try:
            data = await request.json()
        except ValueError:
            pass
        else:
            if path in request.app['post_data']:
                request.app['post_data'][path].append(data)
            else:
                request.app['post_data'][path] = [data]
    return await handler(request)


async def create_dummy_server(create_server):
    app = web.Application(middlewares=(log_middleware,))
    app.add_routes(
        [
            web.route('*', '/200/', return_200),
            web.post('/aws_ses_endpoint/', aws_ses),
            web.post('/grecaptcha_url/', grecaptcha),
            web.get('/google_siw_url/', google_siw),
            web.get('/facebook_siw_url/', facebook_siw),
            web.get('/stripe_root_url/customers/{stripe_customer_id}', stripe_get_customer),
            web.post('/stripe_root_url/customers', stripe_post_customers),
            web.post('/stripe_root_url/refunds', stripe_post_refund),
            web.post('/stripe_root_url/payment_intents', stripe_create_payment_intent),
            web.get('/stripe_root_url/payment_methods/{payment_method_id}', stripe_get_payment_methods),
            web.get('/stripe_root_url/balance/history/{transaction_id}', stripe_get_transaction),
            web.route('*', '/aws_endpoint_url/{extra:.*}', aws_endpoint),
            web.get('/s3_demo_image_url/{image:.*}', s3_demo_image),
            web.get('/donorfy_api_root/{api_key}/constituents/ExternalKey/{ext_key}', donorfy_get_con_ext_id),
            web.get('/donorfy_api_root/{api_key}/constituents/EmailAddress/{email}', donorfy_get_con_email),
            web.post('/donorfy_api_root/{api_key}/constituents/{const_id}/AddActiveTags', donorfy_201),
            web.get('/donorfy_api_root/{api_key}/constituents/{const_id}', donorfy_get_con_id),
            web.put('/donorfy_api_root/{api_key}/constituents/{const_id}', donorfy_200),
            web.post('/donorfy_api_root/{api_key}/constituents/{const_id}/Preferences', donorfy_201),
            web.post('/donorfy_api_root/{api_key}/constituents', donorfy_create_user),
            web.post('/donorfy_api_root/{api_key}/constituents/{const_id}/GiftAidDeclarations', donorfy_201),
            web.post('/donorfy_api_root/{api_key}/activities', donorfy_201),
            web.post('/donorfy_api_root/{api_key}/transactions', donorfy_transactions),
            web.get('/donorfy_api_root/{api_key}/transactions/{trans_id}/Allocations', donorfy_allocations),
            web.put('/donorfy_api_root/{api_key}/transactions/Allocation/{alloc}', donorfy_200),
            web.post('/donorfy_api_root/{api_key}/transactions/{trans_id}/AddAllocation', donorfy_201),
            web.get('/donorfy_api_root/{api_key}/System/LookUpTypes/Campaigns', donorfy_get_campaigns),
            web.post('/donorfy_api_root/{api_key}/System/LookUpTypes/Campaigns', donorfy_201),
        ]
    )
    server = await create_server(app)
    app.update(
        log=[],
        post_data={},
        emails=[],
        images=[],
        server_name=f'http://localhost:{server.port}',
        stripe_idempotency_keys=set(),
        data={},
    )
    return server
