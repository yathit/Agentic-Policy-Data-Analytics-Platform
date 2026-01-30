"""
Background task for running the analytics pipeline.
"""

import uuid
from datetime import datetime
from typing import Optional, Callable

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import Run, RunStatus, Event, Artifact
from app.schemas.plan import Plan as StructuredPlan, TimeRange
from app.schemas.events import AgentEvent
from app.agents.extraction import ExtractionAgent
from app.agents.analytics import AnalyticsAgent


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


def _normalize_sources(sources: Optional[list]) -> list:
    if not sources:
        return ["data.gov.sg", "singstat"]
    normalized = []
    for source in sources:
        if source in ["data_gov_sg", "data.gov.sg"]:
            normalized.append("data.gov.sg")
        elif source in ["singstat"]:
            normalized.append("singstat")
        elif source in ["internal", "mock_internal"]:
            normalized.append("internal")
        else:
            normalized.append(source)
    return normalized


def _db_event_sink(db, run_uuid: uuid.UUID) -> Callable[[AgentEvent], None]:
    def _sink(event: AgentEvent) -> None:
        agent = event.agent.value if hasattr(event.agent, "value") else event.agent
        phase = event.phase.value if hasattr(event.phase, "value") else event.phase
        emit_event(
            db,
            run_uuid,
            agent=str(agent),
            phase=str(phase),
            message=event.message,
            payload=event.payload,
        )

    return _sink


def _apply_plan_edits(plan: StructuredPlan, edits: Optional[dict]) -> StructuredPlan:
    if not edits:
        return plan

    sources = edits.get("sources")
    time_range = edits.get("time_range")

    if sources:
        allowed = set(_normalize_sources(sources))
        plan.sources = [s for s in plan.sources if s.name in allowed]
        plan.extract_steps = [s for s in plan.extract_steps if s.source in allowed]

    if time_range and time_range.get("start") and time_range.get("end"):
        plan.intent.time_range = TimeRange(
            start=time_range["start"],
            end=time_range["end"],
        )

    return plan


def _tables_from_analysis(analysis_result) -> dict:
    tables = {}
    for table in analysis_result.computed_tables:
        columns = list(table.data.keys())
        rows = []
        if columns:
            lengths = []
            for col in columns:
                col_values = table.data[col]
                if isinstance(col_values, list):
                    lengths.append(len(col_values))
                else:
                    lengths.append(1)
            row_count = max(lengths) if lengths else 0
            for idx in range(row_count):
                row = []
                for col in columns:
                    col_values = table.data[col]
                    if isinstance(col_values, list):
                        row.append(col_values[idx] if idx < len(col_values) else None)
                    else:
                        row.append(col_values if idx == 0 else None)
                rows.append(row)
        tables[table.id] = {"columns": columns, "rows": rows}
    return tables


def _charts_from_analysis(analysis_result) -> dict:
    charts = {}
    for chart in analysis_result.charts:
        charts[chart.id] = {"plotly": chart.spec}
    return charts


def _insights_from_analysis(analysis_result, datasets) -> list:
    insights = []
    default_dataset = datasets[0] if datasets else None
    table_id = analysis_result.computed_tables[0].id if analysis_result.computed_tables else "table"

    for insight in analysis_result.insights:
        evidence = insight.evidence or {}
        metric = evidence.get("metric", "value")
        year_start = evidence.get("year_start")
        year_end = evidence.get("year_end")
        citation_dataset_id = None
        if insight.citations:
            citation_dataset_id = insight.citations[0].get("dataset_id")
        if citation_dataset_id is None and default_dataset:
            citation_dataset_id = default_dataset.id

        insights.append({
            "id": str(uuid.uuid4()),
            "headline": insight.headline,
            "evidence": [
                {
                    "table": table_id,
                    "col": metric,
                    "range": [
                        str(year_start) if year_start is not None else "",
                        str(year_end) if year_end is not None else "",
                    ],
                }
            ],
            "policy_implication": insight.policy_implication,
            "citations": [
                {
                    "dataset_id": str(citation_dataset_id) if citation_dataset_id is not None else None,
                    "source": default_dataset.source_type if default_dataset else "unknown",
                    "columns": [metric],
                }
            ],
            "confidence": float(insight.confidence),
        })

    return insights


