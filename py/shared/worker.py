import logging
from pathlib import Path

from arq import Actor, BaseWorker, concurrent

from .images import resize_upload
from .settings import Settings

logger = logging.getLogger('nosht.worker')


class MainActor(Actor):
    def __init__(self, *, settings: Settings=None, **kwargs):
        self.settings = settings or Settings()
        self.redis_settings = self.settings.redis_settings
        super().__init__(**kwargs)

    @concurrent
    async def resize_upload_image(self, image_path, upload_path):
        await resize_upload(Path(image_path), Path(upload_path), self.settings)


class Worker(BaseWorker):
    shadows = [MainActor]

    def __init__(self, **kwargs):  # pragma: no cover
        kwargs['redis_settings'] = Settings().redis_settings
        super().__init__(**kwargs)
