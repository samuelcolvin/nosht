from arq import Actor, DatetimeJob
from buildpg import asyncpg

from .settings import Settings


class BaseActor(Actor):
    job_class = DatetimeJob

    def __init__(self, *, settings: Settings, pg=None, **kwargs):
        self.redis_settings = settings.redis_settings
        super().__init__(**kwargs)
        self.settings = settings
        self.pg = pg
        self.client = None

    async def startup(self):
        self.pg = self.pg or await asyncpg.create_pool_b(dsn=self.settings.pg_dsn, min_size=2)

    async def shutdown(self):
        if self.client:
            await self.client.close()
        await self.pg.close()
