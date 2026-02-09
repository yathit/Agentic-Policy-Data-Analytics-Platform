"""
Runs API endpoints.
"""

import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Run, RunStatus, Plan, Event, Artifact, Dataset, RunDatasetSnapshot
from app.utils.sources import normalize_sources
from app.schemas.run import (
    CreateRunRequest,
    CreateRunResponse,
    ApproveRunRequest,
    ApproveRunResponse,
    AbortRunResponse,
    RunResponse,
    RunListResponse,
    RunListItem,
    PlanResponse,
    PlanStepResponse,
    SourceRationale,
    EventResponse,
    EventListResponse,
    ArtifactsResponse,
    TableData,
    ChartData,
    InsightResponse,
    Evidence,
    Citation,
    DatasetInfo,
    RunDatasetSnapshotResponse,
)
from app.api.errors import NotFoundError, ConflictError, ValidationException

router = APIRouter(prefix="/api/v1", tags=["runs"])


def _get_run_or_404(db: Session, run_id: str) -> Run:
    """Get a run by ID or raise 404."""
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise NotFoundError("Run", run_id)

    run = db.query(Run).filter(Run.id == run_uuid).first()
    if not run:
        raise NotFoundError("Run", run_id)
    return run


def _run_to_response(run: Run, include_plan: bool = False) -> RunResponse:
    """Convert Run model to RunResponse."""
    return RunResponse(
        id=run.id,
        query=run.query,
        status=run.status.value if isinstance(run.status, RunStatus) else run.status,
        plan=_plan_to_response(run.plan) if include_plan and run.plan else None,
        constraints=run.constraints,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        selected_sources=run.selected_sources,
        llm_provider_used=run.llm_provider_used,
        error_summary=run.error_summary,
    )


def _plan_to_response(plan: Plan) -> PlanResponse:
    """Convert Plan model to PlanResponse."""
    steps = []
    for step in plan.steps or []:
        steps.append(PlanStepResponse(
            id=uuid.UUID(step.get("id", str(uuid.uuid4()))),
            agent=step.get("agent", "coordinator"),
            action=step.get("action", ""),
            inputs=step.get("inputs", {}),
            requires_approval=step.get("requires_approval", False),
        ))

    rationale = None
    if plan.source_rationale:
        rationale = [
            SourceRationale(source=r.get("source", ""), why=r.get("why", ""))
            for r in plan.source_rationale
        ]

    return PlanResponse(
        id=plan.id,
        version=plan.version,
        steps=steps,
        source_rationale=rationale,
    )


def _event_to_response(event: Event) -> EventResponse:
    """Convert Event model to EventResponse."""
    return EventResponse(
        id=event.id,
        run_id=event.run_id,
        agent=event.agent,
        phase=event.phase,
        message=event.message,
        payload=event.payload or {},
        ts=event.ts,
    )


# ============================================================================
# Health Endpoint
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# ============================================================================
# Sources Endpoint
# ============================================================================

@router.get("/sources")
async def list_sources():
    """List available data sources."""
    return [
        {"id": "data.gov.sg", "name": "Data.gov.sg", "recommended": True},
        {"id": "singstat", "name": "SingStat Data", "recommended": True},
        {"id": "internal", "name": "IMDA Internal", "recommended": False},
    ]


# ============================================================================
# Runs Endpoints
# ============================================================================

