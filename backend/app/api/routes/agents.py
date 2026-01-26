"""
API endpoints for multi-agent orchestration.

Endpoints:
- POST /agents/query - Submit query and get plan
- POST /agents/approve - Approve/reject plan
- GET /agents/run/{run_id} - Get run status and results
- GET /agents/events/{run_id} - Get event trace for run
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.agents.graph import AgentOrchestrator
from app.schemas.events import event_store, AgentEvent
from app.schemas.plan import Plan, PlanApprovalRequest

router = APIRouter(prefix="/agents", tags=["agents"])


class QueryRequest(BaseModel):
    """Request to submit a new query."""

    query: str
    user_constraints: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    """Response with run ID and proposed plan."""

    run_id: str
    query: str
    plan: Dict[str, Any]
    status: str


class ApprovalResponse(BaseModel):
    """Response after plan approval."""

    run_id: str
    approved: bool
    status: str


class RunStatusResponse(BaseModel):
    """Response with run status and results."""

    run_id: str
    status: str
    plan: Optional[Dict[str, Any]]
    extraction_summary: Optional[List[Dict[str, Any]]]
    analytics: Optional[Dict[str, Any]]
    error: Optional[str]


class EventsResponse(BaseModel):
    """Response with event trace."""

    run_id: str
    events: List[Dict[str, Any]]


# In-memory storage for orchestrators (in production, use Redis or DB)
_orchestrators: Dict[str, AgentOrchestrator] = {}


def get_orchestrator(db: Session = Depends(get_db)) -> AgentOrchestrator:
    """
    Get or create orchestrator for this request.

    Args:
        db: Database session

    Returns:
        AgentOrchestrator instance
    """
    # In production, would use dependency injection or singleton
    return AgentOrchestrator(db)


@router.post("/query", response_model=QueryResponse)
async def submit_query(
    request: QueryRequest, orchestrator: AgentOrchestrator = Depends(get_orchestrator)
) -> QueryResponse:
    """
    Submit a new query for analysis.

    This endpoint:
    1. Accepts user query
    2. Runs Coordinator agent to generate plan
    3. Returns plan for user approval
    4. Stops at HITL approval gate

    Args:
        request: Query request
        orchestrator: Agent orchestrator

    Returns:
        QueryResponse with run ID and proposed plan
    """
    try:
        result = orchestrator.execute(
            query=request.query, user_constraints=request.user_constraints
        )

        return QueryResponse(
            run_id=result["run_id"],
            query=result["query"],
            plan=result["plan"].model_dump() if result["plan"] else {},
            status="awaiting_approval",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve", response_model=ApprovalResponse)
async def approve_plan(
    request: PlanApprovalRequest,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> ApprovalResponse:
    """
    Approve or reject a proposed plan.

    This endpoint:
    1. Accepts approval decision
    2. If approved, continues execution (Extraction → Analytics)
    3. Returns execution status

    Args:
        request: Approval request
        orchestrator: Agent orchestrator

    Returns:
        ApprovalResponse with execution status
    """
    try:
        # Approve plan
        orchestrator.approve_plan(request.run_id, request.approved)

        if request.approved:
            # Continue execution
            final_output = orchestrator.continue_after_approval(request.run_id)

            return ApprovalResponse(
                run_id=request.run_id, approved=True, status="completed"
            )
        else:
            return ApprovalResponse(
                run_id=request.run_id, approved=False, status="rejected"
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/run/{run_id}", response_model=RunStatusResponse)
async def get_run_status(run_id: str) -> RunStatusResponse:
    """
    Get status and results for a run.

    Args:
        run_id: Run identifier

    Returns:
        RunStatusResponse with current status and results
    """
    try:
        # Get events to determine status
        events = event_store.get_events(run_id)

        if not events:
            raise HTTPException(status_code=404, detail="Run not found")

        # Determine status from events
        has_plan = any("plan" in e.payload for e in events)
        has_approval = any(e.payload.get("approved") for e in events)
        has_extraction = any(e.agent.value == "extraction" for e in events)
        has_analytics = any(e.agent.value == "analytics" for e in events)

        if has_analytics:
            status = "completed"
        elif has_extraction:
            status = "extracting"
        elif has_approval:
            status = "approved"
        elif has_plan:
            status = "awaiting_approval"
        else:
            status = "processing"

        # Extract results from events
        plan = None
        for event in reversed(events):
            if "plan" in event.payload:
                plan = event.payload["plan"]
                break

        return RunStatusResponse(
            run_id=run_id,
            status=status,
            plan=plan,
            extraction_summary=None,  # Would extract from events
            analytics=None,  # Would extract from events
            error=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/{run_id}", response_model=EventsResponse)
async def get_events(run_id: str) -> EventsResponse:
    """
    Get full event trace for a run.

    This provides complete observability into agent decisions
    following the ReAct pattern (Reason → Action → Observation → Decision).

    Args:
        run_id: Run identifier

    Returns:
        EventsResponse with all events
    """
    try:
        events = event_store.get_events(run_id)

        if not events:
            raise HTTPException(status_code=404, detail="Run not found")

        return EventsResponse(
            run_id=run_id, events=[e.model_dump() for e in events]
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check(
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> Dict[str, Any]:
    """
    Check health of agent system and LLM providers.

    Returns:
        Health status
    """
    try:
        llm_health = orchestrator.llm_router.health_check()

        return {
            "status": "healthy",
            "llm_providers": llm_health,
            "event_store": {"runs": len(event_store.get_all_runs())},
        }

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
