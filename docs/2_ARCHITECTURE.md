# ARCHITECTURE — Agentic Policy Data Analytics Platform

## 1. System Overview

The system answers policy analytics questions via an agentic workflow:

Natural language query → multi-agent planning and execution → multi-source data extraction → validation/cleaning → statistical analysis + visualisations → cited insights + exportable report.

Key properties:
- Multi-agent orchestration with explicit ReAct event tracing
- Multi-source government data ingestion (2+ sources, 2+ formats)
- LLMs used for interpretation and narration; all numeric/statistical computation is done in Python
- Real-time observability in the UI (WebSocket stream)
- Reproducible runs with persisted provenance, datasets, events, and artifacts

---

## 2. High-Level Architecture

### Components
- **Web UI (Next.js / TS / React)**
  - Query input
  - Live agent monitor (timeline)
  - Results dashboard (charts, tables, insights, citations)
  - History + export

- **API Service (FastAPI)**
  - REST endpoints for runs, history, exports
  - WebSocket endpoint for streaming run events
  - Auth omitted for v1

- **Worker Service (Celery)**
  - Executes multi-agent workflow asynchronously
  - Writes events/results to DB
  - Produces report export artifacts

- **PostgreSQL**
  - Persistent store for runs, events, datasets metadata, results artifacts
  - Enables reproducibility and auditability

- **Redis**
  - Celery broker/result backend (v1)

- **External Data Sources**
  - Data.gov.sg (API/JSON/CSV)
  - DOS SingStat (CSV/Excel downloads)
  - Optional: mock internal dataset from Postgres

- **LLM Providers**
  - Provider A (primary): OpenAI
  - Provider B (fallback): Bedrock or Gemini
  - Routed through `LLMRouter` with timeouts/retry/circuit-breaker

---

## 3. Runtime Flow

### 3.1 Query → Run Creation
1. User submits query in UI.
2. API creates `runs` record with status `queued`.
3. API enqueues Celery task `run_pipeline(run_id)` and returns `run_id`.
4. UI subscribes to WebSocket events for that `run_id`.

### 3.2 Multi-Agent Execution
The worker executes a directed agent graph:

- **Coordinator Agent**
  - Parses intent/time range/entities
  - Selects sources and metrics
  - Builds an execution plan with tool calls
  - Delegates to extraction and analytics

- **Extraction Agent**
  - Fetches raw data from source connectors
  - Normalises formats to DataFrames
  - Runs validation & cleaning
  - Persists dataset metadata + cleaning logs
  - Emits events for each ReAct step

- **Analytics Agent**
  - Computes stats (trends, deltas, breakdowns, correlations where valid)
  - Generates chart specs (Plotly JSON)
  - Produces structured insight objects with citations and evidence pointers

- **Report Generator (tool / step)**
  - Renders markdown report from structured artifacts
  - Converts to PDF (optional) for export

### 3.3 UI Updates
- WebSocket streams events in near-real-time.
- UI renders:
  - Agent timeline (Reason → Action → Observation → Decision)
  - Intermediate artifacts (datasets discovered, validation warnings)
  - Final dashboard once run completes

---

## 4. Agent Orchestration Details

### 4.1 ReAct Event Model
Every agent step emits a structured event:
- `agent`: coordinator | extraction | analytics
- `phase`: reason | action | observation | decision
- `message`: human-readable
- `payload`: structured JSON (safe for UI)
- `ts`: timestamp

This is persisted and streamed, ensuring:
- Transparency (users can see what happened)
- Debuggability (replay the run)
- Auditability (why a conclusion was made)

### 4.2 LangGraph / Graph Structure
A typical graph:
1. `interpret_query` (Coordinator)
2. `plan_workflow` (Coordinator)
3. `extract_sources` (Extraction)
4. `validate_and_clean` (Extraction)
5. `run_analytics` (Analytics)
6. `generate_insights` (Analytics + LLM)
7. `render_report` (Report tool)
8. `finalize_run`

Failures are handled with:
- Source fallback (alternate dataset or cached snapshot)
- LLM fallback (Provider B)
- Partial completion (still return charts/tables if narrative fails)

---

## 5. Data Layer & Provenance

### 5.1 Storage Strategy
Persist everything needed to reproduce:
- Query + resolved intent/time range
- Source endpoints and retrieval timestamps
- Dataset schema snapshots + checksums
- Cleaning/validation logs
- Computed analytics tables
- Chart specs
- Final insights with citations
- Full event stream

### 5.2 Data Provenance Rules
- Every dataset artifact references:
  - `source` (e.g., `data_gov_sg`, `singstat`)
  - `uri` or `endpoint`
  - `retrieved_at`
  - `checksum`
  - `schema_json`
- Every insight must include citations referencing stored dataset IDs and evidence pointers.

---

## 6. Database Schema (Conceptual)

### Tables
- `runs`
  - `id`, `query`, `status`, `created_at`, `started_at`, `finished_at`
  - `selected_sources`, `llm_provider_used`, `error_summary`

- `events`
  - `id`, `run_id`, `agent`, `phase`, `message`, `payload_json`, `ts`

