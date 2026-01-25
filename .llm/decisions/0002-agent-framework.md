# ADR 0002 — Agent Framework & ReAct

## Status
Accepted

## Context
The system uses a multi-agent orchestration pattern to handle complex policy analytics queries. We need:
1. A framework for coordinating multiple specialized agents
2. Transparent reasoning loops (ReAct) for auditability
3. Event streaming for real-time UI updates
4. Graceful error recovery and fallback strategies

## Decision
Use **LangGraph** (LangChain's agentic orchestration framework) with explicit **ReAct loops** and event emission:

### Agent Structure
- **Coordinator:** Plans and delegates; emits `thought`, `action`, `observation`, `decision` events
- **Extraction:** Fetches and cleans data; emits validation and lineage events
- **Analytics:** Computes statistics; emits evidence-linked insights
- **Report:** Synthesizes findings; emits final artifact metadata

### Event Model
Each agent step emits a JSON event:
```json
{
  "run_id": "uuid",
  "agent": "coordinator|extraction|analytics|report",
  "event_type": "thought|action|observation|decision",
  "content": {
    "text": "...",
    "reasoning": "...",
    "tool_call": {...},
    "result": {...}
  },
  "timestamp": "ISO 8601"
}
```

### Graph Topology
```
User Query
    ↓
[Coordinator Plan]
    ↓
Human Review Gate (approve/abort)
    ↓
[Extraction Agent]
    ↓
[Analytics Agent]
    ↓
[Report Generator]
    ↓
Result/Export
```

## Rationale
- **LangGraph:** Purpose-built for agentic workflows; clean API for graph definition
- **ReAct events:** Provides transparency and auditability; enables reproducibility
- **Human gate:** Aligns with AI governance framework (bounded autonomy + oversight)
- **Async streaming:** Real-time UI updates without blocking analysis

## Consequences
- Dependency on LangChain ecosystem (mitigated by clean abstraction layer)
- Event volume can be large (~100s per run); efficient DB indexing required
- Requires async/await throughout; more complex debugging
- ReAct loops add latency (~10-20% overhead) but acceptable for policy context

## Notes
- Events are append-only; immutable audit trail
- Partial failures: if extraction fails on one source, Analytics proceeds with partial data + warning
- Fallback: if Analytics Agent fails, use simpler rule-based insights (documented)
- Future: Add agent introspection (e.g., "explain why you chose source X")
