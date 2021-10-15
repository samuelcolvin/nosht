import asyncio
from arq import BaseWorker, DatetimeJob

from .donorfy import DonorfyActor
from .emails import EmailActor
from .settings import Settings


class Worker(BaseWorker):
    job_class = DatetimeJob
    shadows = [DonorfyActor, EmailActor]

    def __init__(self, **kwargs):  # pragma: no cover
        self.settings = Settings()
        kwargs['redis_settings'] = self.settings.redis_settings
        super().__init__(**kwargs)

    async def shadow_kwargs(self):
        kwargs = await super().shadow_kwargs()
        kwargs['settings'] = self.settings
        # not sure why but the worker sometimes crashes with no explanation on start, this might help
        await asyncio.sleep(2)
        return kwargs
