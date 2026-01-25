# AI Agent Instructions — Agentic Policy Data Analytics Platform

## 🎯 Project Overview

This is a **full-stack agentic analytics platform** answering policy research questions via multi-agent orchestration. Architecture: Next.js frontend → FastAPI backend → Celery workers executing a ReAct-based agent graph (Coordinator → Extraction → Analytics) pulling from government data sources.

**Core design principle:** LLMs for interpretation/narration only; all numeric computation in Python. Events persisted for reproducibility and auditability.

---

## 📚 Reference Documentation

- **Architecture deep-dive:** [`.llm/architecture.md`](./.llm/architecture.md) — read this for system design, data flows, and why decisions were made.
- **Scope & tech stack:** [`.llm/plan.md`](./.llm/plan.md) — success criteria and allowed technologies.
- **Task specifications:** [`.llm/tasks/`](./.llm/tasks/) — current work breakdown.
- **Agent prompts:** [`.llm/prompts/`](./.llm/prompts/) — system prompts for each agent.
- **API contracts:** [`.llm/contracts/api.yaml`](./.llm/contracts/api.yaml) (if present).

---

## 🤖 AI Agent Quick Start

1. **Understand the big picture:** Read `.llm/architecture.md` 
2. **Check the current task:** Find the relevant file in `.llm/tasks/` 
3. **Locate the code:** Navigate to `backend/app/` or `frontend/src/` using the structure above.
4. **Follow patterns:** Copy the structure of existing agents/connectors/tests.
5. **Test before commit:** Run `pytest` or `npm test` locally.
6. **Emit events:** If adding agent logic, ensure ReAct events are emitted.
7. **Document decisions:** Add comments explaining non-obvious choices (e.g., why a fallback is needed).

