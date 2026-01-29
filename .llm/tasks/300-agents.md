### Objective

Implement the **multi-agent system** (Coordinator, Extraction, Analytics) with:

* **bounded autonomy** (plan review gate),
* **ReAct event tracing** (reason/action/observation/decision),
* **LangGraph orchestration** (preferred),
* **multi-cloud LLM routing** via `LLMRouter`,
* graceful failure + partial results.

This task directly satisfies the “Multi-Agent System”, “Agentic Framework (ReAct)”, and “Multi-Cloud LLM Integration” requirements.   

---

### Scope

**In scope**

* Agent graph + contracts between agents
* Event schema + persistence/streaming hooks
* LLMRouter interface used by agents (no provider-specific logic inside agents)
* Plan approval gate (HITL)

**Out of scope**

* UI rendering of the timeline (handled in `005-ui.md`)
* REST endpoints (handled in `004-api.md`)
* Full test suite (handled in `006-tests.md`)

---

### Repo touchpoints

From the agreed structure: 

* Backend agent code should live under:

  * `/backend/app/agents/*`
  * `/backend/app/llm/*`
  * `/backend/app/tools/*`
  * `/backend/app/schemas/*`
* Prompts are already staged in:

  * `/.llm/prompts/coordinator.md`
  * `/.llm/prompts/extraction.md`
  * `/.llm/prompts/analytics.md`
  * `/.llm/prompts/report.md` 

---

### Agent responsibilities

#### 1) Coordinator Agent

**Goal:** translate user query → structured intent → proposed plan → wait for approval → orchestrate execution.

**Inputs**

* `run_id`
* `query_text`
* optional `user_constraints` (sources allowed, timeframe, etc.)
* optional `discovery_hints` (keywords, entities, metrics)

**Outputs**

* `plan` (JSON) suitable for approval + execution
* `discovery_results` (dataset candidates per connector, metadata only)
* ReAct events for transparency

**Authority boundaries**

* May invoke **connector discovery** (metadata search only) to identify datasets
* May *propose* sources/tools; may not execute extraction/analytics directly
* Must stop after `plan` creation until `approved=true`

**Planning sequence (no execution)**

1. Interpret intent (entities, metrics, time range, constraints)
2. Run dataset discovery on **data.gov.sg** and **SingStat** connectors
3. Select best-fit dataset(s) based on relevance and constraints
4. Build extract + analysis steps using **discovered** dataset IDs (no hard-coded IDs)
5. Emit plan and wait for approval

---

#### 2) Extraction Agent

**Goal:** fetch + parse + validate + clean datasets from *approved* sources only.

**Inputs**

* `run_id`
* `approved_plan.extract_steps[]`
* `approved_plan.sources[].datasets[]` (must be discovered via coordinator)

**Outputs**

* Persisted dataset artifacts + provenance (dataset metadata IDs)
* Cleaning/validation logs (structured)
* ReAct events for each step

**Authority boundaries**

* Only uses connectors listed in plan
* Must emit a **quality report**; may downgrade confidence but must not fabricate missing fields

---

#### 3) Analytics Agent

**Goal:** compute deterministic stats + charts + insight objects grounded in computed tables.

**Inputs**

* `run_id`
* dataset IDs + cleaned DataFrames
* `approved_plan.analysis_steps[]`

**Outputs**

* Computed tables (tidy)
* Chart specs (Plotly JSON)
* Insight objects:

  * `headline`, `evidence`, `policy_implication`, `citations`, `confidence`
* ReAct events

**Authority boundaries**

* Numeric computation must be **Python deterministic**
* LLM is only used for narration/structuring; every number must map to computed evidence

---

### Contracts / Schemas

#### Event schema (persist + stream)

```json
{
  "run_id": "uuid",
  "agent": "coordinator|extraction|analytics",
  "phase": "reason|action|observation|decision",
  "message": "string",
  "payload": { "any": "json" },
  "ts": "iso8601"
}
```

#### Plan schema (approval object)

