# Project Plan — Agentic Policy Data Analytics Platform

## 0) Goal
Build a full-stack agentic analytics platform that answers policy research questions end-to-end:
natural-language query → **human-reviewed agent plan** → multi-agent workflow → multi-source government data extraction → validation/cleaning → statistical analysis + visualisations → **confidence-scored, cited insights** → exportable report — with real-time agent event streaming in the UI.

The system is explicitly designed to align with the IMDA New Model AI Governance Framework for Agentic AI (2026), emphasising bounded autonomy, transparency, human oversight, and fail-safe behaviour.

## 1) Scope & Success Criteria

### Must-have (assessment requirements)
- Multi-agent system (3 agents minimum) with **bounded autonomy**:
  - **Data Coordinator Agent**: interprets query, proposes an execution plan, delegates tasks **after human approval**, handles retries/ambiguity.
  - **Data Extraction Agent**: fetches data from approved sources only, normalises formats, validates quality (read-only, least-privilege access).
  - **Analytics Agent**: computes statistics, trends, correlations; generates policy-relevant insights grounded strictly in computed evidence.
- Human-in-the-loop governance:
  - Explicit **plan review / approve / abort** step before execution.
  - Ability to halt runs and inspect partial results.
- Government data integration:
  - Integrate **at least 2** sources from: DOS SingStat, MOM Statistics, Data.gov.sg, mock internal DB.
  - Support **at least 2 formats** among CSV / Excel / JSON / API responses.
  - Error handling for missing data, schema mismatch, API failure.
  - Data quality validation + cleaning with explicit rules and reporting.
- Intelligent analysis:
  - Meaningful statistical analysis (time trends, YoY change, correlation where appropriate).
  - Policy-oriented insight objects with **citations, provenance, and confidence scores**.
  - Visualisations suitable for policy briefing.
- Full-stack app:
  - Frontend: query input, **plan review / approve / abort**, live agent monitor (reason/action/observation), dashboard, history, export.
  - Backend: REST APIs, async task processing for long runs, DB storage, WebSocket streaming.
- Multi-cloud LLM integration:
  - At least **two** providers (e.g., OpenAI + Bedrock/Gemini/Azure OpenAI).
  - Fallback mechanism with health checks / timeouts / retry.
  - LLM used for interpretation and narration — **never for numeric computation**.
- Agentic framework + ReAct:
  - LangGraph (preferred) or equivalent orchestration.
  - Explicit ReAct loop per agent with reasoning traces persisted for auditability.
  - Graceful failure handling (fallback to alternate source/LLM, partial results with warnings).
- Testing:
  - Unit tests (agents/tools/API).
  - Integration tests (multi-agent workflow).
  - LLM tests (hallucination detection, consistency, citation enforcement).
  - Data quality tests.
  - Performance/load tests (lightweight but real).
- DevOps:
  - Docker + Docker Compose for full stack.
  - CI pipeline (GitHub Actions) running tests + lint.
  - Clear docs for setup, run, test, and demo.

### Nice-to-have
- Streaming partial results as they become available.
- Vector store for dataset metadata + semantic retrieval of prior analyses.
- Cost tracking per run (LLM token usage + external API calls).
- Pluggable “internal dataset” connector (mock DB that looks enterprise-real).

### Out of scope (intentionally)
- Auth/RBAC/SSO
- Production-grade data lake
- Heavy ML forecasting models
- Complex multi-tenant governance workflows  
(These can be discussed as “future work” in the innovation section.)

## 2) Tech Choices

### Frontend
- Next.js (App Router), TypeScript, React
- Visualisations: Plotly (or Chart.js if simpler)
- State: lightweight (React Query / SWR optional)
- Realtime: WebSocket client for run events

### Backend
- FastAPI (async)
- Background execution: Celery + Redis
- DB: PostgreSQL (primary)
- Data: Pandas for cleaning/analysis
- Validation: pydantic + pandera (optional) for schema checks

### Agents
- LangGraph for orchestration
- ReAct pattern enforced via event schema:
  - `reason`, `action`, `observation`, `decision`

### LLMs
- Provider A: OpenAI (primary)
- Provider B: AWS Bedrock or Gemini (fallback)
- Implement `LLMRouter` abstraction with:
  - per-provider timeouts
  - retry policies
  - circuit breaker/health state

## 3) System Architecture (high level)

### Request lifecycle
1. User submits query in UI.
2. Backend creates a `run` record and presents proposed agent plan.
3. User approves / edits / aborts plan.
4. Backend enqueues async job.
5. Coordinator agent executes approved plan, emits events.
6. Extraction agent fetches/normalises/validates datasets, stores artifacts + provenance.
7. Analytics agent computes results, generates structured insights + charts.
8. Report generator produces a final report with citations and confidence scores.
9. UI receives WebSocket events in real-time and renders:
   - agent timeline
   - intermediate artifacts (datasets, charts)
   - final dashboard + export actions

### Core backend components
- API service (FastAPI)
- Worker service (Celery)
- Redis broker
- Postgres DB
- Optional: object storage (local volume) for exports

## 4) Data Sources (v1)

