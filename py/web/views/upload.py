from web.utils import json_response


async def upload(request):
    # p = await request.post()
    # image = p['image']
    # content = image.file.read()
    return json_response(status='success')
