"""
Unified event handling for agents.

Provides event sink factory for persisting agent events to the database,
enabling both API and CLI to use the same event persistence mechanism.
"""

import uuid
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.models import Event
from app.schemas.events import AgentEvent


def create_db_event_sink(
    db: Session,
    run_id: uuid.UUID,
) -> Callable[[AgentEvent], None]:
    """
    Create an event sink that persists events to the database.

    This factory creates a callback function that agents can use to emit events.
    Events are immediately committed to the database for real-time visibility.

    Args:
        db: SQLAlchemy database session
        run_id: UUID of the run to associate events with

    Returns:
        Callable that accepts AgentEvent and persists to DB
    """

    def _sink(event: AgentEvent) -> None:
        # Extract enum values if needed
        agent = event.agent.value if hasattr(event.agent, "value") else str(event.agent)
        phase = event.phase.value if hasattr(event.phase, "value") else str(event.phase)

        db_event = Event(
            run_id=run_id,
            agent=agent,
            phase=phase,
            message=event.message,
            payload=event.payload or {},
            collapse_id=event.collapse_id,
        )
        db.add(db_event)
        db.commit()
        db.refresh(db_event)

    return _sink


def emit_db_event(
    db: Session,
    run_id: uuid.UUID,
    agent: str,
    phase: str,
    message: str,
    payload: Optional[dict] = None,
    collapse_id: Optional[str] = None,
) -> Event:
    """
    Create and persist an event directly.

    Convenience function for emitting events without going through AgentEvent.

    Args:
        db: Database session
        run_id: Run UUID
        agent: Agent name (e.g., "coordinator", "extraction")
        phase: Event phase (e.g., "reason", "action", "observation", "decision")
        message: Human-readable message
        payload: Optional structured data
        collapse_id: Optional ID for collapsing related events in UI

    Returns:
        Created Event model instance
    """
    event = Event(
        run_id=run_id,
        agent=agent,
        phase=phase,
        message=message,
        payload=payload or {},
        collapse_id=collapse_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
