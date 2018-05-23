import logging
import os
import sys

from raven import Client


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
    config = {
        'version': 1,
        'disable_existing_loggers': disable_existing,
        'formatters': {
            'events.default': {
                'format': '%(levelname)-7s %(name)25s: %(message)s',
            },
        },
        'handlers': {
            'events.default': {
                'level': log_level,
                'class': 'logging.StreamHandler',
                'formatter': 'events.default',
            },
            'sentry': {
                'level': 'WARNING',
                'class': 'raven.handlers.logging.SentryHandler',
                'client': Client(
                    dsn=raven_dsn,
                    release=os.getenv('COMMIT', None),
                    name=os.getenv('IMAGE_NAME', None),
                ),
            },
        },
        'loggers': {
            'events': {
                'handlers': ['events.default', 'sentry'],
                'level': log_level,
            },
            'arq': {
                'handlers': ['events.default', 'sentry'],
                'level': log_level,
            },
        },
    }
    logging.config.dictConfig(config)
