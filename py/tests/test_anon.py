from .conftest import Factory


async def test_root(cli, factory: Factory):
    await factory.create_company()
    await factory.create_cat()

    r = await cli.get('/api/')
    assert r.status == 200
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
        'highlight_events': [],
        'company': {
            'id': factory.company_id,
            'name': 'Testing',
            'image': 'https://www.example.com/co.png',
        },
        'user': None,
    }
