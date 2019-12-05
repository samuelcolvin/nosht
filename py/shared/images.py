import asyncio
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import List, Optional

import aiobotocore
from PIL import Image

from .settings import Settings
from .utils import pseudo_random_str

logger = logging.getLogger('nosht.images')
LARGE_SIZE = 3840, 1000
SMALL_SIZE = 1920, 500
STRIP_DOMAIN = re.compile('^https?://.+?/')


def strip_domain(url):
    return STRIP_DOMAIN.sub('', url)


def check_image_size(image_data: bytes, *, expected_size):
    try:
        img = Image.open(BytesIO(image_data))
    except OSError:
        raise ValueError('invalid image')
    width, height = expected_size or SMALL_SIZE
    if img.width < width or img.height < height:
        raise ValueError(f'image too small: {img.width}x{img.height} < {width}x{height}')


def create_s3_session(settings: Settings):
    session = aiobotocore.get_session()
    return session.create_client(
        's3',
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key,
        aws_secret_access_key=settings.aws_secret_key,
        endpoint_url=settings.aws_endpoint_url,
    )


async def list_images(path: Path, settings: Settings) -> List[str]:
    images = []
    async with create_s3_session(settings) as s3:
        paginator = s3.get_paginator('list_objects_v2')
        async for result in paginator.paginate(Bucket=settings.s3_bucket, Prefix=str(settings.s3_prefix / path)):
            for c in result.get('Contents', []):
                p = c['Key']
                if re.search(r'main\.\w+$', p):
                    images.append(f'{settings.s3_domain}/{p}')
    return images


async def delete_image(image: str, settings: Settings):
    path = Path(strip_domain(image))
    async with create_s3_session(settings) as s3:
        await asyncio.gather(
            s3.delete_object(Bucket=settings.s3_bucket, Key=str(path)),
            s3.delete_object(Bucket=settings.s3_bucket, Key=str(path.with_name('thumb').with_suffix(path.suffix))),
        )


async def _upload(upload_path: Path, main_img: bytes, thumb_img: Optional[bytes], settings: Settings) -> str:
    upload_path = settings.s3_prefix / upload_path / pseudo_random_str()

    async with create_s3_session(settings) as s3:
        logger.info('uploading to %s', upload_path)
        coros = [
            s3.put_object(
                Bucket=settings.s3_bucket,
                Key=str(upload_path / 'main.png'),
                Body=main_img,
                ContentType='image/png',
                ACL='public-read',
            ),
        ]
        if thumb_img:
            coros.append(
                s3.put_object(
                    Bucket=settings.s3_bucket,
                    Key=str(upload_path / 'thumb.png'),
                    Body=thumb_img,
                    ContentType='image/png',
                    ACL='public-read',
                )
            )
        await asyncio.gather(*coros)
    return f'{settings.s3_domain}/{upload_path}/main.png'


def resize_crop(img, req_width, req_height):
    if img.size == (req_width, req_height):
        return None, None
    aspect_ratio = img.width / img.height
    if aspect_ratio > (req_width / req_height):
        # wide image
        resize_to = int(round(req_height * aspect_ratio)), req_height
        extra = (resize_to[0] - req_width) / 2
        crop_box = extra, 0, extra + req_width, req_height
    else:
        # tall image
        resize_to = req_width, int(round(req_width / aspect_ratio))
        extra = (resize_to[1] - req_height) / 2
        crop_box = 0, extra, req_width, extra + req_height
    return resize_to, crop_box


async def upload_background(image_data: bytes, upload_path: Path, settings: Settings) -> str:
    try:
        img = Image.open(BytesIO(image_data))
    except OSError:
        raise ValueError('invalid image')

    for width, height in (LARGE_SIZE, SMALL_SIZE):
        if img.width >= width and img.height >= height:
            resize_to, crop_box = resize_crop(img, width, height)
            if resize_to:
                img = img.resize(resize_to, Image.ANTIALIAS)
                img = img.crop(crop_box)
            break
    else:
        raise ValueError(f'image too small: {img.size}')

    main_stream = BytesIO()
    img.save(main_stream, 'PNG', optimize=True, quality=95)

    thumb_stream = BytesIO()
    thumb = img.resize((768, 200), Image.ANTIALIAS)  # same shape, height 200
    thumb = thumb.crop((184, 0, 584, 200))  # height staying at 200, width 400 (middle)
    thumb.save(thumb_stream, 'PNG', optimize=True, quality=95)

    return await _upload(upload_path, main_stream.getvalue(), thumb_stream.getvalue(), settings)


async def upload_other(image_data: bytes, *, upload_path: Path, settings: Settings, req_size, thumb=False) -> str:
    img = Image.open(BytesIO(image_data))
    if img.mode != 'RGB':
        img = img.convert('RGB')

    req_width, req_height = req_size
    assert img.width >= req_width and img.height >= req_height, 'image too small'

    aspect_ratio = img.width / img.height
    if aspect_ratio > (req_width / req_height):
        # wide image
        resize_to = int(round(req_height * aspect_ratio)), req_height
    else:
        # tall image
        resize_to = req_width, int(round(req_width / aspect_ratio))

    main_img = img.resize(resize_to, Image.ANTIALIAS)
    main_stream = BytesIO()
    main_img.save(main_stream, format='PNG', optimize=True, quality=95)

    thumb_bytes = None
    if thumb:
        resize_to, crop_box = resize_crop(img, 400, 200)
        if resize_to:
            thumb_img = img.resize(resize_to, Image.ANTIALIAS)
            thumb_img = thumb_img.crop(crop_box)
        else:
            thumb_img = img.copy()

        thumb_stream = BytesIO()
        thumb_img.save(thumb_stream, 'PNG', optimize=True, quality=95)
        thumb_bytes = thumb_stream.getvalue()

    return await _upload(upload_path, main_stream.getvalue(), thumb_bytes, settings)


async def upload_force_shape(image_data: bytes, *, upload_path: Path, settings: Settings, req_size) -> str:
    img = Image.open(BytesIO(image_data))
    if img.mode != 'RGB':
        img = img.convert('RGB')

    req_width, req_height = req_size
    assert img.width >= req_width and img.height >= req_height, 'image too small'

    resize_to, crop_box = resize_crop(img, req_width, req_height)
    if resize_to:
        img = img.resize(resize_to, Image.ANTIALIAS)
        img = img.crop(crop_box)

    img_stream = BytesIO()
    img.save(img_stream, 'PNG', optimize=True, quality=95)

    return await _upload(upload_path, img_stream.getvalue(), None, settings)
