# Task 014 — Pipeline (Backend) — Real Data Fetch + Orchestration Plan

This plan describes how to replace the stubbed pipeline with the actual data-fetch + analysis pipeline, using the existing connectors/agents and preserving UI/WS behavior.

---

## Goals
- Execute real data ingestion from approved sources.
- Run deterministic analytics and generate artifacts (tables/charts/insights).
- Persist artifacts and provenance to the DB.
- Emit DB events for live UI monitoring (WebSocket).
- Keep human-in-the-loop approval gate intact.

---

## Current State (Key Observations)
- `backend/app/tasks/pipeline.py` is stubbed and generates fake events/artifacts.
- Real connectors + ingestion exist in `DataService` and `ExtractionAgent`.
- Analytics exists in `AnalyticsAgent` but still uses synthetic data; can be kept or refined later.
- Event emission is split: agents emit to in-memory `event_store`, while UI/WebSocket uses DB `Event` rows.
- Source names are inconsistent (`data_gov_sg` vs `data.gov.sg`).

---

## Plan of Work

### 1) Normalize source IDs (single canonical scheme)
**Goal:** make connectors, plan, and UI agree on source names.
- Adopt canonical IDs: `data.gov.sg`, `singstat`, `internal`.
- Update:
  - `backend/app/api/routes/runs.py` plan generation + `/sources` list
  - `backend/app/tasks/pipeline.py` source handling
  - `frontend` fallback sources (optional but recommended)

**Success:** a single source ID string works end-to-end (plan ? extraction ? connectors).

---

### 2) Persist a structured plan (not just UI steps)
**Goal:** allow pipeline to execute real plan steps.
- Use `CoordinatorAgent.interpret_query(...)` on run creation.
- Store the full `schemas.plan.Plan` (JSON) in DB.
  - Option A: add a new `plan_json` column to `Plan`.
  - Option B: keep `steps` as UI summary and embed full plan JSON in `steps` or `edits` (less clean).
- Generate UI-friendly `steps` from structured plan so the Plan Review screen remains unchanged.

**Success:** pipeline can rehydrate a `schemas.plan.Plan` for execution.

---

### 3) Implement real pipeline execution
**Goal:** replace stubbed steps with real agents + connectors.
- Load run + plan from DB.
- Validate approval and apply user edits (sources/time range).
- Use `ExtractionAgent.run_extraction(...)` to fetch data from connectors.
- Use `AnalyticsAgent.run_analysis(...)` with extracted `Dataset` objects.
- Create `Artifact` rows from analytics output.
- Update run status/timestamps.

**Success:** artifacts and events reflect real fetched data.

---

### 4) Bridge agent events to DB
**Goal:** ensure UI/WebSocket shows live agent activity.
Two options:
- **Option A (simpler):** replace agent `_emit_event` to write DB `Event` rows.
- **Option B:** adapter that reads `event_store` and persists to DB.

**Success:** the event stream is visible on `/runs/[id]` and over `/ws/runs/{id}`.

---

### 5) Artifacts + Provenance alignment
**Goal:** expose provenance data to UI.
- Use existing `DatasetProvenance` saved by `DataService`.
- Extend the artifacts response or add a provenance endpoint.
- Update UI to display dataset provenance once returned.

**Success:** provenance tab is populated with dataset IDs/URIs/timestamps.

---

## API/Model Changes (Expected)
- `Plan` model: add `plan_json` (full structured plan) or equivalent storage strategy.
- `CreateRun` flow: coordinator used to generate plan + steps.
- `ArtifactsResponse`: include datasets/provenance if feasible.

---

## Risks / Open Questions
1. Which sources should be enabled first? (`data.gov.sg`, `singstat`, `internal`)
2. Should we store plan JSON in a new column or reuse `steps`?
3. Do we align UI `/sources` IDs to canonical IDs now?

---

## Deliverables
- Updated pipeline with real ingestion + analytics flow.
- DB-backed events emitted for each agent phase.
- Artifacts generated from real datasets.
- Optional: provenance in API response.

---

## Minimal Test Plan (once implemented)
- Create run ? approve ? verify run transitions to `running` then `completed`.
- WebSocket receives live events.
- Artifacts endpoint returns tables/charts/insights.
- Provenance endpoint (if added) returns dataset metadata.

---
