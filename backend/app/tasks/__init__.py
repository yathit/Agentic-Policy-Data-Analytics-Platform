"""
Background tasks for the Policy Analytics Platform.
"""

from app.tasks.pipeline import run_pipeline

__all__ = ["run_pipeline"]
