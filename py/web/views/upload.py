from web.utils import json_response


async def upload(request):
    p = await request.post()
    debug(p)
    image = p['image']
    debug(image.filename)
    content = image.file.read()
    debug(len(content))
    return json_response(status='success')
