"""
Celery application configuration.
"""

from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "policy_analytics",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Parse cron expression for data.gov.sg ingest
# Format: minute hour day_of_month month day_of_week
_cron_parts = settings.data_gov_sg_ingest_weekly_cron.split()
_ingest_schedule = crontab(
    minute=_cron_parts[0] if len(_cron_parts) > 0 else "0",
    hour=_cron_parts[1] if len(_cron_parts) > 1 else "2",
    day_of_month=_cron_parts[2] if len(_cron_parts) > 2 else "*",
    month_of_year=_cron_parts[3] if len(_cron_parts) > 3 else "*",
    day_of_week=_cron_parts[4] if len(_cron_parts) > 4 else "0",
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.data_gov_sg_ingest_tz,
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    beat_schedule={
        "data-gov-sg-collections-weekly": {
            "task": "app.tasks.data_gov_sg_ingest.run_data_gov_sg_collections_ingest_task",
            "schedule": _ingest_schedule,
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])
