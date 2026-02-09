"""
Pydantic schemas for runs API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from uuid import UUID


# ============================================================================
# Request Schemas
# ============================================================================

class TimeRangeConstraint(BaseModel):
    """Time range constraint for the query."""
    start: str = Field(..., description="Start date in ISO format (YYYY-MM-DD)")
    end: str = Field(..., description="End date in ISO format (YYYY-MM-DD)")


class RunConstraints(BaseModel):
    """Constraints for run execution."""
    time_range: Optional[TimeRangeConstraint] = None
    sources_allowlist: Optional[List[str]] = Field(None, description="Allowed data sources")
    max_cost_sgd: Optional[float] = Field(None, description="Maximum cost in SGD")


class CreateRunRequest(BaseModel):
    """Request to create a new run."""
    query: str = Field(..., min_length=1, description="User query for analysis")
    constraints: Optional[RunConstraints] = None
    requested_sources: Optional[List[str]] = Field(None, description="Requested data sources")


class ApproveRunRequest(BaseModel):
    """Request to approve a plan and start execution."""
    plan_id: UUID = Field(..., description="Plan ID to approve")
    approved: bool = Field(..., description="Whether to approve the plan")
    edits: Optional[Dict[str, Any]] = Field(None, description="Optional edits to the plan")


# ============================================================================
# Response Schemas
# ============================================================================

class PlanStepResponse(BaseModel):
    """A single step in the plan."""
    id: UUID
    agent: str
    action: str
    inputs: Dict[str, Any]
    requires_approval: bool = False


class SourceRationale(BaseModel):
    """Rationale for selecting a data source."""
    source: str
    why: str


class PlanResponse(BaseModel):
    """Plan response."""
    id: UUID
    version: int
    steps: List[PlanStepResponse]
    source_rationale: Optional[List[SourceRationale]] = None


class RunResponse(BaseModel):
    """Run response."""
    id: UUID
    query: str
    status: str
    plan: Optional[PlanResponse] = None
    constraints: Optional[Dict[str, Any]] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    selected_sources: Optional[List[str]] = None
    llm_provider_used: Optional[str] = None
    error_summary: Optional[str] = None

    class Config:
        from_attributes = True


class CreateRunResponse(BaseModel):
    """Response for creating a run."""
    run: RunResponse
    plan: Optional[PlanResponse] = None  # May be null during planning status


class ApproveRunResponse(BaseModel):
    """Response after approving a run."""
    run_id: UUID
    status: str


class AbortRunResponse(BaseModel):
    """Response after aborting a run."""
    run_id: UUID
    status: str


class RunListItem(BaseModel):
    """Run item in list response."""
    id: UUID
    query: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class RunListResponse(BaseModel):
    """Paginated list of runs."""
    items: List[RunListItem]
    next_cursor: Optional[str] = None


# ============================================================================
# Event Schemas
# ============================================================================

class EventResponse(BaseModel):
    """Event response."""
    id: UUID
    run_id: UUID
    agent: str
    phase: str
    message: str
    payload: Dict[str, Any]
    ts: datetime

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """List of events for a run."""
    items: List[EventResponse]


# ============================================================================
# Artifact Schemas
# ============================================================================

class TableData(BaseModel):
    """Table artifact data."""
    columns: List[str]
    rows: List[List[Any]]


class ChartData(BaseModel):
    """Chart artifact data (Plotly format)."""
    plotly: Dict[str, Any]


class Citation(BaseModel):
    """Citation for an insight."""
    dataset_id: Optional[str] = None
    source: str
    columns: List[str]


class Evidence(BaseModel):
    """Evidence for an insight."""
    table: str
    col: str
    range: List[str]


class InsightResponse(BaseModel):
    """Insight artifact."""
    id: UUID
    headline: str
    evidence: List[Evidence]
    policy_implication: Optional[str] = None
    citations: List[Citation]
    confidence: float


class DatasetInfo(BaseModel):
    """Dataset provenance info for UI."""
    id: str
    name: str
    uri: str
    retrieved_at: datetime
    record_count: Optional[int] = None


class ArtifactsResponse(BaseModel):
    """Artifacts for a run."""
    tables: Optional[Dict[str, TableData]] = None
    charts: Optional[Dict[str, ChartData]] = None
    insights: Optional[List[InsightResponse]] = None
    datasets: Optional[List[DatasetInfo]] = None
    report_md: Optional[str] = None


class RunDatasetSnapshotResponse(BaseModel):
    """Run-scoped dataset snapshot used in execution."""
    run_id: UUID
    dataset_id: int
    dataset_name: str
    columns: List[str]
    rows: List[List[Any]]
    total_row_count: int
    is_truncated: bool
    created_at: datetime


# ============================================================================
# WebSocket Schemas
# ============================================================================

class WebSocketEventMessage(BaseModel):
    """WebSocket event message."""
    type: str = "event"
    event: EventResponse


class WebSocketSnapshotMessage(BaseModel):
    """WebSocket snapshot message sent on connection."""
    type: str = "snapshot"
    run: RunResponse
    events: List[EventResponse]


class WebSocketHeartbeatMessage(BaseModel):
    """WebSocket heartbeat message."""
    type: str = "heartbeat"
    ts: datetime


# ============================================================================
# Error Schemas (RFC7807 Problem JSON)
# ============================================================================

class ValidationErrorItem(BaseModel):
    """Single validation error."""
    loc: List[str]
    msg: str
    type: str


class ProblemResponse(BaseModel):
    """RFC7807 Problem JSON response."""
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: Optional[str] = None
    errors: Optional[List[ValidationErrorItem]] = None
