"""
Background tasks for the Policy Analytics Platform.
"""

from app.tasks.pipeline import run_pipeline
from app.tasks.data_gov_sg_ingest import run_data_gov_sg_collections_ingest_task

__all__ = ["run_pipeline", "run_data_gov_sg_collections_ingest_task"]
