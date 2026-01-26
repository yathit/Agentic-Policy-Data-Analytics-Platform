"""
Runs API endpoints.
"""

import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Run, RunStatus, Plan, Event, Artifact
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


def _run_to_response(run: Run) -> RunResponse:
    """Convert Run model to RunResponse."""
    return RunResponse(
        id=run.id,
        query=run.query,
        status=run.status.value if isinstance(run.status, RunStatus) else run.status,
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


def _generate_plan_steps(query: str, constraints: dict) -> list:
    """Generate plan steps based on the query (stub implementation)."""
    sources = constraints.get("sources_allowlist", ["data_gov_sg", "singstat"]) if constraints else ["data_gov_sg", "singstat"]

    return [
        {
            "id": str(uuid.uuid4()),
            "agent": "coordinator",
            "action": "select_sources",
            "inputs": {"candidates": sources},
            "requires_approval": True,
        },
        {
            "id": str(uuid.uuid4()),
            "agent": "extraction",
            "action": "fetch_datasets",
            "inputs": {"sources": sources},
            "requires_approval": False,
        },
        {
            "id": str(uuid.uuid4()),
            "agent": "analytics",
            "action": "compute_trends",
            "inputs": {"metrics": ["employment", "yoy_change"]},
            "requires_approval": False,
        },
    ]


def _generate_source_rationale(sources: list) -> list:
    """Generate source rationale (stub implementation)."""
    rationale_map = {
        "data_gov_sg": "Demo-friendly stable endpoints",
        "singstat": "Format diversity (csv/excel)",
        "internal_mock": "Internal testing data",
    }
    return [
        {"source": s, "why": rationale_map.get(s, "Selected based on query requirements")}
        for s in sources
    ]


# ============================================================================
# Health Endpoint
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# ============================================================================
# Runs Endpoints
# ============================================================================

@router.post("/runs", response_model=CreateRunResponse, status_code=201)
async def create_run(
    request: CreateRunRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new run with a proposed plan.
    The run will be in 'awaiting_approval' status until approved.
    """
    # Create the run
    run = Run(
        query=request.query,
        constraints=request.constraints.model_dump() if request.constraints else None,
        status=RunStatus.AWAITING_APPROVAL,
    )
    db.add(run)
    db.flush()

    # Generate plan steps
    constraints_dict = request.constraints.model_dump() if request.constraints else {}
    steps = _generate_plan_steps(request.query, constraints_dict)
    sources = constraints_dict.get("sources_allowlist", ["data_gov_sg", "singstat"])

    # Create the plan
    plan = Plan(
        run_id=run.id,
        version=1,
        steps=steps,
        source_rationale=_generate_source_rationale(sources),
    )
    db.add(plan)
    db.commit()
    db.refresh(run)
    db.refresh(plan)

    return CreateRunResponse(
        run=_run_to_response(run),
        plan=_plan_to_response(plan),
    )


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    db: Session = Depends(get_db),
):
    """Get a run by ID."""
    run = _get_run_or_404(db, run_id)
    return _run_to_response(run)


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """List runs with cursor-based pagination."""
    query = db.query(Run).order_by(Run.created_at.desc())

    # Apply cursor if provided
    if cursor:
        try:
            cursor_time = datetime.fromisoformat(cursor)
            query = query.filter(Run.created_at < cursor_time)
        except ValueError:
            raise ValidationException("Invalid cursor format")

    # Fetch one more than limit to determine if there are more results
    runs = query.limit(limit + 1).all()

    # Determine next cursor
    next_cursor = None
    if len(runs) > limit:
        runs = runs[:limit]
        next_cursor = runs[-1].created_at.isoformat()

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
                    dataset_id=uuid.UUID(c["dataset_id"]) if c.get("dataset_id") else None,
                    source=c.get("source", ""),
                    columns=c.get("columns", []),
                )
                for c in insight.get("citations", [])
            ]
            insights.append(InsightResponse(
                headline=insight.get("headline", ""),
                evidence=evidence,
                policy_implication=insight.get("policy_implication"),
                citations=citations,
                confidence=insight.get("confidence", 0.0),
            ))

    return ArtifactsResponse(
        tables=tables,
        charts=charts,
        insights=insights,
        report_md=artifact.report_md,
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
