# Agentic Policy Data Analytics Platform - Local Development Guide

## Overview

This is a GenAI-powered policy data analytics and reporting platform built with:
- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: Next.js 14 (React, TypeScript, Tailwind CSS)
- **Database**: PostgreSQL 16
- **Cache**: Redis 7
- **Orchestration**: Docker Compose

## Prerequisites

Before running the application locally, ensure you have the following installed:

1. **Docker Desktop** (v24.0 or later)
   - [Download for Windows](https://www.docker.com/products/docker-desktop/)
   - [Download for Mac](https://www.docker.com/products/docker-desktop/)
   - [Download for Linux](https://docs.docker.com/desktop/install/linux-install/)

2. **Git** (for cloning the repository)
   - [Download Git](https://git-scm.com/downloads)

3. **Minimum System Requirements**:
   - 4GB RAM
   - 10GB free disk space
   - Internet connection for pulling Docker images

## Quick Start (< 5 minutes)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Agentic-Policy-Data-Analytics-Platform
```

### 2. Set Up Environment Variables

```bash
cp infra/.env.example infra/.env
```

The default `.env` file contains only LLM API keys. Database and Redis
settings are provided via defaults in `infra/docker-compose.yml`.
```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

### 3. Start All Services

```bash
docker compose -f infra/docker-compose.yml up --build
```

This command will:
- Pull required Docker images (PostgreSQL, Redis, Node, Python)
- Build the backend and frontend containers
- Start all services with health checks
- Set up networking between services

**First run** may take 5-10 minutes depending on your internet connection.

### 4. Verify Services

Once all services are running, verify them:

#### Backend API Health Check
```bash
curl http://localhost:8000/health
```
Expected response:
```json
{"status": "ok"}
```

#### Frontend
Open your browser and navigate to:
```
http://localhost:3000
```

You should see the landing page with "Agentic Policy Data Analytics Platform".

#### API Documentation
FastAPI automatically generates interactive API docs:
```
http://localhost:8000/docs
```

## Running Tests

### Backend Tests (pytest)

Run tests inside the API container:
```bash
docker compose -f infra/docker-compose.yml exec api pytest -v
```

To run with coverage:
```bash
docker compose -f infra/docker-compose.yml exec api pytest --cov=app tests/
```

### Frontend Tests (npm)

Run tests inside the frontend container:
```bash
docker compose -f infra/docker-compose.yml exec frontend npm test
```

Note: Frontend tests are currently placeholder and will be implemented in later tasks.

## Development Workflow

### Viewing Logs

View logs for all services:
```bash
docker compose -f infra/docker-compose.yml logs -f
```

View logs for a specific service:
```bash
docker compose -f infra/docker-compose.yml logs -f api
docker compose -f infra/docker-compose.yml logs -f frontend
docker compose -f infra/docker-compose.yml logs -f postgres
docker compose -f infra/docker-compose.yml logs -f redis
```

### Accessing Service Shells

Backend (Python):
```bash
docker compose -f infra/docker-compose.yml exec api /bin/bash
```

Frontend (Node):
```bash
docker compose -f infra/docker-compose.yml exec frontend /bin/sh
```

Database (PostgreSQL):
```bash
docker compose -f infra/docker-compose.yml exec postgres psql -U user -d imda_policy
```

Redis CLI:
```bash
docker compose -f infra/docker-compose.yml exec redis redis-cli
```

### Code Changes

- **Backend**: Changes to Python files are auto-reloaded thanks to `uvicorn --reload`
- **Frontend**: Changes trigger Next.js hot reload automatically
- No container restart needed for code changes!

### Installing New Dependencies

#### Backend (Python/Poetry)
```bash
docker compose -f infra/docker-compose.yml exec api poetry add <package-name>
docker compose -f infra/docker-compose.yml restart api
```

#### Frontend (npm)
```bash
docker compose -f infra/docker-compose.yml exec frontend npm install <package-name>
docker compose -f infra/docker-compose.yml restart frontend
```

## Stopping and Resetting

### Stop All Services

```bash
docker compose -f infra/docker-compose.yml down
```

This stops and removes all containers but preserves data in volumes.

### Reset Everything (Remove Volumes)

**Warning**: This will delete all data in the database!

```bash
docker compose -f infra/docker-compose.yml down -v
```

This removes:
- All containers
- All volumes (PostgreSQL data, Redis data)
- Networks

### Rebuild Containers

If you make changes to Dockerfiles or dependencies:
```bash
docker compose -f infra/docker-compose.yml up --build
```

To rebuild a specific service:
```bash
docker compose -f infra/docker-compose.yml up --build api
```

## Service Endpoints

| Service    | URL                        | Description                |
|------------|----------------------------|----------------------------|
| Frontend   | http://localhost:3000      | Next.js web application    |
| Backend    | http://localhost:8000      | FastAPI REST API           |
| API Docs   | http://localhost:8000/docs | Swagger UI                 |
| PostgreSQL | localhost:5432             | Database (internal)        |
| Redis      | localhost:6379             | Cache (internal)           |

## Troubleshooting

### Port Already in Use

If you see "port already in use" errors:

1. Check what's using the port:
```bash
# Windows
netstat -ano | findstr :8000

# Mac/Linux
lsof -i :8000
```

2. Stop the conflicting service or change the port in `docker-compose.yml`

### Services Not Starting

Check service health:
```bash
docker compose -f infra/docker-compose.yml ps
```

View detailed logs:
```bash
docker compose -f infra/docker-compose.yml logs
```

### Database Connection Issues

Ensure PostgreSQL is healthy:
```bash
docker compose -f infra/docker-compose.yml exec postgres pg_isready -U user
```

### Frontend Build Errors

Clear Next.js cache:
```bash
docker compose -f infra/docker-compose.yml exec frontend rm -rf .next
docker compose -f infra/docker-compose.yml restart frontend
```

### Complete Reset

If all else fails:
```bash
docker compose -f infra/docker-compose.yml down -v
docker system prune -a
docker compose -f infra/docker-compose.yml up --build
```

## Frontend Debug Mode (Docker, no build)

Use this when you want Next.js to run in dev mode (no production build, hot reload).

1. Stop the production frontend container (keep API running):
```bash
docker-compose -f infra/docker-compose.yml stop frontend
```

2. Run the frontend dev server in Docker:
```bash
docker run --rm -it -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://localhost:8000 -v "$(pwd)/frontend:/app" -w /app node:20-alpine sh -c "npm install && npm run dev"
```

Notes:
- This uses the local `frontend/` source directly (no compiled build).
- Keep `docker compose -f infra/docker-compose.yml up` running for the API/DB/Redis.

## Project Structure

```
Agentic-Policy-Data-Analytics-Platform/
|-- backend/                  # FastAPI application
|   |-- app/
|   |   |-- main.py            # FastAPI app entry point
|   |   |-- core/
|   |   |   `-- config.py      # Configuration settings
|   |   `-- api/
|   |       `-- routes/
|   |           `-- health.py  # Health check endpoint
|   |-- tests/                 # Pytest tests
|   |-- pyproject.toml         # Python dependencies
|   `-- Dockerfile
|-- frontend/                  # Next.js application
|   |-- src/
|   |   `-- app/
|   |       |-- page.tsx       # Landing page
|   |       |-- layout.tsx     # Root layout
|   |       `-- globals.css    # Global styles
|   |-- package.json           # Node dependencies
|   |-- next.config.js         # Next.js configuration
|   `-- Dockerfile
|-- infra/                     # Infrastructure
|   |-- docker-compose.yml     # Service orchestration
|   |-- .env.example           # Environment template
|   |-- .env                   # Local environment (git-ignored)
|   `-- scripts/
|       `-- seed_db.sh         # Database seeding (placeholder)
|-- docs/                      # Documentation
|   |-- 1_README.md            # This file
|   |-- 2_ARCHITECTURE.md
|   |-- 3_AGENTS.md
|   |-- 4_DATA_SOURCES.md
|   `-- 5_DEMO_QUERIES.md
|-- .llm/                      # AI agent configuration
|   |-- plan.md
|   |-- prompts/
|   `-- tasks/                 # Task definitions
`-- README.md                  # Root project README
```

## Next Steps

After successfully running the bootstrap:

1. **Task 002**: Implement data source integrations
2. **Task 003**: Build AI agent orchestration
3. **Task 004**: Develop API endpoints
4. **Task 005**: Create UI components
5. **Task 006**: Add comprehensive tests

## Support

For issues or questions:
- Check logs: `docker compose -f infra/docker-compose.yml logs`
- Review troubleshooting section above
- Contact the development team

## License

See [LICENSE](../LICENSE) file for details.
