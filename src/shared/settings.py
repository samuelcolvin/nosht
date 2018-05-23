import os
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseSettings, validator

THIS_DIR = Path(__file__).parent
BASE_DIR = THIS_DIR.parent


class Settings(BaseSettings):
    pg_dsn: str = 'postgres://postgres:waffle@localhost:5432/events'
    pg_name: str = None
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
        }
