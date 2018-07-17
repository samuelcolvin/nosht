import os
from pathlib import Path
from urllib.parse import urlparse

from arq import RedisSettings
from google.oauth2.id_token import _GOOGLE_OAUTH2_CERTS_URL
from pydantic import BaseSettings, conint, validator

THIS_DIR = Path(__file__).parent
BASE_DIR = THIS_DIR.parent


class Settings(BaseSettings):
    pg_dsn: str = 'postgres://postgres:waffle@localhost:5432/nosht'
    pg_name: str = None
    redis_settings: RedisSettings = 'redis://localhost:6379'
    redis_db: int = 1
    auth_key = 'v7RI7qwZB7rxCyrpX4QwpZCUCF7X_HtnMSFuJfZTmfs='
    cookie_max_age = 25 * 3600
    cookie_update_age = 600
    port: int = 8000
    on_docker: bool = False
    on_heroku: bool = False
    min_password_length: conint(gt=5) = 7
    bcrypt_work_factor = 12
    # used for hashing when the user in the db has no password
    dummy_password = '_dummy_password_'

    max_request_size = 10*1024**2  # 10MB

    aws_access_key: str = None
    aws_secret_key: str = None
    s3_bucket: str = None
    s3_domain: str = None
    aws_region: str = 'eu-west-1'
    # set here so they can be overridden during tests
    aws_ses_host = 'email.{region}.amazonaws.com'
    aws_ses_endpoint = 'https://{host}/'

    google_siw_client_key = '315422204069-no6540693ciica79g07rs43v705d348g.apps.googleusercontent.com'
    google_siw_url = _GOOGLE_OAUTH2_CERTS_URL

    facebook_siw_app_secret: bytes = b'b9c0c236dfbdab904e7101560328f0e3'
    facebook_siw_url = 'https://graph.facebook.com/v3.0/me'

    grecaptcha_url = 'https://www.google.com/recaptcha/api/siteverify'
    grecaptcha_secret = 'xxx'
    grecaptcha_threshold = 0.5

    google_maps_static_key = 'AIzaSyBu9cMA2IpeeIDRu5gu54n2-BZ_fGon4P4'

    stripe_root = 'https://api.stripe.com/v1/'
    stripe_idempotency_extra = ''

    default_email_address: str = 'Nosht <nosht@scolvin.com>'

    ticket_ttl = 300

    @validator('on_heroku', always=True)
    def set_on_heroku(cls, v):
        return v or 'DYNO' in os.environ

    @validator('pg_name', always=True, pre=True)
    def set_pg_name(cls, v, values, **kwargs):
        return urlparse(values['pg_dsn']).path.lstrip('/')

    @validator('redis_settings', always=True, pre=True)
    def parse_redis_settings(cls, v):
        conf = urlparse(v)
        return RedisSettings(
            host=conf.hostname,
            port=conf.port,
            password=conf.password,
            database=int((conf.path or '0').strip('/')),
        )

    @property
    def models_sql(self):
        return (THIS_DIR / 'sql' / 'models.sql').read_text()

    @property
    def logic_sql(self):
        return (THIS_DIR / 'sql' / 'logic.sql').read_text()

    class Config:
        fields = {
            'port': 'PORT',
            'pg_dsn': 'DATABASE_URL',
            'redis_settings': 'REDISCLOUD_URL',
        }
        arbitrary_types_allowed = True