def _build_report(run: Run, analysis_result) -> str:
    lines = [
        "# Analysis Report",
        "",
        "## Query",
        run.query,
        "",
        "## Summary",
        f"{len(analysis_result.insights)} insights generated.",
        "",
        "## Insights",
    ]
    for insight in analysis_result.insights:
        lines.append(f"- {insight.headline}")
    lines.append("")
    lines.append("---")
    lines.append("*Report generated automatically by the Policy Analytics Platform*")
    return "\n".join(lines)


@celery_app.task(bind=True, max_retries=3)
def run_pipeline(self, run_id: str):
    """
    Execute the analytics pipeline for a run.

    Executes the actual ingestion + analytics pipeline using connectors/agents.
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

        if not run.plan or not run.plan.plan_json:
            raise ValueError("Structured plan not found for run")

        # Transition to running
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
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

        def check_abort():
            db.refresh(run)
            return run.status == RunStatus.ABORTED

        structured_plan = StructuredPlan.model_validate(run.plan.plan_json)
        structured_plan = _apply_plan_edits(structured_plan, run.plan.edits)
        structured_plan.approved = True

        # Early validation: Check if plan has extraction steps
        if not structured_plan.extract_steps:
            raise ValueError(
                f"No extraction steps in the plan. The coordinator could not identify relevant datasets for query: '{run.query}'. "
                f"Try rephrasing your query to include specific metrics (e.g., 'employment', 'gdp', 'population') "
                f"or entities (e.g., 'tech', 'technology', 'innovation')."
            )

        selected_sources = _normalize_sources([s.name for s in structured_plan.sources])
        run.selected_sources = selected_sources
        db.commit()

        event_sink = _db_event_sink(db, run_uuid)

        extraction_agent = ExtractionAgent(db, event_sink=event_sink)
        extraction_results = extraction_agent.run_extraction(
            run_id=str(run_uuid),
            approved_plan=structured_plan,
            abort_check=check_abort,
        )
        datasets = [r.dataset for r in extraction_results if r.success and r.dataset]

        if check_abort():
            return {"status": "aborted", "run_id": run_id}

        if not datasets:
            # Collect failure reasons from extraction results
            failure_reasons = []
            for i, result in enumerate(extraction_results):
                if not result.success and result.error:
                    step = structured_plan.extract_steps[i] if i < len(structured_plan.extract_steps) else None
                    source = step.source if step else "unknown"
                    dataset_ref = step.dataset_ref if step else "unknown"
                    failure_reasons.append(f"{source}/{dataset_ref}: {result.error}")

            if failure_reasons:
                error_details = "; ".join(failure_reasons[:3])  # Limit to 3 reasons
                if len(failure_reasons) > 3:
                    error_details += f" (+{len(failure_reasons) - 3} more)"
                raise ValueError(f"No datasets were successfully extracted. Failures: {error_details}")
            else:
                raise ValueError("No datasets were successfully extracted. No extraction steps were defined in the plan.")

        analytics_agent = AnalyticsAgent(db, event_sink=event_sink)
        analysis_result = analytics_agent.run_analysis(
            run_id=str(run_uuid),
            approved_plan=structured_plan,
            datasets=datasets,
            abort_check=check_abort,
        )

        if check_abort():
            return {"status": "aborted", "run_id": run_id}

        artifact = Artifact(
            run_id=run_uuid,
            tables=_tables_from_analysis(analysis_result),
            charts=_charts_from_analysis(analysis_result),
            insights=_insights_from_analysis(analysis_result, datasets),
            report_md=_build_report(run, analysis_result),
        )

        db.add(artifact)
        db.commit()

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
