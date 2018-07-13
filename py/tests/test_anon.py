from pytest_toolbox.comparison import RegexStr

from .conftest import Factory


async def test_root(cli, url, factory: Factory):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(highlight=True, status='published', location_name='Testing Location')
    r = await cli.get(url('index'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'categories': [
            {
                'id': factory.category_id,
                'name': 'Supper Clubs',
                'slug': 'supper-clubs',
                'image': 'https://www.example.com/co.png',
                'description': None,
            },
        ],
        'highlight_events': [
            {
                'id': factory.event_id,
                'name': 'The Event Name',
                'cat_slug': 'supper-clubs',
                'slug': 'the-event-name',
                'image': None,
                'short_description': RegexStr('.*'),
                'location_name': 'Testing Location',
                'start_ts': '2020-01-28T19:00:00',
                'duration': None,
            },
        ],
        'company': {
            'id': factory.company_id,
            'name': 'Testing',
            'image': 'https://www.example.com/co.png',
        },
        'user': None,
    }
