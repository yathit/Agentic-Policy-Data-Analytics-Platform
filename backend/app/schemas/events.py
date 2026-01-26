"""
Event schema for ReAct tracing and agent communication.
All agent actions emit structured events for observability and replay.
"""

from enum import Enum
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class EventPhase(str, Enum):
    """ReAct event phases."""

    REASON = "reason"
    ACTION = "action"
    OBSERVATION = "observation"
    DECISION = "decision"


class AgentType(str, Enum):
    """Agent types in the system."""

    COORDINATOR = "coordinator"
    EXTRACTION = "extraction"
    ANALYTICS = "analytics"
    REPORT = "report"


class AgentEvent(BaseModel):
    """
    Structured event for agent actions following ReAct pattern.

    Every agent action emits events with:
    - reason: Why taking this action
    - action: What is being done
    - observation: What was learned
    - decision: What to do next
    """

    run_id: str = Field(..., description="Unique run identifier")
    agent: AgentType = Field(..., description="Agent that emitted this event")
    phase: EventPhase = Field(..., description="ReAct phase")
    message: str = Field(..., description="Human-readable event message")
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Structured event data"
    )
    ts: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
                "agent": "coordinator",
                "phase": "reason",
                "message": "Need to identify relevant datasets for tech sector employment",
                "payload": {
                    "query": "tech sector employment trends",
                    "intent": "time_series_analysis",
                },
                "ts": "2024-01-25T10:30:00Z",
            }
        }


class EventStore:
    """
    In-memory event store for persisting and streaming agent events.
    In production, this would be backed by a database or message queue.
    """

    def __init__(self):
        self._events: Dict[str, list[AgentEvent]] = {}

    def emit(self, event: AgentEvent) -> None:
        """
        Emit an event to the store.

        Args:
            event: AgentEvent to store
        """
        if event.run_id not in self._events:
            self._events[event.run_id] = []
        self._events[event.run_id].append(event)

    def get_events(
        self,
        run_id: str,
        agent: Optional[AgentType] = None,
        phase: Optional[EventPhase] = None,
    ) -> list[AgentEvent]:
        """
        Retrieve events for a run, optionally filtered by agent or phase.

        Args:
            run_id: Run identifier
            agent: Optional agent filter
            phase: Optional phase filter

        Returns:
            List of matching events
        """
        events = self._events.get(run_id, [])

        if agent:
            events = [e for e in events if e.agent == agent]

        if phase:
            events = [e for e in events if e.phase == phase]

        return events

    def get_all_runs(self) -> list[str]:
        """Get list of all run IDs."""
        return list(self._events.keys())

    def clear_run(self, run_id: str) -> None:
        """Clear events for a specific run."""
        if run_id in self._events:
            del self._events[run_id]


# Global event store instance
event_store = EventStore()
