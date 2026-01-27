# Agentic Policy Data Analytics Platform - Architecture Overview

## Overview

The platform runs a Next.js frontend and a FastAPI backend with a Celery worker.
PostgreSQL stores runs, plans, events, and artifacts. Redis is used as the
Celery broker and result backend. Everything is orchestrated via Docker Compose.

## High-Level Diagram

```
                   +---------------------------+
                   |        Frontend           |
                   |  Next.js (React/TS)       |
                   +------+-------------+------+
                          |             |
                     HTTP (REST)   WebSocket (events)
                          |             |
                          v             v
                   +------+-------------+------+
                   |         Backend           |
                   |       FastAPI API         |
                   +------+------+-------------+
                          |      |
                          |      | DB (writes)
                          |      |
                          v      v
                   +------------------+        +------------------+
                   |   PostgreSQL     |        |      Redis       |
                   |   Runs, Events,  |        | Celery broker    |
                   |   Artifacts      |        +--------+---------+
                   +------------------+                 ^
                          ^                             |
                          |                             |
                          +---- Worker writes ----------+
                                                        |
                         enqueue task                   |
                    (approve run)                       |
                          |                             |
                          v                             |
                   +------+-------------+               |
                   |       Backend     |----------------+
                   |   Celery client   |                |
                   +-------------------+                |
                                                        |
                                                        v
                                                +--------------+
                                                |   Worker     |
                                                |  Celery task |
                                                +--------------+
```

## Core Components

- Frontend: `frontend/` (Next.js 14 app)
  - Calls REST endpoints under `/api/v1`
  - Opens WebSocket connections for live event streaming
- Backend: `backend/` (FastAPI)
  - REST endpoints for runs, sources, artifacts, exports, and health
  - WebSocket endpoint for run event streaming
- Worker: Celery task runner
  - Executes the pipeline stub and writes events/artifacts
- Database: PostgreSQL 16
  - Run lifecycle data, events, artifacts
- Cache/Broker: Redis 7
  - Celery broker and result backend

## Key Runtime Flows

### 1) Create a Run (Plan Proposal)
1. User submits a query in the frontend.
2. Frontend POSTs to `/api/v1/runs`.
3. Backend stores a `Run` and a proposed `Plan`.
4. Frontend navigates to the run detail page.

### 2) Approve and Execute
1. User approves a plan via `/api/v1/runs/{run_id}/approve`.
2. Backend enqueues a Celery task.
3. Worker executes a pipeline stub:
   - Updates run status
   - Emits events
   - Writes artifacts (tables, charts, insights, report)
4. Backend serves updated run data and artifacts.

### 3) Real-time Updates
1. Frontend connects to `/ws/runs/{run_id}`.
2. Backend sends a snapshot and streams events.
3. Frontend renders event timeline and status updates.

## Service Orchestration

Docker Compose (`infra/docker-compose.yml`) runs:
- `postgres` (database)
- `redis` (broker/cache)
- `api` (FastAPI)
- `worker` (Celery)
- `frontend` (Next.js)

## Notable Endpoints

- Health: `GET /health`, `GET /api/v1/health`
- Sources: `GET /api/v1/sources`
- Runs: `POST /api/v1/runs`, `GET /api/v1/runs`, `GET /api/v1/runs/{id}`
- Actions: `POST /api/v1/runs/{id}/approve`, `POST /api/v1/runs/{id}/abort`
- Artifacts: `GET /api/v1/runs/{id}/artifacts`
- Export: `GET /api/v1/runs/{id}/export?format=md|pdf`
- WebSocket: `GET /ws/runs/{id}`

## Current Limitations

- Pipeline execution is a stub (demo data + mock artifacts).
- PDF export is not implemented (returns 501).
