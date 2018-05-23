import asyncio
import os

from shared.db import lenient_conn, prepare_database

from .settings import Settings

patches = []


def reset_database(settings: Settings):
    if not (os.getenv('CONFIRM_DATABASE_RESET') == 'confirm' or input('Confirm database reset? [yN] ') == 'y'):
        print('cancelling')
    else:
        print('resetting database...')
        loop = asyncio.get_event_loop()
        loop.run_until_complete(prepare_database(settings, True))
        print('done.')


def patch(func):
    patches.append(func)
    return func


def run_patch(settings: Settings, live, patch_name):
    if patch_name is None:
        print('available patches:\n{}'.format(
            '\n'.join('  {}: {}'.format(p.__name__, p.__doc__.strip('\n ')) for p in patches)
        ))
        return
    patch_lookup = {p.__name__: p for p in patches}
    try:
        patch_func = patch_lookup[patch_name]
    except KeyError as e:
        raise RuntimeError(f'patch "{patch_name}" not found in patches: {[p.__name__ for p in patches]}') from e

    print(f'running patch {patch_name} live {live}')
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_run_patch(settings, live, patch_func))


async def _run_patch(settings, live, patch_func):
    conn = await lenient_conn(settings)
    tr = conn.transaction()
    await tr.start()
    print('=' * 40)
    try:
        await patch_func(conn, settings=settings, live=live)
    except BaseException as e:
        print('=' * 40)
        await tr.rollback()
        raise RuntimeError('error running patch, rolling back') from e
    else:
        print('=' * 40)
        if live:
            print('live, committed patch')
            await tr.commit()
        else:
            print('not live, rolling back')
            await tr.rollback()
    finally:
        await conn.close()


@patch
async def run_logic_sql(conn, settings, **kwargs):
    """
    run logic.sql code.
    """
    await conn.execute(settings.logic_sql)
