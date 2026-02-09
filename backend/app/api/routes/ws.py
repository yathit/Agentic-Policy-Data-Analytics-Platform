"""
WebSocket endpoint for real-time run event streaming.
"""

import uuid
import asyncio
from datetime import datetime
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Run, Event, RunStatus

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for run event streaming."""

    def __init__(self):
        # Map run_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, run_id: str, websocket: WebSocket):
        """Accept a new WebSocket connection for a run."""
        await websocket.accept()
        async with self._lock:
            if run_id not in self.active_connections:
                self.active_connections[run_id] = set()
            self.active_connections[run_id].add(websocket)

    async def disconnect(self, run_id: str, websocket: WebSocket):
        """Remove a WebSocket connection."""
        async with self._lock:
            if run_id in self.active_connections:
                self.active_connections[run_id].discard(websocket)
                if not self.active_connections[run_id]:
                    del self.active_connections[run_id]

    async def broadcast_event(self, run_id: str, event_data: dict):
        """Broadcast an event to all connections for a run."""
        async with self._lock:
            connections = self.active_connections.get(run_id, set()).copy()

        for websocket in connections:
            try:
                await websocket.send_json({
                    "type": "event",
                    "event": event_data,
                })
            except Exception:
                # Connection might be closed
                await self.disconnect(run_id, websocket)

    async def send_snapshot(self, websocket: WebSocket, run_data: dict, events: list):
        """Send initial snapshot to a newly connected client."""
        try:
            await websocket.send_json({
                "type": "snapshot",
                "run": run_data,
                "events": events,
            })
        except Exception:
            pass

    async def send_heartbeat(self, websocket: WebSocket):
        """Send heartbeat to keep connection alive."""
        try:
            await websocket.send_json({
                "type": "heartbeat",
                "ts": datetime.utcnow().isoformat(),
            })
        except Exception:
            pass


# Global connection manager
manager = ConnectionManager()


def _plan_to_dict(plan) -> dict:
    """Convert Plan to dictionary for WebSocket response."""
    if not plan:
        return None

    import uuid as uuid_module
    steps = []
    for step in plan.steps or []:
        steps.append({
            "id": step.get("id", str(uuid_module.uuid4())),
            "agent": step.get("agent", "coordinator"),
            "action": step.get("action", ""),
            "inputs": step.get("inputs", {}),
            "requires_approval": step.get("requires_approval", False),
        })

    rationale = None
    if plan.source_rationale:
        rationale = [
            {"source": r.get("source", ""), "why": r.get("why", "")}
            for r in plan.source_rationale
        ]

    return {
        "id": str(plan.id),
        "version": plan.version,
        "steps": steps,
        "source_rationale": rationale,
    }


def _run_to_dict(run: Run) -> dict:
    """Convert Run to dictionary for WebSocket response."""
    return {
        "id": str(run.id),
        "query": run.query,
        "status": run.status.value if isinstance(run.status, RunStatus) else run.status,
        "plan": _plan_to_dict(run.plan) if run.plan else None,
        "constraints": run.constraints,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "selected_sources": run.selected_sources,
        "llm_provider_used": run.llm_provider_used,
        "error_summary": run.error_summary,
    }


def _event_to_dict(event: Event) -> dict:
    """Convert Event to dictionary for WebSocket response."""
    return {
        "id": str(event.id),
        "run_id": str(event.run_id),
        "agent": event.agent,
        "phase": event.phase,
        "message": event.message,
        "payload": event.payload or {},
        "ts": event.ts.isoformat() if event.ts else None,
    }


def _sanitize_payload(payload: dict) -> dict:
    """Remove sensitive data from event payload."""
    sensitive_keys = {"api_key", "secret", "password", "token", "credential"}
    sanitized = {}
    for key, value in payload.items():
        if key.lower() in sensitive_keys:
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_payload(value)
        else:
            sanitized[key] = value
    return sanitized


@router.websocket("/ws/runs/{run_id}")
async def websocket_run_events(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for streaming run events.

    Connects to a specific run and receives real-time events.
    On connection, receives a snapshot of current run state and recent events.
    Then receives events as they occur during execution.
    """
    # Validate run_id format
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        await websocket.close(code=1008, reason="Invalid run ID format")
        return

    # Get initial run state
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.id == run_uuid).first()
        if not run:
            await websocket.close(code=1008, reason="Run not found")
            return

        # Get recent events (last 50)
        events = (
            db.query(Event)
            .filter(Event.run_id == run_uuid)
            .order_by(Event.ts.desc())
            .limit(50)
            .all()
        )
        events.reverse()  # Oldest first

        run_data = _run_to_dict(run)
        events_data = [_event_to_dict(e) for e in events]

        # Sanitize payloads
        for event in events_data:
            event["payload"] = _sanitize_payload(event.get("payload", {}))

    finally:
        db.close()

    # Accept connection
    await manager.connect(run_id, websocket)

    try:
        # Send initial snapshot
        await manager.send_snapshot(websocket, run_data, events_data)

        # Poll for new events on a short interval without waiting on client messages
        last_event_ts = events[-1].ts if events else datetime.min
        last_status = run_data["status"]
        poll_interval = 1.0
        heartbeat_interval = 30.0
        last_heartbeat = asyncio.get_running_loop().time()

        while True:
            try:
                # Non-blocking receive for optional client messages
                try:
                    message = await asyncio.wait_for(websocket.receive_json(), timeout=0.01)
                    if message.get("type") == "ping":
                        await manager.send_heartbeat(websocket)
                except asyncio.TimeoutError:
                    pass

                # Poll for new events
                db = SessionLocal()
                try:
                    new_events = (
                        db.query(Event)
                        .filter(Event.run_id == run_uuid)
                        .filter(Event.ts > last_event_ts)
                        .order_by(Event.ts.asc())
                        .all()
                    )

                    for event in new_events:
                        event_data = _event_to_dict(event)
                        event_data["payload"] = _sanitize_payload(event_data.get("payload", {}))
                        await websocket.send_json({
                            "type": "event",
                            "event": event_data,
                        })
                        last_event_ts = event.ts

                    # Check run status for updates
                    run = db.query(Run).filter(Run.id == run_uuid).first()
                    if run:
                        current_status = run.status.value if isinstance(run.status, RunStatus) else run.status

                        # Send status update if status changed (e.g., planning -> awaiting_approval)
                        if current_status != last_status:
                            await websocket.send_json({
                                "type": "status",
                                "status": current_status,
                                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                            })
                            last_status = current_status

                            # Also send updated run data with plan if transitioning to awaiting_approval
                            if current_status == "awaiting_approval":
                                await websocket.send_json({
                                    "type": "snapshot",
                                    "run": _run_to_dict(run),
                                    "events": [],  # Events already sent incrementally
                                })

                        # Close connection on terminal states
                        if run.status in [
                            RunStatus.COMPLETED,
                            RunStatus.FAILED,
                            RunStatus.ABORTED,
                        ]:
                            await asyncio.sleep(1)
                            break

                finally:
                    db.close()

                # Heartbeat to keep connection alive
                now = asyncio.get_running_loop().time()
                if now - last_heartbeat >= heartbeat_interval:
                    await manager.send_heartbeat(websocket)
                    last_heartbeat = now

                await asyncio.sleep(poll_interval)

            except WebSocketDisconnect:
                break

    except Exception:
        pass
    finally:
        await manager.disconnect(run_id, websocket)


# Function to broadcast events from background tasks
async def broadcast_event_to_run(run_id: str, event: Event):
    """
    Broadcast a new event to all WebSocket connections for a run.
    Called from background tasks when new events are created.
    """
    event_data = _event_to_dict(event)
    event_data["payload"] = _sanitize_payload(event_data.get("payload", {}))
    await manager.broadcast_event(run_id, event_data)
