# Plan: Weekly data.gov.sg Collections Ingest + Startup Bootstrap

Date: 2026-01-29

## Goals
- Run the data.gov.sg collections ingest on a weekly schedule (Option B).
- On startup, if the collections table is empty, trigger a one-time ingest after all services are ready.
- Keep the workflow idempotent and safe across multiple app instances.

## Scope
- Scheduling (weekly) and startup bootstrap logic.
- Readiness checks and concurrency safeguards.
- Basic observability (logs + success/failure metadata).

## Non-goals
- Changing the ingest logic in `backend/app/workers/data_gov_sg_collections.py`.
- Building UI for admin controls.
- Backfilling other data.gov.sg endpoints.

## Assumptions
- Celery is already used (`backend/app/tasks/pipeline.py`).
- Postgres schema includes `data_gov_sg_collection` (see `backend/app/db/sql/ddl_data_gov_sg_collection.sql`).

## Proposed Design

### 1) Weekly Schedule  
- Add a Celery Beat schedule that calls a new task wrapper for
  `run_data_gov_sg_collections_ingest()`.
- Default schedule: weekly, configurable via environment variables.
- Recommended default: Sunday 02:00 Asia/Singapore (configurable timezone + time).

### 2) Startup Bootstrap (Empty Table)
- On backend startup (after DB is ready), check if
  `data_gov_sg_collection` has any rows.
- If empty, enqueue the same Celery task immediately.
- Guard against multiple instances enqueueing at once (see locking below).

### 3) Readiness & Concurrency
- Readiness: ensure DB connectivity and migrations/DDL applied before the
  startup check runs.
- Use a Postgres advisory lock to prevent duplicate concurrent ingests:
- Both weekly and startup paths should respect the same lock.

### 4) Observability
- Skip for now

### 5) Configuration
- `DATA_GOV_SG_INGEST_WEEKLY_CRON` (e.g., `0 2 * * 0`)
- `DATA_GOV_SG_INGEST_TZ` (default `Asia/Singapore`)
- `DATA_GOV_SG_INGEST_STARTUP_IF_EMPTY` (default `true`)

## Execution Steps (Implementation Plan)
1. Create a Celery task wrapper (e.g., `run_data_gov_sg_collections_ingest_task`)
   in `backend/app/tasks/` that calls the worker function and logs results.
2. Register a Celery Beat schedule to run weekly.
3. Add startup hook (FastAPI lifespan or `startup` event) that:
   - Waits for DB ready
   - Checks if `data_gov_sg_collection` is empty
   - Enqueues the task if empty

