#!/usr/bin/env python3.6
import asyncio
import logging.config
import os
import sys

import uvloop
from aiohttp import web
from arq import RunWorkerProcess

from app.db import reset_database, run_patch
from app.logs import setup_logging
from app.settings import Settings
from app.main import create_app


logger = logging.getLogger('events.run')


if __name__ == '__main__':
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    setup_logging()
    settings = Settings()
    try:
        _, command, *args = sys.argv
    except ValueError:
        logger.info('no command provided, options are: "reset_database", "patch", "worker", "web" or "docker-run"')
        sys.exit(1)
    if command == 'docker-run':
        command = 'web' if 'PORT' in os.environ else 'worker'

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
        app = create_app(settings=settings)
        port = int(os.getenv('PORT', 8000))
        web.run_app(app, port=settings.port, shutdown_timeout=1, access_log=None, print=lambda *args: None)
    elif command == 'worker':
        logger.info('running worker...')
        RunWorkerProcess('app/worker.py', 'Worker')
    else:
        logger.error(f'unknown command "{command}"')
        sys.exit(1)
