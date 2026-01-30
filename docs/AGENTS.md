# Multi-Agent System Documentation

## Overview

This document describes the multi-agent system implemented for the IMDA Policy Data Analytics Platform. The system uses LangGraph orchestration with three specialized agents following the ReAct (Reason-Action-Observation-Decision) pattern.

## Architecture

### Agent Types

1. **Coordinator Agent** (`app/agents/coordinator.py`)
   - Interprets natural language queries
   - Generates structured execution plans
   - Proposes data sources and analysis steps
   - **Bounded authority**: Cannot execute directly, only propose

2. **Extraction Agent** (`app/agents/extraction.py`)
   - Fetches data from approved sources only
   - Validates data quality
   - Cleans and normalizes datasets
   - Tracks full provenance
   - **Deterministic**: No LLM usage, pure data pipeline

3. **Analytics Agent** (`app/agents/analytics.py`)
   - Computes statistics using Python/pandas
   - Generates chart specifications (Plotly JSON)
   - Creates grounded insights with citations
   - **Principle**: Python for numbers, LLM for language only

### Workflow

```
User Query
    ↓
Coordinator: Interpret → Propose Plan
    ↓
[APPROVAL GATE - HITL]  ← Human reviews and approves
    ↓
Extraction: Fetch → Validate → Clean
    ↓
Analytics: Compute → Chart → Insight
    ↓
Final Results (with full event trace)
```

## Key Features

### 1. Bounded Autonomy

Each agent has clear authority boundaries:
- Coordinator **proposes** but doesn't execute
- Extraction **only** uses approved sources from plan
- Analytics **only** computes with Python (no LLM math)

### 2. Plan Approval Gate (HITL)

**Critical**: The system MUST stop after plan generation and wait for human approval.

```python
# Execute until approval gate
result = orchestrator.execute(query)

# Human reviews plan
plan = result["plan"]

# Human approves
orchestrator.approve_plan(run_id, approved=True)

# Continue execution
final_output = orchestrator.continue_after_approval(run_id)
```

### 3. ReAct Event Tracing

Every agent action emits structured events:

```json
{
  "run_id": "uuid",
  "agent": "coordinator|extraction|analytics",
  "phase": "reason|action|observation|decision",
  "message": "Human-readable description",
  "payload": { "structured": "data" },
  "ts": "2024-01-25T10:30:00Z"
}
```

Events provide:
- Full observability into agent decisions
- Audit trail for compliance
- Debugging and replay capability

### 4. Multi-Cloud LLM Routing

LLM calls automatically failover between providers:

```
Primary (OpenAI) → Fallback (Anthropic) → Template
```

```python
llm_router = LLMRouter(
    primary_provider=LLMProvider.OPENAI,
    secondary_provider=LLMProvider.ANTHROPIC
)

result = llm_router.complete(
    task_name="intent_parse",
    prompt=prompt,
    schema=json_schema
)
```

### 5. Grounded Insights with Citations

Every insight MUST cite source datasets:

```json
{
  "headline": "Tech sector employment grew 55% from 2019 to 2023",
  "evidence": {
    "value_2019": 100000,
    "value_2023": 155000,
    "percentage_change": 0.55
  },
  "citations": [
    {
      "dataset_id": 123,
      "dataset_name": "Singstat Employment by Industry",
      "field": "employment_count"
    }
  ],
  "confidence": 0.95
}
```

## Directory Structure

```
backend/
├── app/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── coordinator.py      # Query interpretation & planning
│   │   ├── extraction.py       # Data fetching & validation
│   │   ├── analytics.py        # Computation & insights
│   │   └── graph.py            # LangGraph orchestration
│   ├── llm/
│   │   ├── __init__.py
│   │   └── router.py           # Multi-cloud LLM router
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── events.py           # ReAct event schema
│   │   └── plan.py             # Plan & intent schema
│   ├── api/routes/
│   │   └── agents.py           # REST endpoints
│   └── ...
├── .llm/
│   └── prompts/
│       ├── coordinator.md      # Coordinator system prompt
│       ├── extraction.md       # Extraction system prompt
│       ├── analytics.md        # Analytics system prompt
│       └── report.md           # Report generator prompt
└── demo_agents.py              # Demo script
```

## API Endpoints

### POST `/agents/query`

Submit a new query for analysis.

