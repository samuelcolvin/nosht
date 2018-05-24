#!/usr/bin/env python3.6
import asyncio
import logging.config
import os
import sys

import uvloop
from aiohttp import web
from arq import RunWorkerProcess

from shared.db import reset_database, run_patch
from shared.logs import setup_logging
from shared.settings import Settings

logger = logging.getLogger('nosht.run')


if __name__ == '__main__':
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    setup_logging()
    settings = Settings()
    try:
        _, command, *args = sys.argv
    except ValueError:
        logger.info('no command provided, options are: "reset_database", "patch", "worker" or "web"')
        sys.exit(1)

    if command == 'reset_database':
        logger.info('running reset_database...')
        reset_database(settings)
    elif command == 'patch':
        logger.info('running patch...')
        live = '--live' in args
        if live:
            args.remove('--live')
        run_patch(settings, live, args[0] if args else None)
    elif command == 'web':
        logger.info('running web server...')
        from web.main import create_app
        app = create_app(settings=settings)
        port = int(os.getenv('PORT', 8000))
        web.run_app(app, port=settings.port, shutdown_timeout=6, access_log=None, print=lambda *args: None)
    elif command == 'worker':
        logger.info('running worker...')
        RunWorkerProcess('shared/worker.py', 'Worker')
    else:
        logger.error(f'unknown command "{command}"')
        sys.exit(1)