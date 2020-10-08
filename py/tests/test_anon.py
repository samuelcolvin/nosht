import re
from datetime import datetime, timezone

from buildpg import Values
from pytest_toolbox.comparison import RegexStr

from shared.actions import ActionTypes

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
                'image': 'https://www.example.org/main.png',
                'description': None,
            },
        ],
        'highlight_events': [
            {
                'id': factory.event_id,
                'name': 'The Event Name',
                'cat_slug': 'supper-clubs',
                'slug': 'the-event-name',
                'image': 'https://www.example.org/main.png',
                'secondary_image': None,
                'short_description': RegexStr(r'.*'),
                'location_name': 'Testing Location',
                'start_ts': '2032-06-28T19:00:00',
                'duration': 3600,
                'sold_out': False,
                'allow_donations': False,
                'allow_tickets': True,
            },
        ],
        'company': {
            'id': factory.company_id,
            'name': 'Testing',
            'image': 'https://www.example.org/main.png',
            'currency': 'gbp',
            'stripe_public_key': 'stripe_key_xxx',
            'footer_links': None,
        },
        'user': None,
    }


async def test_sitemap(cli, url, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(status='published')

    await db_conn.execute_b(
        'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
        values=Values(
            company=factory.company_id,
            user_id=factory.user_id,
            type=ActionTypes.edit_event,
            event=factory.event_id,
            ts=datetime(2032, 6, 1, tzinfo=timezone.utc),
        ),
    )

    e2 = await factory.create_event(name='second event', status='published', highlight=True)

    await db_conn.execute_b(
        'INSERT INTO actions (:values__names) VALUES :values RETURNING id',
        values=Values(
            company=factory.company_id,
            user_id=factory.user_id,
            type=ActionTypes.create_event,
            event=e2,
            ts=datetime(2031, 1, 1, tzinfo=timezone.utc),
        ),
    )

    r = await cli.get(url('sitemap'))
    text = await r.text()
    assert r.status == 200, text
    assert text.startswith(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    )
    assert text.endswith('</url>\n</urlset>\n')
    lines = sorted(text.strip('\n').split('\n'))
    # debug(text, lines)
    assert lines == [
        '</urlset>',
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<url>'
        '<loc>https://127.0.0.1/</loc>'
        '<lastmod>2032-06-01</lastmod>'
        '<changefreq>daily</changefreq>'
        '<priority>1.0</priority>'
        '</url>',
        '<url>'
        '<loc>https://127.0.0.1/supper-clubs/</loc>'
        '<lastmod>2032-06-01</lastmod>'
        '<changefreq>daily</changefreq>'
        '<priority>0.9</priority>'
        '</url>',
        '<url>'
        '<loc>https://127.0.0.1/supper-clubs/second-event/</loc>'
        '<lastmod>2031-01-01</lastmod>'
        '<changefreq>daily</changefreq>'
        '<priority>0.7</priority>'
        '</url>',
        '<url><loc>https://127.0.0.1/supper-clubs/the-event-name/</loc>'
        '<lastmod>2032-06-01</lastmod>'
        '<changefreq>daily</changefreq>'
        '<priority>0.5</priority>'
        '</url>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]


async def test_sitemap_none(cli, url, factory: Factory):
    await factory.create_company()
    r = await cli.get(url('sitemap'))
    text = await r.text()
    assert r.status == 200, text
    assert re.sub(r'\d{4}-\d\d-\d\d', 'DATE', text) == (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '<url>'
        '<loc>https://127.0.0.1/</loc>'
        '<lastmod>DATE</lastmod>'
        '<changefreq>daily</changefreq>'
        '<priority>1.0</priority>'
        '</url>\n'
        '</urlset>\n'
    )


async def test_sitemap_error(cli, url, factory: Factory):
    await factory.create_company()
    r = await cli.get(url('sitemap'))
    text = await r.text()
    assert r.status == 200, text


async def test_get_company_links(cli, url, factory: Factory, db_conn):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()

    v = '[{"title": "foo", "url": "https://www.example.com", "new_tab": true}]'
    await db_conn.execute('UPDATE companies SET footer_links=$1', v)

    r = await cli.get(url('index'))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data['company']['footer_links'] == [
        {'url': 'https://www.example.com', 'title': 'foo', 'new_tab': True},
    ]