**Request:**
```json
{
  "query": "What has been the trend in Singapore's tech sector employment?",
  "user_constraints": {
    "allowed_sources": ["singstat", "data.gov.sg"]
  }
}
```

**Response:**
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "query": "...",
  "plan": { ... },
  "status": "awaiting_approval"
}
```

### POST `/agents/approve`

Approve or reject a plan.

**Request:**
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "approved": true,
  "feedback": "Optional feedback if rejected"
}
```

**Response:**
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "approved": true,
  "status": "completed"
}
```

### GET `/agents/run/{run_id}`

Get status and results for a run.

**Response:**
```json
{
  "run_id": "...",
  "status": "completed",
  "plan": { ... },
  "extraction_summary": [ ... ],
  "analytics": { ... }
}
```

### GET `/agents/events/{run_id}`

Get full event trace for observability.

**Response:**
```json
{
  "run_id": "...",
  "events": [
    {
      "agent": "coordinator",
      "phase": "reason",
      "message": "Interpreting user query...",
      "payload": { ... }
    }
  ]
}
```

## Running the Demo

### Prerequisites

**You only need:**
- 🐳 **Docker Desktop** (Windows/Mac) or Docker Engine (Linux)
- 🔑 **API keys** from OpenAI and/or Anthropic (at least one)

**No need to install:**
- ❌ Python
- ❌ Poetry, pip, or any packages
- ❌ PostgreSQL
- ❌ Redis

Everything runs in Docker containers!

---

### Step 1: Get API Keys

You need at least one API key (the system will automatically failover between providers):

#### OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy the key (starts with `sk-...`)

#### Anthropic API Key (Optional but recommended for failover)
1. Go to https://console.anthropic.com/
2. Sign in or create an account
3. Navigate to API Keys
4. Create a new key
5. Copy the key (starts with `sk-ant-...`)

---

### Step 2: Configure API Keys

Navigate to the `infra` directory and create your environment file:

**Windows (CMD):**
```cmd
cd infra
copy .env.example .env
notepad .env
```

**Windows (PowerShell):**
```powershell
cd infra
Copy-Item .env.example .env
notepad .env
```

**Linux/Mac:**
```bash
cd infra
cp .env.example .env
nano .env
```

Edit the `.env` file and paste your API keys:

```env
# LLM API Keys (Required)
# You need at least one. Both recommended for automatic failover.

OPENAI_API_KEY=sk-your-actual-key-here
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```

**Important:**
- Paste your actual API keys after the `=` sign
- You need at least one API key (OpenAI OR Anthropic)
- Having both enables automatic failover
- No quotes needed, no spaces

---

### Step 3: Start the System

From the project root directory:

```cmd
docker-compose -f infra/docker-compose.yml up -d
```

Or if you're already in the `infra` directory:

```cmd
docker-compose up -d
```

This will start:
- ✅ PostgreSQL database
- ✅ Redis cache
- ✅ Backend API with agent system
- ✅ Frontend UI

**Wait 10-15 seconds** for all services to initialize.

---

### Step 4: Verify Everything is Running

Check that all containers are up:

```cmd
docker-compose -f infra/docker-compose.yml ps
```

Expected output:
```
NAME                              STATUS              PORTS
policy-analytics-postgres         Up                  5432/tcp
policy-analytics-redis            Up                  6379/tcp
policy-analytics-api              Up                  0.0.0.0:8000->8000/tcp
policy-analytics-frontend         Up                  0.0.0.0:3000->3000/tcp
```

---

### Step 5: Run the Agent Demo

```cmd
docker-compose -f infra/docker-compose.yml exec api python demo_agents.py
```

Or if you're in the `infra` directory:

```cmd
docker-compose exec api python demo_agents.py
```

You should see output like:

```
================================================================================
 MULTI-AGENT POLICY ANALYTICS DEMO
================================================================================

Query: What has been the trend in Singapore's tech sector employment from 2019 to 2023?

================================================================================
 STEP 1: COORDINATOR - Generate Plan
================================================================================

Run ID: 550e8400-e29b-41d4-a716-446655440000

[Coordinator] Interpreting query...
[Coordinator] Generated plan with 2 data sources, 2 extraction steps, 2 analysis steps

Plan:
{
  "intent": {
    "question": "What has been the trend in Singapore's tech sector employment from 2019 to 2023?",
    "time_range": {"start": "2019", "end": "2023"},
    "entities": ["Singapore", "tech sector"],
    "metrics": ["employment"]
  },
  ...
}

