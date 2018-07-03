from pytest_toolbox.comparison import RegexStr

from shared.db import create_demo_data


async def test_create_demo_data(cli, db_conn, settings):
    await create_demo_data(db_conn, settings, company_host='127.0.0.1')
    r = await cli.get('/api/')
    assert r.status == 200
    data = await r.json()
    assert data == {
        'categories': [
            {
                'id': await db_conn.fetchval("SELECT id FROM categories WHERE slug='supper-clubs'"),
                'name': 'Supper Clubs',
                'slug': 'supper-clubs',
                'image': 'https://nosht.scolvin.com/cat/mountains/options/yQt1XLAPDm',
                'description': (
                    'Eat, drink & discuss middle aged,'
                    ' middle class things like house prices and consumerist guilt'
                ),
            },
            {
                'id': await db_conn.fetchval("SELECT id FROM categories WHERE slug='singing-events'"),
                'name': 'Singing Events',
                'slug': 'singing-events',
                'image': 'https://nosht.scolvin.com/cat/mountains/options/zwaxBXpsyu',
                'description': 'Sing loudly and badly in the company of other people too polite to comment',
            },
        ],
        'highlight_events': [
            {
                'id': await db_conn.fetchval("SELECT id FROM events WHERE slug='franks-great-supper'"),
                'name': "Frank's Great Supper",
                'cat_slug': 'supper-clubs',
                'slug': 'franks-great-supper',
                'image': 'https://nosht.scolvin.com/cat/mountains/options/yQt1XLAPDm',
                'short_description': RegexStr('.*'),
                'location': '31 Testing Road, London',
                'start_ts': '2020-01-28T19:00:00',
                'duration': 7200,
            },
            {
                'id': await db_conn.fetchval("SELECT id FROM events WHERE slug='janes-great-supper'"),
                'name': "Jane's Great Supper",
                'cat_slug': 'supper-clubs',
                'slug': 'janes-great-supper',
                'image': 'https://nosht.scolvin.com/cat/mountains/options/YEcz6kUlsc',
                'short_description': RegexStr('.*'),
                'location': '253 Brixton Road, London',
                'start_ts': '2020-02-10T18:00:00',
                'duration': 10800,
            },
            {
                'id': await db_conn.fetchval("SELECT id FROM events WHERE slug='loud-singing'"),
                'name': 'Loud Singing',
                'cat_slug': 'singing-events',
                'slug': 'loud-singing',
                'image': 'https://nosht.scolvin.com/cat/mountains/options/g3I6RDoZtE',
                'short_description': RegexStr('.*'),
                'location': 'Big Church, London',
                'start_ts': '2020-02-15T00:00:00',
                'duration': None,
            },
        ],
        'company': {
            'id': await db_conn.fetchval('SELECT id FROM companies'),
            'name': 'Testing',
            'image': 'https://nosht.scolvin.com/cat/mountains/options/3WsQ7fKy0G',
        },
        'user': None,
    }
