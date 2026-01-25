# AI Agent Instructions — Agentic Policy Data Analytics Platform

## 🎯 Project Overview

This is a **full-stack agentic analytics platform** answering policy research questions via multi-agent orchestration. Architecture: Next.js frontend → FastAPI backend → Celery workers executing a ReAct-based agent graph (Coordinator → Extraction → Analytics) pulling from government data sources.

**Core design principle:** LLMs for interpretation/narration only; all numeric computation in Python. Events persisted for reproducibility and auditability.

---

## 🏗️ Essential Architecture

### Request Lifecycle
1. User query → API creates `run` record (status: `queued`)
2. Backend presents proposed **agent plan** for approval (HITL gate)
3. User approves/edits/aborts in UI
4. Celery worker executes approved plan asynchronously
5. Multi-agent graph emits **ReAct events** (reason → action → observation → decision)
6. WebSocket streams events to UI in real-time; UI renders timeline + final dashboard

### Three-Agent System
- **Coordinator:** Parses intent, selects sources, builds plan. Stops at approval gate.
- **Extraction:** Fetches from approved sources only, normalises formats, validates quality, logs cleaning steps.
- **Analytics:** Computes stats (trends, YoY, correlations), generates chart specs, structures insights with citations.

**Critical:** Each agent must emit explicit ReAct events at each phase. Events are persisted in `events` table and streamed via WebSocket.

### Data Provenance
Every dataset artifact must track: `source`, `uri`, `retrieved_at`, `checksum`, `schema_json`. Every insight must cite dataset IDs and evidence pointers. This enables reproducibility and transparency.

---

## 🗂️ Repo Structure & Key Files

```
/backend
  app/
    main.py                    # FastAPI entry; sets up WebSocket, routes
    agents/                    # Multi-agent orchestration
      coordinator.py           # Plan generation (LangGraph node)
      extraction.py            # Data fetching & validation
      analytics.py             # Statistical computation
      graph.py                 # LangGraph definition (dag/routing)
    llm/
      router.py                # LLMRouter (multi-cloud failover logic)
      providers/               # Provider adapters (openai, bedrock, etc.)
    connectors/                # Data source integrations
      datagovsg.py             # Data.gov.sg (JSON/CSV/API)
      singstat.py              # DOS SingStat (CSV/Excel downloads)
      mock_internal.py         # Mock enterprise dataset
    tools/                     # Agent-callable tools (fetch, compute, format)
    schemas/                   # Pydantic models (ReAct events, plans, artifacts)
      events.py                # ReAct event structure
      artifacts.py             # Charts, insights, datasets
    db/
      models.py                # SQLAlchemy ORM (runs, events, datasets, artifacts)
  tests/
    conftest.py                # Pytest fixtures (stubbed connectors, LLM mocks)
    fixtures/                  # Sample datasets (datagov_sg_sample.json, etc.)
    test_*.py                  # Unit tests (agents, connectors, API)
    integration/
      test_pipeline_e2e.py      # Full multi-agent workflow with stubs
  Dockerfile
  pyproject.toml

/frontend
  src/
    app/
      page.tsx                 # Home page (query input)
      layout.tsx
    components/
      QueryInput.tsx           # User query submission
      PlanReview.tsx           # HITL gate (approve/edit/abort)
      AgentTimeline.tsx        # ReAct event stream visualization
      Dashboard.tsx            # Results (charts, tables, insights)
    hooks/
      useRun.ts                # WebSocket subscription + polling
      useEvents.ts             # Real-time event filtering
    api/
      client.ts                # REST client (create run, approve, fetch artifacts)
  package.json

/.llm
  architecture.md              # Full system design (READ THIS FIRST)
  plan.md                      # Scope, success criteria, tech stack
  tasks/
    001-bootstrap.md           # Repo skeleton (Docker Compose)
    002-data-sources.md        # Connector implementations
    003-agents.md              # Agent orchestration (LangGraph)
    004-api.md                 # REST + WebSocket endpoints
    005-ui.md                  # Frontend flows
    006-tests.md               # Test strategy
  prompts/
    coordinator.md             # Coordinator system prompt
    extraction.md              # Extraction agent prompt
    analytics.md               # Analytics agent prompt
    report.md                  # Report generator prompt

/infra
  docker-compose.yml           # Postgres, Redis, API, Frontend services
  .env.example                 # Environment template
```

