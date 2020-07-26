#!/usr/bin/env python3
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
    return json_response(root_data)


event_data = {
    'event': {
        'allow_marketing_message': None,
        'booking_trust_message': None,
        'category_content': None,
        'allow_tickets': True,
        'allow_donations': False,
        'cover_costs_message': None,
        'cover_costs_percentage': None,
        'duration': 7200,
        'host_id': 1,
        'host_name': 'Frank Spencer',
        'id': 1,
        'image': 'http://www.example.com/img.png',
        'location': {
            'lat': 51.479415,
            'lng': -0.132098,
            'name': '31 Testing Road, London'
        },
        'long_description': 'Sit quisquam quisquam eius sed tempora.',
        'name': "Frank's Great Supper",
        'short_description': 'Quisquam quiquia voluptatem dolor ipsum...',
        'start_ts': '2020-01-28T19:00:00',
        'stripe_key': 'pk_test_foobar',
        'terms_and_conditions_message': None,
        'ticket_extra_help_text': 'This is the help text for this field, tell us about your nut allergy',
        'ticket_extra_title': 'Dietary Requirements & Extra Information',
        'tickets_available': None
    },
    'ticket_types': [
        {
            'name': 'Standard',
            'price': 30.0
        }
    ]
}


async def event(request):
    assert request.match_info['category'] == 'foo'
    assert request.match_info['event'] == 'bar'
    return json_response(event_data)


async def on_prepare(request, response):
    response.headers['Access-Control-Allow-Origin'] = '*'


app = web.Application()
app.on_response_prepare.append(on_prepare)
app.add_routes([
    web.get('/api/', root),
    web.get('/api/events/{category}/{event}/', event),
])

hdlr = logging.StreamHandler()
hdlr.setLevel(logging.INFO)
hdlr.setFormatter(logging.Formatter(fmt='%(message)s', datefmt='%H:%M:%S'))
logger = logging.getLogger('aiohttp')
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)

web.run_app(app, port=8000, print=lambda x: None)
