#!/usr/bin/env python3
import asyncio
import locale
import logging.config
import sys

import uvloop
from aiohttp import web
from arq import RunWorkerProcess

from shared.db import reset_database, run_patch
from shared.logs import setup_logging
from shared.settings import Settings

logger = logging.getLogger('nosht.run')


def main():
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logging_client = setup_logging()
    try:
        locale.setlocale(locale.LC_ALL, 'en_GB.utf8')
    except locale.Error:
        pass
    try:
        settings = Settings()
        try:
            _, command, *args = sys.argv
        except ValueError:
            logger.info('no command provided, options are: "reset_database", "patch", "worker" or "web"')
            return 1

        if command == 'reset_database':
            logger.info('running reset_database...')
            reset_database(settings)
        elif command == 'patch':
            logger.info('running patch...')
            live = '--live' in args
            if live:
                args.remove('--live')
            return run_patch(settings, live, args[0] if args else None)
        elif command == 'web':
            logger.info('running web server...')
            from web.main import create_app

            app = create_app(settings=settings)
            web.run_app(app, port=settings.port, shutdown_timeout=6, access_log=None, print=lambda *args: None)
        elif command == 'worker':
            logger.info('running worker...')
            RunWorkerProcess('shared/worker.py', 'Worker')
        else:
            logger.error(f'unknown command "{command}"')
            return 1
    finally:
        loop = asyncio.get_event_loop()
        if logging_client and not loop.is_closed():
            transport = logging_client.remote.get_transport()
            transport and loop.run_until_complete(transport.close())


if __name__ == '__main__':
    sys.exit(main() or 0)
