#!/usr/bin/env python3.6
import logging

from aiohttp import web
from aiohttp.web_response import json_response

root_data = {
    'categories': [
        {
            'id': 1,
            'name': 'Supper Clubs',
            'slug': 'supper-clubs',
            'image': 'https://nosht.example.com/testing-co/supper-clubs/option/MAttgVi2dE',
            'description': 'Eat, drink & discuss middle aged, middle class things ',
        },
        {
            'id': 2,
            'name': 'Singing Events',
            'slug': 'singing-events',
            'image': 'https://nosht.example.com/testing-co/singing-events/option/PxMDn0d2b2',
            'description': 'Sing loudly and badly in the company of other people too polite to comment',
        },
    ],
    'highlight_events': [
        {
            'id': 1,
            'name': "Frank's Great Supper",
            'cat_slug': 'supper-clubs',
            'slug': 'franks-great-supper',
            'image': 'https://nosht.example.com/testing-co/supper-clubs/franks-great-supper/eI23ipV2lp',
            'short_description': 'Tempora modi magnam velit.',
            'start_ts': '2020-01-28T19:00:00',
            'location_name': '31 Testing Road, London',
            'duration': 7200,
        },
    ],
    'company': {
        'id': 1,
        'name': 'Testing Company',
        'image': 'https://nosht.example.com/testing-co/co/image/h5OIsMh7fs',
        'currency': 'gbp',
    },
    'user': None,
}


async def root(request):
    return json_response(root_data, headers={'Access-Control-Allow-Origin': '*'})

app = web.Application()
app.add_routes([
    web.get('/api/', root),
])

hdlr = logging.StreamHandler()
hdlr.setLevel(logging.INFO)
hdlr.setFormatter(logging.Formatter(fmt='%(message)s', datefmt='%H:%M:%S'))
logger = logging.getLogger('aiohttp')
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)

web.run_app(app, port=8000, print=lambda x: None)
