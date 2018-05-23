import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from arq import RedisSettings
from pydantic import BaseSettings, validator

THIS_DIR = Path(__file__).parent
BASE_DIR = THIS_DIR.parent


class Settings(BaseSettings):
    pg_dsn: str = 'postgres://postgres:waffle@localhost:5432/events'
    pg_name: str = None
    redis_settings: Any = 'redis://localhost:6379/0'
    google_siw_client_key = 'xxx'
    auth_key = b'v7RI7qwZB7rxCyrpX4QwpZCUCF7X_HtnMSFuJfZTmfs='
    port: int = 8000
    on_docker: bool = False
    on_heroku: bool = False

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
            database=int(conf.path.lstrip('/')),
            password=conf.password
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
            'redis_settings': 'REDIS_URL',
        }
