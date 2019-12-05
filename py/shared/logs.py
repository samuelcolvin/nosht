import logging
import logging.config
import os
import sys

from raven import Client
from raven_aiohttp import AioHttpTransport


def setup_logging(disable_existing=False):
    """
    setup logging config by updating the arq logging config
    """
    verbose = '--verbose' in sys.argv
    log_level = 'DEBUG' if verbose else 'INFO'
    raven_dsn = os.getenv('RAVEN_DSN', None)
    if raven_dsn in ('', '-'):
        # thus setting an environment variable of "-" means no raven
        raven_dsn = None

    client = None
    if raven_dsn:
        client = Client(
            transport=AioHttpTransport, dsn=raven_dsn, release=os.getenv('COMMIT', None), name=os.getenv('DYNO', None),
        )
    config = {
        'version': 1,
        'disable_existing_loggers': disable_existing,
        'formatters': {'nosht.default': {'format': '%(levelname)-7s %(name)16s: %(message)s'}},
        'handlers': {
            'nosht.default': {'level': log_level, 'class': 'logging.StreamHandler', 'formatter': 'nosht.default'},
            'sentry': {'level': 'WARNING', 'class': 'raven.handlers.logging.SentryHandler', 'client': client}
            if client
            else {'level': 'WARNING', 'class': 'logging.NullHandler'},
        },
        'loggers': {
            'nosht': {'handlers': ['nosht.default', 'sentry'], 'level': log_level},
            'arq': {'handlers': ['nosht.default', 'sentry'], 'level': log_level},
        },
    }
    logging.config.dictConfig(config)
    return client
