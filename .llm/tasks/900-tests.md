# 006 — Tests

## Goal
Implement a comprehensive, demo-ready test suite that covers:
- unit tests (agents/tools/API)
- integration tests (multi-agent workflow)
- LLM-specific guardrail tests (hallucination/citation/consistency)
- data quality validation tests
- performance/load smoke tests
…and document how to run and interpret them.

## Scope
### In scope
- Backend pytest suite covering API + orchestration + connectors + validators + analytics
- Frontend unit tests for key UI modules (timeline rendering, plan approval flow, API client)
- Deterministic integration tests using fixtures (no real external network)
- LLM tests using stubs/doubles (no paid API calls in CI)
- Coverage reports and a lightweight load test script

### Out of scope
- Full browser E2E (Playwright/Cypress) unless time permits
- Heavy-scale benchmarking

---

## Prerequisites

- **Docker** and **Docker Compose** installed on the host
- No Python, Node.js, or other runtime installations required on host
- All dependencies are managed inside containers

---

## Files to add / modify

### Backend
- `backend/tests/conftest.py`
- `backend/tests/test_api_runs.py`
- `backend/tests/test_ws_events.py`
- `backend/tests/test_llm_router.py`
- `backend/tests/test_agents_coordinator.py`
- `backend/tests/test_agents_extraction.py`
- `backend/tests/test_agents_analytics.py`
- `backend/tests/test_connectors_singstat.py`
- `backend/tests/test_quality_validation.py`
- `backend/tests/test_insight_grounding.py`
- `backend/tests/integration/test_pipeline_e2e.py`
- `backend/tests/fixtures/` (recorded responses + small sample datasets)
  - `singstat_sample.csv`
  - `singstat_sample.xlsx` (optional)
  - `pipeline_expected_artifacts.json`
- `backend/pyproject.toml` (add pytest/cov config if missing)

### Frontend
- `frontend/jest.config.(js|ts)` (or `vitest.config.ts`)
- `frontend/src/__tests__/timeline.test.tsx`
- `frontend/src/__tests__/plan_approval.test.tsx`
- `frontend/src/__tests__/api_client.test.ts`

### Docs
- `docs/TESTING.md`

### CI
- `.github/workflows/ci.yml` (if not already created in earlier task)

---

## Test Strategy (what we must prove)

### 1) Unit tests
**API**
- `GET /health` returns ok
- `POST /runs` creates a run and returns `run_id` + plan
- `POST /runs/{run_id}/approve` transitions status + enqueues work (mock queue)
- `GET /runs/{run_id}` returns stored artifacts

**Agent orchestration**
- Coordinator produces a plan that:
  - selects only allowed sources
  - includes time range + metrics
  - emits ReAct events

**Connectors**
- Data.gov.sg V2 connector parses JSON/CSV → normalized DataFrame
- SingStat connector parses CSV/Excel → normalized DataFrame
- Failure handling: timeout/retry path returns structured error event

**Data quality**
- Required columns present
- Type coercion rules
- Missingness thresholds produce warnings (not crashes)
- Time continuity gap detection

**Analytics**
- Trend + YoY delta correctness on fixture datasets
- Correlation only computed when sample size threshold met (otherwise explicit warning)

### 2) Integration tests (E2E in-process)
Run the full pipeline with:
- stubbed connectors returning fixtures
- stubbed LLM provider(s) returning deterministic outputs
Expect:
- events persisted in the right order (coordinator → extraction → analytics)
- datasets stored with provenance fields
- artifacts include tables + charts + insights
- insights include citations and evidence pointers

### 3) LLM-specific tests (guardrails)
These are policy-critical for the assessment.

**Citation enforcement**
- fail if any insight has empty citations
- fail if citation references unknown dataset_id
- fail if citation column/time range not present in stored dataset schema

**Hallucination detection**
- verify every numeric claim in insight `evidence` matches computed tables within tolerance
- reject if mismatch

**Consistency**
- same query + fixed seed (or deterministic stub) yields structurally identical plan JSON

**Fallback routing**
- primary provider failure triggers fallback provider
- circuit breaker prevents repeated calls when unhealthy (if implemented)

### 4) Performance/load smoke
- simple script to start N runs concurrently (e.g., 10–50) using mocked connectors/LLM
- assert p95 API latency for run creation remains acceptable locally
- ensure WS event flood protection doesn’t crash the server (basic bounded queue)

---

## Implementation Notes

### Determinism rules
- No network calls in tests.
- Use fixed fixtures for connectors.
- LLM is always stubbed with deterministic responses.
- Seed any random behavior.

### Suggested stubbing approach (backend)
- Dependency-inject connectors + LLMRouter into the pipeline
- In tests, replace with fakes that:
  - return fixture datasets
  - emit predictable events

### Suggested assertions
- Validate persisted run status transitions: `queued → awaiting_approval → running → completed|failed`
- Validate event schema fields: `run_id, agent, phase, message, payload, ts`
- Validate artifact schema: `tables_json, charts_json, insights_json`

---

## Commands

### Backend
```bash
cd backend
pytest -q
pytest --cov=app --cov-report=term-missing
```

### Integration (assumes services already up)
```bash
# Execute integration tests inside the api container
docker compose -f infra/docker-compose.yml run --rm api pytest tests/integration/test_datagov.py -v
docker compose -f infra/docker-compose.yml run --rm api pytest tests/integration/test_pipeline_e2e.py -v
```

### Frontend

```bash
cd frontend
npm test
```

### Combined (local)

```bash
docker compose -f infra/docker-compose.yml up --build
```

---

## Acceptance Criteria

* Backend: `pytest` passes with:

  * unit coverage for API, router, agents, connectors, validators, analytics
  * at least 1 integration test running the full pipeline with fixtures
  * LLM guardrail tests (citations + grounding + fallback)
  * Frontend: unit tests pass for timeline rendering and plan approval flow
  * `docs/TESTING.md` exists and includes:
    * test plan and methodology
    * hallucination detection approach
    * how to run locally + in CI
    * how to read coverage output
    * CI runs tests on push/PR and fails on test failures

---

## Deliverables Checklist

* [ ] Backend test suite + fixtures
* [ ] Frontend unit tests
* [ ] `docs/TESTING.md`
* [ ] CI workflow running tests + coverage

```
