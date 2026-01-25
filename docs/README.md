# IMDA Agentic Policy Data Analytics Platform — Bootstrap Guide

## Prerequisites

Before running locally, ensure you have:
- Docker Desktop (latest version)
- docker-compose (included with Docker Desktop)
- Git
- (Optional) Python 3.11+ for direct backend testing
- (Optional) Node.js 20+ for direct frontend testing

## Quick Start

### 1. Clone and Setup

```bash
cd /path/to/project
cp infra/.env.example infra/.env
```

### 2. Start All Services

```bash
docker compose -f infra/docker-compose.yml up --build
```

This will start:
- **PostgreSQL** (localhost:5432)
- **Redis** (localhost:6379)
- **API** (localhost:8000)
- **Frontend** (localhost:3000)

All services include health checks and will wait for dependencies to be ready.

### 3. Verify Everything Works

Open your browser to:
- Frontend: [http://localhost:3000](http://localhost:3000) — Should show "Bootstrap OK ✓"
- API Health: [http://localhost:8000/health](http://localhost:8000/health) — Should return `{"status": "ok"}`

Alternatively, use curl:

```bash
curl -s http://localhost:8000/health | jq .
```

## Running Tests

### Backend Tests

```bash
docker compose -f infra/docker-compose.yml exec api pytest -v
```

### Frontend Tests

```bash
docker compose -f infra/docker-compose.yml exec frontend npm test
```

## Stopping Services

### Stop (keep volumes)

```bash
docker compose -f infra/docker-compose.yml down
```

### Stop and Remove Volumes (full reset)

```bash
docker compose -f infra/docker-compose.yml down -v
```

## Useful Commands

### View Logs

```bash
# All services
docker compose -f infra/docker-compose.yml logs -f

# Specific service
docker compose -f infra/docker-compose.yml logs -f api
docker compose -f infra/docker-compose.yml logs -f frontend
```

### Direct Backend Testing (without Docker)

```bash
cd backend
pip install -e .
pytest -v
```

### Direct Frontend Development

```bash
cd frontend
npm install
npm run dev
```

## Environment Variables

See [infra/.env.example](../infra/.env.example) for available configuration options.

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app entry point
│   │   ├── core/config.py          # Configuration
│   │   └── api/routes/health.py    # Health endpoint
│   ├── tests/test_health.py        # Health endpoint tests
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/page.tsx            # Home page
│   │   └── app/layout.tsx          # Root layout
│   ├── Dockerfile
│   ├── next.config.js
│   └── package.json
└── infra/
    ├── docker-compose.yml          # Services orchestration
    ├── .env.example                # Environment template
    └── scripts/seed_db.sh          # Database seeding
```

## Troubleshooting

### Services not starting?

1. Ensure Docker Desktop is running
2. Check available disk space
3. Remove old containers: `docker system prune`
4. Rebuild: `docker compose -f infra/docker-compose.yml up --build --no-cache`

### Port conflicts?

If ports 3000, 8000, 5432, or 6379 are in use:
1. Find what's using the port: `netstat -ano | findstr :8000` (Windows) or `lsof -i :8000` (macOS/Linux)
2. Stop the conflicting service or change ports in `docker-compose.yml`

### API returns 502 Gateway Error?

This typically means the API container is still starting. Wait 10-15 seconds and refresh.

## Next Steps

Once bootstrap is running:
1. Review [.llm/architecture.md](./.llm/architecture.md) for system design
2. Check [.llm/tasks/002-data-sources.md](./.llm/tasks/002-data-sources.md) for next tasks
3. Read agent prompts in [.llm/prompts/](./.llm/prompts/) for AI agent specifications

## Support

For issues or questions:
1. Check logs: `docker compose -f infra/docker-compose.yml logs`
2. Verify all services are healthy: `docker compose -f infra/docker-compose.yml ps`
3. Review this guide's Troubleshooting section
