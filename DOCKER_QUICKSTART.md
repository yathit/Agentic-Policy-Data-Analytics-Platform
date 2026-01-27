# Docker Quick Start Guide

Get the multi-agent system running in under 5 minutes with Docker - no Python installation required!

## Prerequisites

1. **Docker Desktop** (Windows/Mac): Download from [docker.com](https://www.docker.com/products/docker-desktop/)
   - Or **Docker Engine** (Linux)

2. **API Keys** (at least one):
   - OpenAI: https://platform.openai.com/api-keys
   - Anthropic: https://console.anthropic.com/

## Quick Start

### 1. Set Up Environment Variables

```cmd
cd infra
copy .env.example .env
```

Edit `infra/.env` and paste your API keys:
```env
OPENAI_API_KEY=sk-your-actual-key-here
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```
You need at least one. Both recommended for automatic failover.

### 2. Start Everything

```cmd
docker-compose up -d
```

This starts:
- ✅ PostgreSQL (database)
- ✅ Redis (cache)
- ✅ Backend API (with agents)
- ✅ Frontend UI

### 3. Verify It's Running

**Check status:**
```cmd
docker-compose ps
```

**View logs:**
```cmd
docker-compose logs -f api
```

**Access API docs:**
Open http://localhost:8000/docs

### 4. Run the Demo

```cmd
docker-compose exec api python demo_agents.py
```

Expected output:
```
================================================================================
 STEP 1: COORDINATOR - Generate Plan
================================================================================

Run ID: 550e8400-e29b-41d4-a716-446655440000
...
```

### 5. Test API Endpoints

**Submit a query:**
```cmd
curl -X POST http://localhost:8000/agents/query ^
  -H "Content-Type: application/json" ^
  -d "{\"query\": \"What has been the trend in Singapore tech sector employment?\"}"
```

Or open http://localhost:8000/docs and try the interactive API.

### 6. View Frontend (Optional)

Open http://localhost:3000 in your browser

## Common Commands

### View Logs
```cmd
# All services
docker-compose logs -f

# Just API
docker-compose logs -f api

# Just database
docker-compose logs -f postgres
```

### Restart Services
```cmd
docker-compose restart
```

### Stop Services
```cmd
docker-compose down
```

### Rebuild After Code Changes
```cmd
docker-compose up -d --build
```

### Run Commands Inside Containers
```cmd
# Run demo
docker-compose exec api python demo_agents.py

# Run tests
docker-compose exec api pytest

# Access Python shell
docker-compose exec api python

# Access database
docker-compose exec postgres psql -U user -d imda_policy
```

### Initialize/Reset Database
```cmd
# Run migrations
docker-compose exec api alembic upgrade head

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
docker-compose exec api alembic upgrade head
```

## Troubleshooting

### Ports Already in Use

**Error:** `port is already allocated`

**Solution:** Change ports in `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # Change 8000 to 8001
```

### Container Won't Start

**Check logs:**
```cmd
docker-compose logs api
```

**Common issues:**
- Missing API keys in `.env`
- Database not ready (wait 10 seconds and try again)
- Port conflicts (see above)

### API Keys Not Working

**Verify environment variables:**
```cmd
docker-compose exec api env | grep API_KEY
```

If empty, check:
1. `.env` file exists in `infra/` directory
2. API keys are set correctly
3. Restart containers: `docker-compose restart`

### Database Connection Errors

**Wait for PostgreSQL to be ready:**
```cmd
docker-compose exec postgres pg_isready -U user
```

If not ready, wait a few seconds and try again.

### Clear Everything and Start Fresh

```cmd
# Stop and remove containers, volumes, networks
docker-compose down -v

# Remove images (optional)
docker-compose down --rmi all

# Start fresh
docker-compose up -d --build
```

## Development Workflow

### 1. Code Changes

Edit files in `backend/app/` - changes are automatically reflected due to volume mounting.

### 2. Restart API (if needed)

```cmd
docker-compose restart api
```

### 3. Add New Dependencies

Edit `backend/pyproject.toml` or `backend/requirements.txt`, then:

```cmd
docker-compose up -d --build api
```

### 4. Run Tests

```cmd
docker-compose exec api pytest
```

## File Structure

```
.
├── infra/
│   ├── docker-compose.yml    # Service definitions
│   └── .env                   # Your API keys (create from .env.example)
├── backend/
│   ├── Dockerfile             # Backend container image
│   ├── app/                   # Application code (auto-reloaded)
│   └── demo_agents.py         # Demo script
└── frontend/
    └── Dockerfile             # Frontend container image
```

## Next Steps

1. **Explore the API**: http://localhost:8000/docs
2. **Run the demo**: `docker-compose exec api python demo_agents.py`
3. **View the frontend**: http://localhost:3000
4. **Check agent documentation**: [docs/AGENTS.md](docs/AGENTS.md)

## Benefits of Docker Approach

✅ **No local Python installation** - Everything runs in containers
✅ **Consistent environment** - Same setup on Windows/Mac/Linux
✅ **Easy cleanup** - `docker-compose down` removes everything
✅ **Database included** - PostgreSQL and Redis pre-configured
✅ **Hot reload** - Code changes reflected immediately
✅ **Production-ready** - Same setup for dev and deployment

## Need Help?

- **Docker docs**: https://docs.docker.com/
- **Docker Compose**: https://docs.docker.com/compose/
- **Agent system docs**: [docs/AGENTS.md](docs/AGENTS.md)
- **Windows-specific issues**: [backend/WINDOWS_SETUP.md](backend/WINDOWS_SETUP.md) (for local setup without Docker)
