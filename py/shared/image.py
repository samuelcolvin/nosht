import asyncio
import os
import random
import string
import sys
from io import BytesIO
from pathlib import Path

import aiobotocore
from PIL import Image

auth = dict(
    aws_access_key_id=os.environ['AWS_ACCESS_KEY'],
    aws_secret_access_key=os.environ['AWS_SECRET_KEY'],
)
AWS_BUCKET = os.environ['AWS_BUCKET']


async def upload(cat: str, main_img: bytes, thumb_img: bytes, loop):
    """
    structure:
    /cat/<cat>/options/<random>/main.jpg
    /cat/<cat>/options/<random>/thumb.jpg

    /cat/<cat>/host/<random>/main.jpg
    /cat/<cat>/host/<random>/thumb.jpg
    """
    r = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
    dest = Path('cat') / cat / 'options' / r
    session = aiobotocore.get_session(loop=loop)
    async with session.create_client('s3', region_name='eu-west-1', **auth) as client:

        print('uploading to', dest)
        await asyncio.gather(
            client.put_object(
                Bucket=AWS_BUCKET,
                Key=str(dest / 'main.jpg'),
                Body=main_img,
                ContentType='image/jpeg',
                ACL='public-read',
            ),
            client.put_object(
                Bucket=AWS_BUCKET,
                Key=str(dest / 'thumb.jpg'),
                Body=thumb_img,
                ContentType='image/jpeg',
                ACL='public-read'
            ),
        )


async def main(path: Path, loop):
    img = Image.open(path)

    for width, height in [(3840, 1000), (1920, 500)]:
        if img.width >= width and img.height >= height:
            # big enough to be retina
            if img.size != (width, height):
                aspect_ratio = img.width / img.height
                if aspect_ratio > 3.84:
                    # wide image
                    resize_to = int(round(height * aspect_ratio)), height
                    extra = (resize_to[0] - width) / 2
                    crop_box = extra, 0, extra + width, height
                else:
                    # tall image
                    resize_to = width, int(round(width / aspect_ratio))
                    extra = (resize_to[1] - height) / 2
                    crop_box = 0, extra, width, extra + height
                # debug(aspect_ratio, resize_to, extra, crop_box)
                img = img.resize(resize_to, Image.ANTIALIAS)
                img = img.crop(crop_box)
            break
    else:
        raise ValueError(f'image too small: {img.size}')
    main_stream, thumb_stream = BytesIO(), BytesIO()
    img.save(main_stream, 'JPEG', optimize=True, quality=95)

    thumb = img.resize((768, 200), Image.ANTIALIAS)  # same shape, height 200
    thumb = thumb.crop((184, 0, 584, 200))  # height staying at 200, width 400 (middle)
    thumb.save(thumb_stream, 'JPEG', optimize=True, quality=95)

    await upload('mountains', main_stream.getvalue(), thumb_stream.getvalue(), loop)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(sys.argv[-1], loop))
