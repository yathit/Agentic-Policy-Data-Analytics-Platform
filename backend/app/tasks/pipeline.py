"""
Background task for running the analytics pipeline.
"""

import uuid
from datetime import datetime
from typing import Optional

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import Run, RunStatus, Event, Artifact


def emit_event(
    db,
    run_id: uuid.UUID,
    agent: str,
    phase: str,
    message: str,
    payload: Optional[dict] = None,
) -> Event:
    """Create and persist an event."""
    event = Event(
        run_id=run_id,
        agent=agent,
        phase=phase,
        message=message,
        payload=payload or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@celery_app.task(bind=True, max_retries=3)
def run_pipeline(self, run_id: str):
    """
    Execute the analytics pipeline for a run.

    This is a stub implementation that:
    1. Updates run status to running
    2. Emits events for each phase
    3. Creates stub artifacts
    4. Marks run as completed

    In production, this would call the actual agent pipeline.
    """
    db = SessionLocal()

    try:
        run_uuid = uuid.UUID(run_id)
        run = db.query(Run).filter(Run.id == run_uuid).first()

        if not run:
            raise ValueError(f"Run {run_id} not found")

        # Check if run was aborted before starting
        if run.status == RunStatus.ABORTED:
            return {"status": "aborted", "run_id": run_id}

        # Transition to running
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        run.llm_provider_used = "openai"  # Stub
        db.commit()

        # Emit started event
        emit_event(
            db,
            run_uuid,
            agent="coordinator",
            phase="decision",
            message="Execution started",
            payload={"status": "running"},
        )

        # Check for abort between steps
        def check_abort():
            db.refresh(run)
            return run.status == RunStatus.ABORTED

        # === COORDINATOR PHASE ===
        emit_event(
            db,
            run_uuid,
            agent="coordinator",
            phase="reason",
            message="Analyzing query intent and selecting data sources",
            payload={"query": run.query},
        )

        if check_abort():
            return {"status": "aborted", "run_id": run_id}

        emit_event(
            db,
            run_uuid,
            agent="coordinator",
            phase="action",
            message="Selecting sources based on query requirements",
            payload={"candidates": ["data_gov_sg", "singstat"]},
        )

        # Use user-selected sources or fall back to defaults
        sources = run.selected_sources or ["data_gov_sg", "singstat"]

        emit_event(
            db,
            run_uuid,
            agent="coordinator",
            phase="observation",
            message="Sources selected successfully",
            payload={"selected": sources},
        )

        # Update selected sources if not already set
        if not run.selected_sources:
            run.selected_sources = sources
        db.commit()

        # === EXTRACTION PHASE ===
        if check_abort():
            return {"status": "aborted", "run_id": run_id}

        emit_event(
            db,
            run_uuid,
            agent="extraction",
            phase="reason",
            message="Need to fetch datasets from selected sources",
            payload={"sources": run.selected_sources},
        )

        emit_event(
            db,
            run_uuid,
            agent="extraction",
            phase="action",
            message="Fetching datasets from data.gov.sg",
            payload={"source": "data_gov_sg", "endpoint": "/api/v2/datasets"},
        )

        emit_event(
            db,
            run_uuid,
            agent="extraction",
            phase="observation",
            message="Datasets fetched successfully",
            payload={
                "datasets_count": 2,
                "rows_total": 1000,
            },
        )

        if check_abort():
            return {"status": "aborted", "run_id": run_id}

        emit_event(
            db,
            run_uuid,
            agent="extraction",
            phase="action",
            message="Fetching datasets from SingStat",
            payload={"source": "singstat", "endpoint": "/tabledata"},
        )

        emit_event(
            db,
            run_uuid,
            agent="extraction",
            phase="observation",
            message="SingStat data fetched",
            payload={
                "datasets_count": 1,
                "format": "csv",
            },
        )

        # === ANALYTICS PHASE ===
        if check_abort():
            return {"status": "aborted", "run_id": run_id}

        emit_event(
            db,
            run_uuid,
            agent="analytics",
            phase="reason",
            message="Computing trend analysis on fetched data",
            payload={"metrics": ["employment", "yoy_change"]},
        )

        emit_event(
            db,
            run_uuid,
            agent="analytics",
            phase="action",
            message="Calculating employment trends",
            payload={"operation": "time_series_analysis"},
        )

        emit_event(
            db,
            run_uuid,
            agent="analytics",
            phase="observation",
            message="Trend analysis completed",
            payload={
                "trend": "increasing",
                "yoy_change": 5.2,
            },
        )

        # === REPORT PHASE ===
        if check_abort():
            return {"status": "aborted", "run_id": run_id}

        emit_event(
            db,
            run_uuid,
            agent="report",
            phase="reason",
            message="Generating report from analysis results",
            payload={"format": "markdown"},
        )

        emit_event(
            db,
            run_uuid,
            agent="report",
            phase="action",
            message="Rendering charts and tables",
            payload={"charts": 1, "tables": 1},
        )

        # Create artifacts
        artifact = Artifact(
            run_id=run_uuid,
            tables={
                "employment_trend": {
                    "columns": ["date", "value"],
                    "rows": [
                        ["2020-01-01", 1234],
                        ["2021-01-01", 1300],
                        ["2022-01-01", 1380],
                        ["2023-01-01", 1450],
                        ["2024-01-01", 1520],
                    ],
                }
            },
            charts={
                "employment_line": {
                    "plotly": {
                        "data": [
                            {
                                "type": "scatter",
                                "mode": "lines+markers",
                                "x": ["2020", "2021", "2022", "2023", "2024"],
                                "y": [1234, 1300, 1380, 1450, 1520],
                                "name": "Employment",
                            }
                        ],
                        "layout": {
                            "title": "Tech Sector Employment Trend",
                            "xaxis": {"title": "Year"},
                            "yaxis": {"title": "Employees"},
                        },
                    }
                }
            },
            insights=[
                {
                    "headline": "Tech employment rose steadily 2020-2024",
                    "evidence": [
                        {
                            "table": "employment_trend",
                            "col": "value",
                            "range": ["2020-01-01", "2024-01-01"],
                        }
                    ],
                    "policy_implication": "Consider sustaining skills pipeline initiatives.",
                    "citations": [
                        {
                            "dataset_id": None,
                            "source": "data_gov_sg",
                            "columns": ["date", "value"],
                        }
                    ],
                    "confidence": 0.78,
                }
            ],
            report_md=f"""# Analysis Report

## Query
{run.query}

## Summary
Analysis of employment trends in the technology sector from 2020 to 2024.

## Key Findings

### Employment Growth
Tech sector employment has shown consistent growth over the analysis period:
- 2020: 1,234 employees
- 2024: 1,520 employees
- Overall growth: 23.2%

### Trend Analysis
The employment trend shows a steady increase year-over-year, with an average annual growth rate of approximately 5.2%.

## Policy Implications
- Consider sustaining skills pipeline initiatives
- Monitor workforce development programs in the tech sector

## Data Sources
- data.gov.sg
- SingStat

---
*Report generated automatically by the Policy Analytics Platform*
""",
        )
        db.add(artifact)
        db.commit()

        emit_event(
            db,
            run_uuid,
            agent="report",
            phase="observation",
            message="Report generated successfully",
            payload={"artifact_id": str(artifact.id)},
        )

        emit_event(
            db,
            run_uuid,
            agent="report",
            phase="decision",
            message="Pipeline completed successfully",
            payload={"status": "completed"},
        )

        # Mark run as completed
        run.status = RunStatus.COMPLETED
        run.finished_at = datetime.utcnow()
        db.commit()

        return {"status": "completed", "run_id": run_id}

    except Exception as e:
        # Mark run as failed
        try:
            run = db.query(Run).filter(Run.id == uuid.UUID(run_id)).first()
            if run:
                run.status = RunStatus.FAILED
                run.finished_at = datetime.utcnow()
                run.error_summary = str(e)[:500]  # Limit error message length
                db.commit()

                emit_event(
                    db,
                    uuid.UUID(run_id),
                    agent="coordinator",
                    phase="decision",
                    message="Pipeline failed with error",
                    payload={"error": str(e)[:200]},  # Don't expose full stack traces
                )
        except Exception:
            pass

        raise

    finally:
        db.close()
