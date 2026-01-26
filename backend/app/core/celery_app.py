"""
Celery application configuration.
"""

from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "policy_analytics",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])