```json
{
  "intent": {
    "question": "string",
    "time_range": { "start": "YYYY", "end": "YYYY" },
    "entities": ["string"],
    "metrics": ["string"]
  },
  "sources": [
    {
      "name": "data_gov_sg|singstat|mock_internal",
      "format": "api|csv|excel|json",
      "datasets": [
        { "id": "string", "title": "string", "score": 0.0, "discovered_by": "string" }
      ]
    }
  ],
  "discovery_steps": [
    { "source": "data_gov_sg|singstat", "query": "string", "notes": "string" }
  ],
  "extract_steps": [
    { "source": "string", "dataset_ref": "string", "notes": "string" }
  ],
  "analysis_steps": [
    { "type": "trend|yoy|breakdown|correlation", "params": { } }
  ],
  "guardrails": {
    "approved_sources_only": true,
    "no_llm_math": true,
    "citation_required": true
  }
}
```

---

### LangGraph design (agent graph)

Nodes (conceptual):

1. `coordinator.interpret_query`
2. `coordinator.propose_plan`
3. **WAIT**: `plan_approval_gate` (blocks until `approved=true`)
4. `extraction.run_steps`
5. `analytics.compute_tables`
6. `analytics.build_insights`
7. `report.render` (optional step, but keep the hook)
8. `finalize`

Edges:

* Coordinator → Approval Gate → Extraction → Analytics → Finalize
* Failure edges:

  * Extraction failure → alternate dataset candidate (same source) → else partial result
  * LLM failure → fallback provider via router → else template narration

This matches the architecture’s directed workflow and observability requirements. 

---

### LLMRouter integration points

Agents must call an internal interface (example shape):

* `llm_router.complete(task_name, prompt, schema=None, timeout_s=...) -> text|json`

Rules:

* Coordinator uses LLM for: intent parse + plan proposal
* Analytics uses LLM for: insight wording only (given computed evidence JSON)
* Extraction should not require LLM (keep it deterministic)

Fallback expectations (provider A → provider B → degrade):

* If both LLMs fail: proceed with extraction + analytics; narration becomes template-based with warnings.  

---

### Prompting approach (files already staged)

Use the prompts under `/.llm/prompts/*.md` as **system templates**, and inject:

* run context (query, approved plan)
* data provenance (dataset IDs, schemas)
* computed evidence JSON (for analytics narration)

Keep prompts strict about:

* citations from retrieved dataset IDs only
* no invented numbers
* uncertainty + limitations as first-class outputs 

---

### Failure handling requirements

* **Data source failure**: retry/backoff; alternate dataset candidate; alternate source only if plan allows
* **Schema mismatch**: emit validation error + attempt safe coercions; else fail extraction step and continue others
* **Partial completion**: finalize run with `warnings[]` and any artifacts produced
* **LLM failure**: router fallback; else template narration with explicit warning

---

### Acceptance criteria

* Running a single “demo query” produces:

  * Coordinator events + plan JSON
  * A hard stop until `approved=true`
  * Extraction events + at least one persisted dataset artifact with quality report
  * Analytics events + at least one computed table + one chart spec + one insight with citations + confidence
* Every insight includes at least one citation that references an actual dataset artifact ID for that run
* No numeric values appear in insights unless they exist in computed tables
* All agent steps emit ReAct events and can be replayed from persisted logs  

---

### Deliverables checklist

* `/backend/app/agents/coordinator.py`
* `/backend/app/agents/extraction.py`
* `/backend/app/agents/analytics.py`
* `/backend/app/agents/graph.py` (LangGraph wiring)
* `/backend/app/llm/router.py`
* `/backend/app/schemas/events.py` + `/backend/app/schemas/plan.py`
* `/backend/app/tools/*` (connectors + validators callable from Extraction)
* Documentation ready for `AGENTS.md`

---

### Notes

* Keep agent logic deterministic where possible.
* Treat the plan approval gate as non-negotiable—this is your strongest “agentic governance” demo moment. 
