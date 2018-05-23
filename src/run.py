#!/usr/bin/env python3.6
import asyncio
import logging.config
import os
import sys
from pathlib import Path

import uvloop
from aiohttp import web

THIS_DIR = Path(__file__).parent
if not Path(THIS_DIR / 'shared').exists():
    # when running outside docker
    sys.path.append(str(THIS_DIR / '..'))

from shared.logs import setup_logging  # NOQA
from shared.patch import reset_database, run_patch  # NOQA
from shared.settings import Settings  # NOQA
from web.main import create_app  # NOQA


logger = logging.getLogger('events.web.run')


if __name__ == '__main__':
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    setup_logging()
    settings = Settings()
    try:
        _, command, *args = sys.argv
    except ValueError:
        print('no command provided, options are: "reset_database", "patch" or "web"')
        sys.exit(1)

    if command == 'reset_database':
        print('running reset_database...')
        reset_database(settings)
    elif command == 'patch':
        print('running patch...')
        live = '--live' in args
        if live:
            args.remove('--live')
        run_patch(settings, live, args[0] if args else None)
    elif command == 'web':
        print('running web server...')
        app = create_app(settings=settings)
        port = int(os.getenv('PORT', 8000))
        web.run_app(app, port=settings.port, shutdown_timeout=1, access_log=None, print=lambda *args: None)
    else:
        print(f'unknown command "{command}"')
        sys.exit(1)
