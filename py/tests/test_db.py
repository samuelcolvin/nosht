from pytest_toolbox.comparison import RegexStr

from shared.db import create_demo_data


async def test_create_demo_data(cli, url, db_conn, settings):
    await create_demo_data(db_conn, settings, company_domain='127.0.0.1')
    r = await cli.get(url('index'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {
        'categories': [
            {
                'id': await db_conn.fetchval("SELECT id FROM categories WHERE slug='supper-clubs'"),
                'name': 'Supper Clubs',
                'slug': 'supper-clubs',
                'image': RegexStr(r'http.*'),
                'description': (
                    'Eat, drink & discuss middle aged, middle class things like house prices and consumerist guilt'
                ),
            },
            {
                'id': await db_conn.fetchval("SELECT id FROM categories WHERE slug='singing-events'"),
                'name': 'Singing Events',
                'slug': 'singing-events',
                'image': RegexStr(r'http.*'),
                'description': 'Sing loudly and badly in the company of other people too polite to comment',
            },
        ],
        'highlight_events': [
            {
                'id': await db_conn.fetchval("SELECT id FROM events WHERE slug='franks-great-supper'"),
                'name': "Frank's Great Supper",
                'cat_slug': 'supper-clubs',
                'slug': 'franks-great-supper',
                'image': RegexStr(r'http.*'),
                'secondary_image': None,
                'short_description': RegexStr(r'.*'),
                'location_name': '31 Testing Road, London',
                'start_ts': '2032-01-28T19:00:00',
                'duration': 7200,
                'sold_out': False,
                'allow_donations': False,
                'allow_tickets': True,
            },
            {
                'id': await db_conn.fetchval("SELECT id FROM events WHERE slug='janes-great-supper'"),
                'name': "Jane's Great Supper",
                'cat_slug': 'supper-clubs',
                'slug': 'janes-great-supper',
                'image': RegexStr(r'http.*'),
                'secondary_image': None,
                'short_description': RegexStr(r'.*'),
                'location_name': '253 Brixton Road, London',
                'start_ts': '2032-02-10T18:00:00',
                'duration': 10800,
                'sold_out': False,
                'allow_donations': False,
                'allow_tickets': True,
            },
            {
                'id': await db_conn.fetchval("SELECT id FROM events WHERE slug='loud-singing'"),
                'name': 'Loud Singing',
                'cat_slug': 'singing-events',
                'slug': 'loud-singing',
                'image': RegexStr(r'http.*'),
                'secondary_image': None,
                'short_description': RegexStr(r'.*'),
                'location_name': 'Big Church, London',
                'start_ts': '2032-02-15T00:00:00',
                'duration': None,
                'sold_out': False,
                'allow_donations': False,
                'allow_tickets': True,
            },
        ],
        'company': {
            'id': await db_conn.fetchval('SELECT id FROM companies'),
            'name': 'Testing Company',
            'image': RegexStr(r'http.*'),
            'currency': 'gbp',
            'stripe_public_key': 'pk_test_efpfygU2qxGIwgcjn5T5DTTI',
            'footer_links': None,
        },
        'user': None,
    }