### Required v1 targets (pick 2 to start)
- **Data.gov.sg**: API / JSON / CSV endpoints (stable and demo-friendly)
- **DOS SingStat**: downloadable CSV/Excel tables (show format diversity)

### Optional / fallback
- Mock “internal” dataset in Postgres (MOM-like stats) to demonstrate enterprise integration.

### Data ingestion rules
- Every dataset stored with:
  - source name
  - retrieval timestamp
  - raw URI/endpoint
  - checksum/hash
  - schema snapshot
  - row count
  - cleaning steps log

## 5) Data Quality & Validation

### Minimum checks
- Required columns present
- Datatypes coercible (date/number/category)
- Missingness thresholds (e.g., warn if >5% on key metrics)
- Time series continuity checks (detect gaps)
- Duplicate row detection where applicable

### Cleaning steps (transparent)
- Normalise column names
- Parse dates to canonical form
- Convert numeric strings to floats/ints
- Handle missing values (drop/forward-fill/interpolate depending on metric)
- Outlier detection (simple z-score or IQR; label, not delete, unless configured)

All checks emit structured events and are visible in UI.

## 6) Analytics (v1)

### Core analyses
- Trend lines over time
- YoY / QoQ change (configurable)
- Sector breakdown (top-N categories)
- Simple correlations (only when statistically meaningful + adequate sample size)

### Output format (structured)
- Metrics table(s)
- Chart specs (Plotly JSON)
- Insight objects:
  - `headline`
  - `evidence` (numbers derived from computed tables)
  - `policy_implication`
  - `citations` (dataset references + column names + time ranges)
  - `confidence` (rule-based score)

## 7) Real-time Agent Observability

### Event stream schema
- `run_id`
- `agent` (coordinator|extraction|analytics)
- `phase` (reason|action|observation|decision)
- `message` (human-readable)
- `payload` (structured JSON, safe to display)
- `ts`

UI shows a timeline with filtering by agent and phase.

### Governance signals exposed in UI
- Agent role and authority boundaries
- Data source provenance per action
- Confidence / uncertainty indicators on insights
- Explicit warnings on partial, degraded, or low-confidence outputs

## 8) Multi-Cloud LLM Strategy

### Principles
- LLM for:
  - query interpretation (intent + entities + time range)
  - tool selection / planning (Coordinator)
  - narrative insight wording (grounded in computed evidence)
  - report formatting
- LLM not for:
  - calculating stats
  - inventing numbers
  - referencing sources that were not actually retrieved

### Fallback
- If Provider A fails (timeout/rate limit/5xx), route to Provider B.
- If both fail, degrade gracefully:
  - show extracted data + computed charts
  - skip narrative or use template-based wording with warnings

## 9) Testing Strategy

### Unit tests
- Connectors (happy path + failure path)
- Data quality validators
- Analytics computations
- LLMRouter fallback behavior
- API handlers

### Integration tests
- End-to-end run with mocked external APIs (recorded fixtures)
- Multi-agent workflow produces:
  - datasets persisted
  - events streamed
  - insights contain citations and confidence scores

### LLM-specific tests
- Citation enforcement: fail if insight lacks citation or references unknown dataset.
- Consistency: same query with fixed seed produces structurally identical plan.
- Hallucination detection:
  - verify every numeric claim exists in computed tables
  - reject if mismatch beyond tolerance

### Performance/load
- Concurrent run initiation
- Worker throughput baseline
- WebSocket event flood protection

## 10) DevOps & Delivery

### Docker
- `docker-compose.yml` includes:
  - frontend
  - api
  - worker
  - postgres
  - redis

### CI (GitHub Actions)
- Backend: lint + pytest + coverage
- Frontend: lint + unit tests
- Build docker images (optional)

### Documentation deliverables
- 1_README.md (setup/run/test/demo)
- 2_ARCHITECTURE.md (agents + data flow + schema)
- 3_AGENTS.md (overview of LLM agents and query flow)
- 4_DATA_SOURCES.md (endpoints, formats, caveats)
- 5_DEMO_QUERIES (example query)
- Optional: AI_ASSISTED_DEVELOPMENT.md (guardrails and verification approach)

## 11) Demo Plan (20 minutes)

### Demo query (primary)
“Analyse employment trends in the technology sector from 2020–2024.”
“Analyse AI and digital economy workforce trends in Singapore from 2019–2024, and assess potential talent gaps relevant to AI governance and digital regulation.”

### What to show live
- Query submission
- Coordinator plan proposal → human approval
- Extraction from 2 sources + validation logs
- Analytics charts and computed tables
- Final insights with citations and confidence scores
- Export report
- Failure demo:
  - simulate API failure or LLM timeout
  - show fallback, partial results, and user-facing warning

## 12) AI-Assisted Development Workflow (repo discipline)

### Rules
- Work in small tasks under `/.llm/tasks/NNN-*.md`
- Each task lists:
  - allowed files to edit
  - acceptance criteria
  - test command to run
- No new dependencies without updating docs
- Every backend feature includes tests (at least a stub)
- Every insight must be backed by computed evidence + citations

### Output quality bar
- Clean structure, minimal magic
- Deterministic data pipelines
- Transparent provenance
- Demo-ready stability
