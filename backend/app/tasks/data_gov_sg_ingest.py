"""
Celery task for data.gov.sg collections ingest with advisory locking.
"""

import logging

from sqlalchemy import text

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.workers.data_gov_sg_collections import run_data_gov_sg_collections_ingest

logger = logging.getLogger(__name__)

# Postgres advisory lock ID for data.gov.sg ingest (arbitrary unique int)
INGEST_ADVISORY_LOCK_ID = 8675309


def _try_advisory_lock(db) -> bool:
    """
    Try to acquire a Postgres advisory lock (non-blocking).

    Returns True if lock acquired, False if another process holds it.
    """
    result = db.execute(
        text("SELECT pg_try_advisory_lock(:lock_id)"),
        {"lock_id": INGEST_ADVISORY_LOCK_ID},
    )
    return result.scalar()


def _release_advisory_lock(db) -> None:
    """Release the Postgres advisory lock."""
    db.execute(
        text("SELECT pg_advisory_unlock(:lock_id)"),
        {"lock_id": INGEST_ADVISORY_LOCK_ID},
    )


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def run_data_gov_sg_collections_ingest_task(self):
    """
    Celery task wrapper for data.gov.sg collections ingest.

    Uses Postgres advisory lock to prevent concurrent runs across workers.
    """
    db = SessionLocal()

    try:
        # Try to acquire advisory lock
        if not _try_advisory_lock(db):
            logger.info("data.gov.sg ingest already running (advisory lock held), skipping")
            return {"status": "skipped", "reason": "concurrent_run"}

        logger.info("Starting data.gov.sg collections ingest")

        try:
            result = run_data_gov_sg_collections_ingest()

            logger.info(
                "data.gov.sg ingest completed: pages=%d, seen=%d, inserted=%d, skipped=%d",
                result["pages_fetched"],
                result["collections_seen"],
                result["rows_inserted"],
                result["skipped"],
            )

            if result["errors"]:
                logger.warning("Ingest errors: %s", result["errors"])

            return {
                "status": "completed",
                "pages_fetched": result["pages_fetched"],
                "collections_seen": result["collections_seen"],
                "rows_inserted": result["rows_inserted"],
                "skipped": result["skipped"],
                "errors": result["errors"],
            }

        except Exception as e:
            logger.exception("data.gov.sg ingest failed: %s", e)
            raise self.retry(exc=e)

        finally:
            _release_advisory_lock(db)

    finally:
        db.close()
