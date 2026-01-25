# Task 001 — Bootstrap (Repo Skeleton + Local Dev)

## Goal
Get a clean mono-repo skeleton running locally via Docker Compose with:
- Backend API up with a health endpoint
- Frontend up with a placeholder page
- Postgres + Redis running
- Basic lint/test commands wired (can be no-op placeholders initially)
- Minimal docs so reviewers can run in <5 minutes

---

## Deliverables

### Repo structure
```

/backend
	pyproject.toml
	app/
		main.py
		core/
			config.py
		api/
			routes/
				health.py
	tests/
		test_health.py
	Dockerfile

/frontend
	package.json
	next.config.js
	src/
		app/
			page.tsx
	Dockerfile

/infra
	docker-compose.yml
	.env.example
	scripts/
		seed_db.sh

/docs
	README.md

/.llm
	plan.md
	architecture.md
	prompts/
		coordinator.md
		extraction.md
		analytics.md
		report.md
	tasks/
		001-bootstrap.md
		002-data-sources.md
		003-agents.md
		004-api.md
		005-ui.md
		006-tests.md
	contracts/
		api.yaml
		db-schema.sql
	decisions/
		0001-llm-router.md
		0002-agent-framewor


---

## Acceptance Criteria (Must Pass)

### A) One-command local run
- `docker compose -f infra/docker-compose.yml up --build`
- Services start without manual steps:
  - `postgres` healthy
  - `redis` healthy
  - `api` healthy
  - `frontend` reachable

### B) Backend health endpoint
- `GET http://localhost:8000/health` returns:
```json
{ "status": "ok" }
````

### C) Frontend placeholder

* `http://localhost:3000/` renders a placeholder (e.g. “IMDA GenAI Demo — Bootstrap OK”)

### D) Basic tests run

* Backend: `pytest` contains at least one passing test (`/health`)
* Frontend: `npm test` exists (can be a placeholder that succeeds)

### E) Minimal documentation

* `/docs/README.md` includes:

  * prerequisites
  * how to run locally
  * how to run tests
  * how to stop and reset

---

## Implementation Plan

### 1) Infra

* `/infra/docker-compose.yml`

  * postgres:16
  * redis:7
  * api (FastAPI)
  * frontend (Next.js)
* `/infra/.env.example`
* `/infra/scripts/seed_db.sh` (placeholder)

### 2) Backend

* FastAPI app with `/health`
* Dockerfile using `uvicorn`
* Pytest health test

### 3) Frontend

* Minimal Next.js app
* Placeholder landing page
* Dockerfile with build + start

### 4) Docs

* `/docs/README.md` runbook

---

## Commands

### Start

```bash
cp infra/.env.example infra/.env
docker compose -f infra/docker-compose.yml up --build
```

### Verify

```bash
curl -s http://localhost:8000/health
```

### Stop

```bash
docker compose -f infra/docker-compose.yml down
```

### Reset (remove volumes)

```bash
docker compose -f infra/docker-compose.yml down -v
```

### Tests

```bash
docker compose -f infra/docker-compose.yml exec api pytest -q
docker compose -f infra/docker-compose.yml exec frontend npm test
```

---

## Notes

* No agent logic, DB migrations, or real data sources in this task.
* Keep bootstrap deterministic and reviewer-friendly.
* Optimize for fast local setup over completeness.



