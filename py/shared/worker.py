import logging

from arq import Actor, BaseWorker, concurrent

from .settings import Settings

logger = logging.getLogger('nosht.worker')


class MainActor(Actor):
    def __init__(self, *, settings: Settings, **kwargs):
        self.settings = settings
        self.redis_settings = self.settings.redis_settings
        super().__init__(**kwargs)

    @concurrent
    async def testing(self):
        print('testing worker')


class Worker(BaseWorker):
    shadows = [MainActor]

    def __init__(self, **kwargs):  # pragma: no cover
        self.settings = Settings()
        kwargs['redis_settings'] = self.settings.redis_settings
        super().__init__(**kwargs)

    async def shadow_kwargs(self):
        kwargs = await super().shadow_kwargs()
        kwargs['settings'] = self.settings
        return kwargs
