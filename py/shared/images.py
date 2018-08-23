import asyncio
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Optional, Set

import aiobotocore
from PIL import Image

from .settings import Settings
from .utils import pseudo_random_str

logger = logging.getLogger('nosht.images')
LARGE_SIZE = 3840, 1000
SMALL_SIZE = 1920, 500
LOGO_SIZE = 256, 256
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


async def list_images(path: Path, settings: Settings) -> Set[str]:
    files = set()
    async with create_s3_session(settings) as s3:
        paginator = s3.get_paginator('list_objects_v2')
        async for result in paginator.paginate(Bucket=settings.s3_bucket, Prefix=str(settings.s3_prefix / path)):
            for c in result.get('Contents', []):
                p = re.sub(r'/(?:main|thumb)\.jpg$', '', c['Key'])
                url = f'{settings.s3_domain}/{p}'
                files.add(url)
    return files


async def delete_image(image: str, settings: Settings):
    path = Path(strip_domain(image))
    async with create_s3_session(settings) as s3:
        await asyncio.gather(
            s3.delete_object(Bucket=settings.s3_bucket, Key=str(path / 'main.jpg')),
            s3.delete_object(Bucket=settings.s3_bucket, Key=str(path / 'thumb.jpg')),
        )


async def _upload(upload_path: Path, main_img: bytes, thumb_img: Optional[bytes], settings: Settings) -> str:
    upload_path = settings.s3_prefix / upload_path / pseudo_random_str()

    async with create_s3_session(settings) as s3:
        logger.info('uploading to %s', upload_path)
        coros = [
            s3.put_object(
                Bucket=settings.s3_bucket,
                Key=str(upload_path / 'main.jpg'),
                Body=main_img,
                ContentType='image/jpeg',
                ACL='public-read',
            ),
        ]
        if thumb_img:
            coros.append(s3.put_object(
                Bucket=settings.s3_bucket,
                Key=str(upload_path / 'thumb.jpg'),
                Body=thumb_img,
                ContentType='image/jpeg',
                ACL='public-read'
            ))
        await asyncio.gather(*coros)
    return f'{settings.s3_domain}/{upload_path}'


async def resize_upload(image_data: bytes, upload_path: Path, settings: Settings) -> str:
    try:
        img = Image.open(BytesIO(image_data))
    except OSError:
        raise ValueError('invalid image')

    for width, height in (LARGE_SIZE, SMALL_SIZE):
        if img.width >= width and img.height >= height:
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

    return await _upload(upload_path, main_stream.getvalue(), thumb_stream.getvalue(), settings)


async def upload_logo(image_data: bytes, upload_path: Path, settings: Settings) -> str:
    try:
        img = Image.open(BytesIO(image_data))
    except OSError:
        raise ValueError('invalid image')

    width, height = LOGO_SIZE
    if img.width < width or img.height < height:
        raise ValueError(f'image too small: {img.size}')

    aspect_ratio = img.width / img.height
    if aspect_ratio > 1:
        # wide image
        resize_to = int(round(height * aspect_ratio)), height
    else:
        # tall image
        resize_to = width, int(round(width / aspect_ratio))

    img = img.resize(resize_to, Image.ANTIALIAS)
    stream = BytesIO()
    img.save(stream, 'JPEG', optimize=True, quality=95)
    return await _upload(upload_path, stream.getvalue(), None, settings)