---

## 🔧 Developer Workflows

### Local Setup
```bash
# One-command startup:
docker compose -f infra/docker-compose.yml up --build

# Services: postgres (5432), redis (6379), api (8000), frontend (3000)
# Health check: curl http://localhost:8000/health
```

### Backend Development
```bash
cd backend
pip install -e ".[dev]"              # Install with test dependencies
pytest                                # Run all tests
pytest -v tests/integration/          # Run integration suite
pytest --cov=app tests/               # Coverage report
python -m black app/ tests/           # Format code
python -m pylint app/                 # Lint
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev                           # Start Next.js dev server (3000)
npm test                              # Run jest/vitest suite
npm run lint                          # ESLint check
```

### Testing Philosophy
- **Unit tests** use **fixtures** (no real API calls). See `backend/tests/fixtures/` for sample data.gov.sg/SingStat responses.
- **LLM tests** use **stubs** returning deterministic outputs (prevent $ usage in CI).
- **Integration tests** wire real agent code with stubbed I/O (verify orchestration logic).
- **E2E** tests are run manually/on-demand in staging (not in CI).

Example stub pattern in `conftest.py`:
```python
@pytest.fixture
def mock_llm_provider():
    return MagicMock(spec=LLMProvider)
    mock.chat(...).return_value = ChatResponse(content="{ ... }")
```

---

## 📋 Critical Patterns & Conventions

### ReAct Event Emission
Every agent step **must** emit a structured event to the database + WebSocket:
```python
# Event schema in schemas/events.py
event = ReActEvent(
    run_id=run_id,
    agent="coordinator" | "extraction" | "analytics",
    phase="reason" | "action" | "observation" | "decision",
    message="Human-readable explanation",
    payload={ ... },  # Structured JSON (safe for UI)
    ts=datetime.utcnow()
)
await db.events.insert(event)
await websocket_broadcast(run_id, event)
```
**Why:** Enables real-time UI updates + replay/audit trails + transparent reasoning.

### LLMRouter Usage
Never call OpenAI/Bedrock directly. Always route through `LLMRouter`:
```python
from app.llm.router import LLMRouter
router = LLMRouter()
response = await router.chat(messages=[...], timeout=30, fallback_provider="bedrock")
```
Router handles timeouts, retries, circuit-breaker, provider failover.

### Connector Pattern
All data connectors implement:
```python
# In connectors/{source}.py
async def discover(intent: str) -> list[DatasetCandidate]: ...
async def fetch(ref: DatasetRef) -> bytes: ...
async def parse(raw: bytes) -> pd.DataFrame: ...
async def validate(df: pd.DataFrame) -> QualityReport: ...
async def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningLog]: ...
```
**Why:** Standardized integration + quality transparency + source fallback.

### Data Provenance
When storing a dataset:
```python
dataset = Dataset(
    run_id=run_id,
    source="data_gov_sg" | "singstat" | "mock_internal",
    uri="https://...",
    retrieved_at=datetime.utcnow(),
    checksum=hashlib.sha256(raw_bytes).hexdigest(),
    schema_json=df.dtypes.to_dict(),
    row_count=len(df),
    quality_report_json=quality_report.dict(),
    cleaning_log_json=cleaning_log.dict()
)
await db.datasets.insert(dataset)
```
**Never create insights without tracing back to a stored dataset.**

