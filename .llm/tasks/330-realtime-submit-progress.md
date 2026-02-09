# Task 330 - Real-Time Planning Progress During Query Submission

## Objective
Eliminate the "silent long pause" after clicking **Submit Query** by showing live, meaningful progress while the coordinator performs LLM intent parsing and dataset discovery/ranking.

## Problem (Observed)
- `POST /api/v1/runs` currently waits for full plan generation before returning.
- During this wait, the home page only shows `Submitting...` with no stage detail.
- Users perceive the app as stalled even though backend work is ongoing.

## Product Direction
- Return quickly from submit with a `run_id`, then stream or poll planning progress events.
- Show stage-by-stage progress in UI (intent parsing, discovery, ranking, plan assembly).
- Keep transparency high: what is happening now, what just finished, and what is next.

## Scope
- Backend run creation flow in `backend/app/api/routes/runs.py`.
- Coordinator planning event sequence in `backend/app/agents/coordinator.py`.
- Run status model/contract in `backend/app/models/run.py` and run schemas.
- Frontend submit flow in `frontend/src/app/page.tsx` and `frontend/src/components/QueryBox.tsx`.
- Frontend run details event handling in `frontend/src/app/runs/[runId]/page.tsx`.

## Non-Goals
- No changes to analytics/extraction execution after approval.
- No redesign of timeline components beyond submit/planning experience.
- No model quality changes for ranking itself (this task is UX/state visibility).

## Plan

### 1. Introduce explicit planning lifecycle state
- Add a pre-approval planning state (example: `planning`) to run lifecycle.
- On submit:
  - Create run immediately with planning status.
  - Return response immediately with `run.id` and status.
- Transition states:
  - `planning` -> `awaiting_approval` when plan persisted successfully.
  - `planning` -> `failed` on planning error (with error summary).

### 2. Move plan generation to background execution
- Decouple plan generation from synchronous request path in `create_run`.
- Trigger asynchronous planning worker/task right after run creation.
- Ensure idempotency guard so planning is not generated twice for same run.
- Persist partial planning events even if final plan fails.

### 3. Add planning-stage progress events
- Emit fine-grained events from coordinator with stable machine-readable `stage` keys:
  - `planning_started`
  - `intent_parsing_started` / `intent_parsing_completed`
  - `discovery_started` / `discovery_source_completed`
  - `ranking_started` / `ranking_completed`
  - `plan_assembly_started` / `plan_ready`
- Include payload fields for UX:
  - `stage`
  - `progress_percent` (coarse milestones, not fake precision)
  - `source` (when applicable)
  - counters like `candidates_seen`, `sources_completed`, `sources_total`
  - `eta_hint_seconds` (optional, heuristic)

### 4. Update frontend submit UX for immediate liveliness
- After submit returns `run_id`, navigate immediately to `/runs/{runId}`.
- On run page, if status is `planning`:
  - Show dedicated "Building plan..." panel with stage labels.
  - Show latest event message and elapsed time.
  - Show skeleton placeholders for plan review card until plan exists.
- Replace single static `Submitting...` feedback with stage-aware copy.

### 5. Ensure transport fallback works
- Primary: WebSocket snapshot/events update planning progress live.
- Fallback: poll run/events endpoints while status is `planning`.
- Guarantee user still sees progress if websocket is disconnected.

### 6. Failure and timeout behavior
- Define planning timeout threshold (configurable) for very long LLM/discovery waits.
- If timeout/failure:
  - set run to `failed`
  - emit terminal event with reason and retry guidance
  - show clear recovery action in UI (retry with same query).

### 7. Metrics and observability
- Track planning latency breakdown:
  - total planning duration
  - intent parsing duration
  - discovery duration
  - ranking duration
- Add logs/counters to verify reduced perceived idle time.

## API/Contract Changes
- Run status enum adds `planning`.
- `CreateRunResponse` remains compatible but now returns before plan is ready.
- `GET /runs/{id}` may return `plan: null` while `status=planning`.
- Events contract includes stable planning `stage` and coarse `progress_percent`.

## Acceptance Criteria
1. Submit returns quickly (target: under 1 second excluding DB latency), even when planning is slow.
2. User sees progress updates within 1-2 seconds after submit and continuously thereafter.
3. No long silent period while LLM parsing/discovery is running.
4. When planning completes, UI transitions to normal plan review without refresh.
5. On planning failure/timeout, user sees explicit reason and retry path.
6. Existing flows for `awaiting_approval -> approve -> queued/running` remain intact.

## Test Plan

### Backend
- Unit tests for run lifecycle transitions:
  - `planning -> awaiting_approval`
  - `planning -> failed`
- Test asynchronous planning trigger on run creation.
- Test planning event payload schema (`stage`, `progress_percent`, counters).
- Test timeout handling and terminal failure event emission.

### API Contract
- `POST /runs` returns before plan exists.
- `GET /runs/{id}` returns `status=planning` with `plan=null` during planning.
- `GET /runs/{id}/events` includes ordered planning stage events.

### Frontend
- Home submit test: immediate navigation to run detail after API success.
- Run detail test: planning panel appears when status is `planning`.
- WebSocket-disconnected scenario: polling still updates stage/progress.
- Transition test: planning panel replaced by plan review when status becomes `awaiting_approval`.

### End-to-End
- Simulate slow intent parsing/discovery and verify user receives multiple progress updates before plan completion.
- Verify no regression in approve/run pipeline after plan is ready.

## Rollout Notes
- Ship behind a feature flag if needed (`ENABLE_ASYNC_PLAN_CREATION`).
- Keep backward compatibility for clients that assume immediate plan availability by handling `plan=null` defensively.