================================================================================
 STEP 2: APPROVAL GATE (HITL)
================================================================================

⏸️  In production, this would PAUSE and wait for human approval via UI/API.
For demo purposes, auto-approving plan...

✓ Plan approved

================================================================================
 STEP 3: EXTRACTION - Fetch & Validate Data
================================================================================

[Extraction] Fetching 2 datasets...
[Extraction] Dataset 1: singstat/employment_by_industry (500 rows, quality: 0.95)
[Extraction] Dataset 2: data.gov.sg/tech_statistics (350 rows, quality: 0.92)

================================================================================
 STEP 4: ANALYTICS - Compute Insights
================================================================================

[Analytics] Computing trend analysis...
[Analytics] Generated 2 insights with full citations

Insight 1: Tech sector employment grew 55% from 2019 to 2023
  Confidence: 0.95
  Evidence: {start: 100000, end: 155000, change: 55000}
  Citations: [Dataset #1: singstat/employment_by_industry]

================================================================================
 ✓ DEMO COMPLETE
================================================================================
```

---

### Step 6: Access the API

Open your browser and go to:

**API Documentation (Interactive):**
http://localhost:8000/docs

**Frontend UI:**
http://localhost:3000

Try making API calls:

```bash
# Submit a query
curl -X POST http://localhost:8000/agents/query \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"What has been the trend in Singapore tech sector employment?\"}"

# Get run status
curl http://localhost:8000/agents/run/{run_id}

# Get event trace
curl http://localhost:8000/agents/events/{run_id}
```

---

### How API Keys Are Passed to Containers

When you run `docker-compose up`, Docker reads the `.env` file in the `infra/` directory and:

1. **Loads environment variables** from `infra/.env`
2. **Passes them to containers** via the `docker-compose.yml` configuration:

```yaml
services:
  api:
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
```

3. **The agent system** (running inside the container) reads these environment variables:

```python
# In app/llm/router.py
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
```

**Verify API keys are loaded:**

```cmd
docker-compose exec api env | grep API_KEY
```

Expected output:
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

---

### Stopping the System

When you're done:

```cmd
docker-compose -f infra/docker-compose.yml down
```

To also remove volumes (database data):

```cmd
docker-compose -f infra/docker-compose.yml down -v
```

---

### Troubleshooting

#### Problem: "Error: One or both API keys are required"

**Solution:** Check your `.env` file:
1. Ensure `.env` exists in `infra/` directory
2. Verify API keys are set correctly (no quotes, no spaces)
3. Restart containers: `docker-compose restart api`

#### Problem: "Container exited with code 1"

**Solution:** Check logs:
```cmd
docker-compose logs api
```

Common issues:
- Missing or invalid API keys
- Database not ready (wait 10 seconds and try again)

#### Problem: "Port 8000 already in use"

**Solution:** Either:
- Stop the service using port 8000
- Or change the port in `docker-compose.yml`:
  ```yaml
  ports:
    - "8001:8000"  # Use port 8001 instead
  ```

#### Problem: API keys not loading

**Solution:**
1. Verify `.env` file location: should be `infra/.env`
2. Check file format (no BOM, Unix line endings)
3. Rebuild containers: `docker-compose up -d --build`

**For more troubleshooting, see [DOCKER_QUICKSTART.md](../DOCKER_QUICKSTART.md)**

Run the demo query with

    docker-compose -f infra/docker-compose.yml exec api python demo_agents.py 

### Expected Output

```
================================================================================
 STEP 1: COORDINATOR - Generate Plan
================================================================================

Run ID: 550e8400-e29b-41d4-a716-446655440000

Generated Plan:
{
  "intent": {
    "question": "What has been the trend in Singapore's tech sector employment from 2019 to 2023?",
    "time_range": {"start": "2019", "end": "2023"},
    "entities": ["Singapore", "tech sector"],
    "metrics": ["employment"]
  },
  "sources": [
    {"name": "singstat", "datasets": ["employment_by_industry"], "format": "api"}
  ],
  ...
}

================================================================================
 STEP 2: APPROVAL GATE (HITL)
================================================================================

In production, this would wait for user approval via UI/API.
For demo, auto-approving plan...

✓ Plan approved

================================================================================
 STEP 3: EXTRACTION & ANALYTICS - Execute Plan
================================================================================

Extraction Summary:
  Dataset 1:
    ID: 1
    Name: singstat_employment_by_industry
    Rows: 500
    Quality Score: 0.95

Analytics Results:
  Insights: 1

  Insight: Tech sector employment grew 55% from 2019 to 2023
    Confidence: 0.95
    Citations: 1
```

## Configuration

### LLM Provider Priority

The system uses multiple LLM providers with automatic failover:

**Primary → Secondary → Template**

Default configuration in `app/llm/router.py`:
```python
llm_router = LLMRouter(
    primary_provider=LLMProvider.OPENAI,      # Try first
    secondary_provider=LLMProvider.ANTHROPIC  # Fallback if primary fails
)
```

If both fail, the system uses template-based responses with warnings.

**To change provider priority:**
1. Edit `backend/app/llm/router.py`
2. Swap `OPENAI` and `ANTHROPIC` to change priority
3. Rebuild container: `docker-compose up -d --build api`

### API Key Management

API keys are stored in `infra/.env`:

```env
OPENAI_API_KEY=sk-your-actual-key
ANTHROPIC_API_KEY=sk-ant-your-actual-key
```

**To update API keys:**
1. Edit `infra/.env` and paste new keys
2. Restart API: `docker-compose restart api`

**To verify keys are loaded:**
```cmd
docker-compose exec api env | grep API_KEY
```

You should see your keys (partially masked for security).

### Agent System Prompts

Customize agent behavior by editing prompts in `.llm/prompts/`:

- `coordinator.md` - How Coordinator interprets queries
- `extraction.md` - Extraction validation rules
- `analytics.md` - Analytics computation guidelines

After editing prompts, restart the API:
```cmd
docker-compose restart api
```

## Acceptance Criteria (from Task)

✅ **Plan Approval Gate**: Hard stop until `approved=true`
✅ **ReAct Events**: Every step emits reason/action/observation/decision
✅ **Citations**: Every insight references dataset IDs
✅ **No LLM Math**: All numbers computed with Python
✅ **Quality Reports**: Extraction emits completeness scores and issues
✅ **Multi-Cloud**: Automatic failover between OpenAI and Anthropic
✅ **Provenance**: Full tracking from source to insight

## Testing

### Unit Tests (Future)

**With Docker:**
```cmd
docker-compose exec api pytest tests/agents/
```

### Integration Tests (Future)

**With Docker:**
```cmd
docker-compose exec api pytest tests/integration/test_agent_workflow.py
```

### Run All Tests

**With Docker:**
```cmd
docker-compose exec api pytest -v
```

## Troubleshooting

### LLM Provider Failures

**Symptom**: Both providers fail

**Solution**:
1. Check API keys are set
2. Verify network connectivity
3. Check provider status pages
4. System falls back to template responses

### Approval Gate Not Working

**Symptom**: Execution proceeds without approval

**Solution**:
1. Verify `plan.approved` is False after interpretation
2. Check `_check_approval()` logic in graph.py
3. Ensure `approve_plan()` is called before `continue_after_approval()`

### Missing Citations

**Symptom**: Insights lack dataset references

**Solution**:
1. Check Analytics agent `_generate_insight()` method
2. Verify extraction results include dataset IDs
3. Review analytics.md system prompt

## Future Enhancements

1. **Persistent Event Store**: Replace in-memory storage with PostgreSQL or Redis
2. **Streaming Events**: WebSocket support for real-time updates
3. **Report Generator Agent**: Fourth agent for final report synthesis
4. **Advanced Failure Handling**: Retry with alternate datasets
5. **Agent Performance Metrics**: Track latency, success rates, LLM costs

## Demo Queries

For a comprehensive list of example queries to test the system, see **[DEMO_QUERIES.md](DEMO_QUERIES.md)**.

### Quick Examples

| Query Type | Example |
|------------|---------|
| Trend Analysis | "What has been the trend in Singapore's tech sector employment from 2019 to 2023?" |
| Comparison | "Compare digital adoption rates across different demographics" |
| Breakdown | "Show employment breakdown by local vs foreign workers in the digital sector" |
| Correlation | "Is there a correlation between AI training completion and employment rates?" |

## References

- Demo queries: [DEMO_QUERIES.md](DEMO_QUERIES.md)
- Task specification: `.llm/tasks/003-agents.md`
- LangGraph docs: https://langchain-ai.github.io/langgraph/
- ReAct paper: https://arxiv.org/abs/2210.03629
