from celery import Celery

from config import settings

celery_app = Celery(
    "ai_dev_platform",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["workers.pipeline_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)