- `datasets`
  - `id`, `run_id`, `source`, `uri`, `retrieved_at`, `checksum`
  - `row_count`, `schema_json`, `quality_report_json`, `cleaning_log_json`

- `artifacts`
  - `id`, `run_id`
  - `tables_json` (computed tables)
  - `charts_json` (Plotly specs)
  - `insights_json`
  - `report_md`
  - `report_pdf_path` (optional)

---

## 7. Government Data Connectors

### 7.1 Connector Interface
Each connector implements:
- `discover(query_intent) -> dataset_candidates`
- `fetch(dataset_ref) -> raw_bytes`
- `parse(raw_bytes) -> DataFrame`
- `validate(df) -> quality_report`
- `clean(df) -> cleaned_df + cleaning_log`

### 7.2 Data.gov.sg
- Prefer JSON/API endpoints when available
- Support CSV downloads as fallback
- Robust retries with backoff

### 7.3 DOS SingStat
- Handle CSV/Excel table downloads
- Normalise multi-header formats
- Convert “Year/Quarter/Month” columns to canonical time index

### 7.4 Mock Internal Dataset (IMDA-Realistic)

To simulate realistic “internal systems” commonly found within IMDA, a set of **IMDA-themed internal datasets** will be seeded into PostgreSQL. These datasets are *synthetic but policy-plausible*, derived from publicly observable IMDA focus areas (digital economy measurement, AI workforce development, online safety regulation, emerging technology adoption, and digital infrastructure resilience).

These datasets are treated as **authoritative internal sources** by the agent system and behave differently from external government APIs:
- Lower latency
- Stable schemas
- Higher trust weight during planning
- Preferred fallback when external APIs fail

## 8. Analytics Architecture

### 8.1 Principles
- All numeric/statistical work is deterministic Python computation.
- LLM only narrates and structures insights based on computed evidence.

### 8.2 Core Analyses (v1)
- Time-series trendlines
- YoY / QoQ / MoM deltas (as applicable)
- Category breakdown (top-N)
- Correlation only when:
  - adequate sample size
  - clear interpretation
  - stated limitations

### 8.3 Outputs
- `tables_json`: named computed tables (tidy format)
- `charts_json`: Plotly specs referencing those tables
- `insights_json`: objects including:
  - `headline`
  - `evidence` (values + table/column pointers)
  - `policy_implication`
  - `citations` (dataset IDs + columns + time ranges)
  - `confidence` (rule-based)

---

## 9. LLM Integration Design

### 9.1 LLMRouter
Responsibilities:
- Normalize provider APIs into a single interface
- Enforce timeouts and retries
- Fallback on:
  - timeouts
  - rate limits
  - transient 5xx
- Track provider used per run

### 9.2 LLM Usage Boundaries
Allowed:
- Parse query → intent JSON
- Create plan steps
- Summarize insights grounded in evidence
- Format report

Disallowed:
- Compute numeric results
- Invent missing data
- Cite sources not retrieved in the run

---

## 10. Real-Time Observability (WebSocket)

### WebSocket Channel
- `ws://.../ws/runs/{run_id}`
- Streams `events` as they are written

Front-end renders:
- Timeline grouped by agent
- Filter by phase
- Expand payload JSON for evidence/debugging

---

## 11. Failure Handling & Degradation

### Data failures
- Retry with backoff
- Switch dataset candidate (same source)
- Switch source (alternate provider)
- Partial run result still returned with warnings

### LLM failures
- Route to fallback provider
- If both fail:
  - return computed stats and charts
  - generate template-based minimal narrative

### Validation failures
- Hard fail if core columns missing and no alternate dataset exists
- Soft fail (warning) for:
  - missingness above threshold
  - partial time gaps
  - suspected outliers

---

## 12. Security & Compliance (v1 posture, v2 direction)

v1 focuses on:
- Secrets via environment variables
- No secrets in logs/events
- Sanitized payloads for UI

v2 (innovation-ready):
- On-prem deployment model
- Private networking to data sources
- PII redaction tools
- Audit log signing
- Fine-grained access control

---

## 13. Deployment Topology (Docker Compose)

Services:
- `frontend`
- `api`
- `worker`
- `postgres`
- `redis`

Local dev:
- One command brings up stack
- Seed scripts for mock dataset (optional)
- Makefile targets for tests/lint

---

## 14. Key Design Decisions

- **Agentic transparency over opaque “LLM answers”**: all steps are evented, persisted, and observable.
- **Deterministic analytics**: avoids hallucinated numbers and supports strict validation.
- **Provenance-first**: citations and dataset IDs are first-class objects.
- **Asynchronous execution**: long runs won’t block API; UI remains responsive.
- **Multi-cloud resilience**: LLM fallback is built in, not bolted on.

---

## 15. Future Enhancements (for Innovation Section)

- Vector index for dataset metadata + prior analyses (RAG)
- Team collaboration: shared run templates, comments, tagged insights
- Confidence calibration and “review required” workflows
- Cost-aware LLM routing and caching
- Automated monitoring for upstream API schema changes
