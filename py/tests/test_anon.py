

async def test_root(cli, create_demo_data):
    r = await cli.get('/api/')
    assert r.status == 200