@router.post("/runs", response_model=CreateRunResponse, status_code=201)
async def create_run(
    request: CreateRunRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new run and trigger background plan generation.

    Returns immediately with run_id in 'planning' status.
    Plan generation happens asynchronously, emitting progress events.
    Status transitions: planning -> awaiting_approval (or failed).
    """
    constraints_dict = request.constraints.model_dump() if request.constraints else {}

    # Create the run with planning status (returns immediately)
    run = Run(
        query=request.query,
        constraints=constraints_dict or None,
        status=RunStatus.PLANNING,
        selected_sources=normalize_sources(
            request.requested_sources
            or constraints_dict.get("sources_allowlist")
        ),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Trigger background plan generation task
    try:
        from app.tasks.pipeline import generate_plan
        generate_plan.delay(
            str(run.id),
            request.query,
            constraints_dict,
            request.requested_sources or [],
        )
    except Exception as e:
        # If task queuing fails (e.g., Celery/Redis not available), mark run as failed
        run.status = RunStatus.FAILED
        run.error_summary = f"Failed to start plan generation: {str(e)[:200]}"
        db.commit()
        db.refresh(run)

    # Return immediately with run_id (plan will be null during planning)
    return CreateRunResponse(
        run=_run_to_response(run),
        plan=None,
    )


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    db: Session = Depends(get_db),
):
    """Get a run by ID."""
    run = _get_run_or_404(db, run_id)
    return _run_to_response(run, include_plan=True)


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """List runs with cursor-based pagination."""
    from sqlalchemy import or_, and_

    # Sort by created_at desc, then by id for stable ordering
    query = db.query(Run).order_by(Run.created_at.desc(), Run.id.desc())

    # Apply cursor if provided
    if cursor:
        try:
            # Parse cursor - can be either "id" (new format) or "timestamp" (legacy)
            try:
                cursor_uuid = uuid.UUID(cursor)
                # ID-based cursor: exclude this ID and all IDs that would come before it in sort order
                # Since we sort by (created_at DESC, id DESC), we need items that come "after"
                # the cursor in that order. We use a subquery to get the cursor row's created_at.
                from sqlalchemy import select
                cursor_created_at = (
                    select(Run.created_at)
                    .where(Run.id == cursor_uuid)
                    .scalar_subquery()
                )
                # Filter for rows after the cursor: either earlier timestamp, or same timestamp but smaller ID
                query = query.filter(
                    or_(
                        Run.created_at < cursor_created_at,
                        and_(
                            Run.created_at == cursor_created_at,
                            Run.id < cursor_uuid
                        )
                    )
                )
            except ValueError:
                # Legacy cursor format (timestamp only) - for backwards compatibility
                cursor_time = datetime.fromisoformat(cursor)
                query = query.filter(Run.created_at < cursor_time)
        except (ValueError, TypeError):
            raise ValidationException("Invalid cursor format")

    # Fetch one more than limit to determine if there are more results
    runs = query.limit(limit + 1).all()

    # Determine next cursor (just use the ID)
    next_cursor = None
    if len(runs) > limit:
        runs = runs[:limit]
        last_run = runs[-1]
        next_cursor = str(last_run.id)

    items = [
        RunListItem(
            id=run.id,
            query=run.query,
            status=run.status.value if isinstance(run.status, RunStatus) else run.status,
            created_at=run.created_at,
        )
        for run in runs
    ]

    return RunListResponse(items=items, next_cursor=next_cursor)


@router.post("/runs/{run_id}/approve", response_model=ApproveRunResponse)
async def approve_run(
    run_id: str,
    request: ApproveRunRequest,
    db: Session = Depends(get_db),
):
    """Approve a plan and start execution."""
    run = _get_run_or_404(db, run_id)

    # Validate status
    if run.status != RunStatus.AWAITING_APPROVAL:
        raise ConflictError(
            f"Run is in '{run.status.value}' status and cannot be approved"
        )

    # Validate plan ID
    if not run.plan or run.plan.id != request.plan_id:
        raise NotFoundError("Plan", str(request.plan_id))

    if request.approved:
        # Update plan approval
        run.plan.approved = "true"
        run.plan.approved_at = datetime.utcnow()
        run.plan.edits = request.edits

        # Update run status
        run.status = RunStatus.QUEUED

        # Create initial event
        event = Event(
            run_id=run.id,
            agent="coordinator",
            phase="decision",
            message="Plan approved, execution queued",
            payload={"plan_id": str(run.plan.id), "approved": True},
        )
        db.add(event)

        db.commit()

        # Enqueue background task (import here to avoid circular imports)
        from app.tasks.pipeline import run_pipeline
        run_pipeline.delay(str(run.id))

    else:
        # Plan rejected
        run.plan.approved = "false"
        run.status = RunStatus.ABORTED

        event = Event(
            run_id=run.id,
            agent="coordinator",
            phase="decision",
            message="Plan rejected by user",
            payload={"plan_id": str(run.plan.id), "approved": False},
        )
        db.add(event)
        db.commit()

    db.refresh(run)
    return ApproveRunResponse(
        run_id=run.id,
        status=run.status.value,
    )


@router.post("/runs/{run_id}/abort", response_model=AbortRunResponse)
async def abort_run(
    run_id: str,
    db: Session = Depends(get_db),
):
    """Abort a run."""
    run = _get_run_or_404(db, run_id)

    # Can only abort runs that are not already completed/failed/aborted
    terminal_states = [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.ABORTED]
    if run.status in terminal_states:
        raise ConflictError(
            f"Run is in '{run.status.value}' status and cannot be aborted"
        )

    # Update status
    run.status = RunStatus.ABORTED
    run.finished_at = datetime.utcnow()

    # Create abort event
    event = Event(
        run_id=run.id,
        agent="coordinator",
        phase="decision",
        message="Run aborted by user",
        payload={"aborted_by": "user"},
    )
    db.add(event)
    db.commit()
    db.refresh(run)

    return AbortRunResponse(
        run_id=run.id,
        status=run.status.value,
    )


# ============================================================================
# Events Endpoint
# ============================================================================

@router.get("/runs/{run_id}/events", response_model=EventListResponse)
async def list_events(
    run_id: str,
    after: Optional[str] = Query(default=None, description="ISO timestamp to filter events after"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List events for a run."""
    run = _get_run_or_404(db, run_id)

    query = db.query(Event).filter(Event.run_id == run.id).order_by(Event.ts.asc())

    # Filter by timestamp if provided
    if after:
        try:
            after_time = datetime.fromisoformat(after.replace("Z", "+00:00"))
            query = query.filter(Event.ts > after_time)
        except ValueError:
            raise ValidationException("Invalid 'after' timestamp format")

    events = query.limit(limit).all()
    return EventListResponse(items=[_event_to_response(e) for e in events])


# ============================================================================
# Artifacts Endpoint
# ============================================================================

@router.get("/runs/{run_id}/artifacts", response_model=ArtifactsResponse)
async def get_artifacts(
    run_id: str,
    db: Session = Depends(get_db),
):
    """Get artifacts for a run."""
    run = _get_run_or_404(db, run_id)

    # Get artifact from database
    artifact = db.query(Artifact).filter(Artifact.run_id == run.id).first()

    if not artifact:
        # Return empty artifacts if none exist
        return ArtifactsResponse(
            tables=None,
            charts=None,
            insights=None,
            report_md=None,
        )

    # Convert stored data to response format
    tables = None
    if artifact.tables:
        tables = {
            name: TableData(columns=data.get("columns", []), rows=data.get("rows", []))
            for name, data in artifact.tables.items()
        }

    charts = None
    if artifact.charts:
        charts = {
            name: ChartData(plotly=data.get("plotly", {}))
            for name, data in artifact.charts.items()
        }

    insights = None
    dataset_ids = set()
    if artifact.insights:
        insights = []
        for insight in artifact.insights:
            evidence = [
                Evidence(
                    table=e.get("table", ""),
                    col=e.get("col", ""),
                    range=e.get("range", []),
                )
                for e in insight.get("evidence", [])
            ]
            citations = [
                Citation(
                    dataset_id=str(c["dataset_id"]) if c.get("dataset_id") is not None else None,
                    source=c.get("source", ""),
                    columns=c.get("columns", []),
                )
                for c in insight.get("citations", [])
            ]
            for citation in citations:
                if citation.dataset_id and citation.dataset_id.isdigit():
                    dataset_ids.add(int(citation.dataset_id))
            # Use stored id or generate one
            insight_id = uuid.UUID(insight["id"]) if insight.get("id") else uuid.uuid4()
            insights.append(InsightResponse(
                id=insight_id,
                headline=insight.get("headline", ""),
                evidence=evidence,
                policy_implication=insight.get("policy_implication"),
                citations=citations,
                confidence=insight.get("confidence", 0.0),
            ))

    datasets = None
    if dataset_ids:
        datasets = []
        dataset_rows = (
            db.query(Dataset)
            .filter(Dataset.id.in_(dataset_ids))
            .all()
        )
        for dataset in dataset_rows:
            provenance = dataset.provenance
            datasets.append(DatasetInfo(
                id=str(dataset.id),
                name=dataset.name,
                uri=provenance.source_uri if provenance else "",
                retrieved_at=(provenance.retrieved_at if provenance else dataset.created_at),
                record_count=dataset.row_count,
            ))

    return ArtifactsResponse(
        tables=tables,
        charts=charts,
        insights=insights,
        datasets=datasets,
        report_md=artifact.report_md,
    )


@router.get("/runs/{run_id}/datasets/{dataset_id}", response_model=RunDatasetSnapshotResponse)
async def get_run_dataset_snapshot(
    run_id: str,
    dataset_id: int,
    db: Session = Depends(get_db),
):
    """Get run-scoped dataset snapshot captured during extraction."""
    run = _get_run_or_404(db, run_id)
    snapshot = (
        db.query(RunDatasetSnapshot)
        .join(Dataset, Dataset.id == RunDatasetSnapshot.dataset_id)
        .filter(
            RunDatasetSnapshot.run_id == run.id,
            RunDatasetSnapshot.dataset_id == dataset_id,
        )
        .first()
    )
    if not snapshot:
        raise NotFoundError("RunDatasetSnapshot", f"{run_id}:{dataset_id}")

    dataset = db.query(Dataset).filter(Dataset.id == snapshot.dataset_id).first()
    dataset_name = dataset.name if dataset else f"dataset_{dataset_id}"
    source_uri = dataset.provenance.source_uri if dataset and dataset.provenance else None

    return RunDatasetSnapshotResponse(
        run_id=run.id,
        dataset_id=snapshot.dataset_id,
        dataset_name=dataset_name,
        source_uri=source_uri,
        columns=snapshot.columns or [],
        rows=snapshot.rows or [],
        total_row_count=snapshot.total_row_count,
        is_truncated=snapshot.is_truncated,
        created_at=snapshot.created_at,
    )


# ============================================================================
# Export Endpoint
# ============================================================================

@router.get("/runs/{run_id}/export")
async def export_run(
    run_id: str,
    format: str = Query(default="md", pattern="^(md|pdf)$"),
    db: Session = Depends(get_db),
):
    """Export run report in specified format."""
    run = _get_run_or_404(db, run_id)

    # Get artifact
    artifact = db.query(Artifact).filter(Artifact.run_id == run.id).first()

    if format == "md":
        # Return markdown report
        if artifact and artifact.report_md:
            return Response(
                content=artifact.report_md,
                media_type="text/markdown",
                headers={"Content-Disposition": f"attachment; filename=report_{run_id}.md"},
            )
        else:
            # Generate basic markdown if no report exists
            md_content = f"""# Analysis Report

## Query
{run.query}

## Status
{run.status.value if isinstance(run.status, RunStatus) else run.status}

## Created
{run.created_at.isoformat()}

---
*Report generated automatically*
"""
            return Response(
                content=md_content,
                media_type="text/markdown",
                headers={"Content-Disposition": f"attachment; filename=report_{run_id}.md"},
            )

    elif format == "pdf":
        # PDF export not implemented
        from app.api.errors import problem_response
        return problem_response(
            status_code=501,
            title="Not Implemented",
            detail="PDF export is not yet implemented",
            instance=f"/api/v1/runs/{run_id}/export",
        )