### Agent Orchestration (LangGraph)
Define the graph in `agents/graph.py`:
```python
from langgraph.graph import StateGraph

graph = StateGraph(PipelineState)
graph.add_node("interpret_query", coordinator_interpret)
graph.add_node("plan_workflow", coordinator_plan)
graph.add_node("extract_sources", extraction_extract)
graph.add_node("validate_and_clean", extraction_validate)
graph.add_node("run_analytics", analytics_run)
graph.add_node("generate_insights", analytics_generate_insights)
graph.add_edge("interpret_query", "plan_workflow")
graph.add_conditional_edges("plan_workflow", approval_gate)
# ... etc
```
Each node is an async function that emits events and updates state.

### Multi-Cloud LLM Fallback
```python
# In coordinator agent
response = await llm_router.chat(
    messages=system_prompt + [user_query],
    temperature=0.2,  # Lower for determinism
    timeout=30,
    fallback_provider="bedrock",  # If OpenAI times out
    tools=[select_sources_tool, set_timeframe_tool, ...]  # If using function calling
)
```
**Never assume a provider will succeed.** Design for degradation.

---

## ✅ Testing Imperatives

### Before Pushing Code
1. **Unit tests pass:** `pytest backend/tests/test_*.py -v`
2. **Integration test passes:** `pytest backend/tests/integration/ -v`
3. **No real external API calls in CI.** Stub all LLM + data source calls.
4. **Coverage >70% on app/agents, app/llm, app/connectors.**

### When Adding a New Connector
1. Implement the `Connector` ABC in `/app/connectors/{source}.py`.
2. Add fixture data under `tests/fixtures/{source}_sample.*`.
3. Write unit tests in `tests/test_connectors_{source}.py`.
4. Add integration test step in `tests/integration/test_pipeline_e2e.py`.

### When Adding an Agent Step
1. Define the node function in the agent module.
2. Emit ReAct events at each phase (reason, action, observation, decision).
3. Unit test with mocked dependencies.
4. Integration test with full graph + stubbed I/O.

---

## 🚨 Common Pitfalls to Avoid

| Pitfall | ❌ Wrong | ✅ Right |
|---------|---------|---------|
| Direct LLM call | `await openai.ChatCompletion.create(...)` | `await llm_router.chat(...)` |
| Numeric computation in LLM | LLM returns "The trend is up" | Python computes trend, LLM narrates findings |
| Missing provenance | Store insight without dataset ID | Insight includes `dataset_ids[]` + `evidence_pointers[]` |
| Event not persisted | Emit event only to WebSocket | Persist **and** emit (db insert + broadcast) |
| No failure path | Assume data source always works | Try primary, fallback to alt source, degrade gracefully |
| Hard-coded credentials | `api_key="sk-..."` in code | Read from `.env` / environment variables |
| Skipping HITL gate | Execute plan immediately | Always require `approved=true` before worker execution |

---

## 📚 Reference Documentation

- **Architecture deep-dive:** [`.llm/architecture.md`](./.llm/architecture.md) — read this for system design, data flows, and why decisions were made.
- **Scope & tech stack:** [`.llm/plan.md`](./.llm/plan.md) — success criteria and allowed technologies.
- **Task specifications:** [`.llm/tasks/`](./.llm/tasks/) — current work breakdown.
- **Agent prompts:** [`.llm/prompts/`](./.llm/prompts/) — system prompts for each agent.
- **API contracts:** [`.llm/contracts/api.yaml`](./.llm/contracts/api.yaml) (if present).

---

## 🤖 AI Agent Quick Start

1. **Understand the big picture:** Read `.llm/architecture.md` (5 min).
2. **Check the current task:** Find the relevant file in `.llm/tasks/` (1 min).
3. **Locate the code:** Navigate to `backend/app/` or `frontend/src/` using the structure above.
4. **Follow patterns:** Copy the structure of existing agents/connectors/tests.
5. **Test before commit:** Run `pytest` or `npm test` locally.
6. **Emit events:** If adding agent logic, ensure ReAct events are emitted.
7. **Document decisions:** Add comments explaining non-obvious choices (e.g., why a fallback is needed).

