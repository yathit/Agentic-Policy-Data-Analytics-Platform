# Troubleshooting Guide

## Issue: API Container Failed to Start

### Problem
When running `docker-compose up -d`, the API container failed with error:
```
ModuleNotFoundError: No module named 'langgraph'
```

### Root Cause
The Docker image was built before the agent system dependencies (langgraph, langchain, etc.) were added to `pyproject.toml`. The old cached image didn't include these packages.

### Solution Applied
1. **Updated Dependencies**: Added agent system packages to `backend/pyproject.toml`:
   - `langgraph ^0.0.25`
   - `langchain ^0.1.0`
   - `langchain-openai ^0.0.5`
   - `langchain-anthropic ^0.1.0`
   - `openai ^1.10.0`
   - `anthropic ^0.18.0`
   - `plotly ^5.18.0`
   - `numpy ^1.26.0`

2. **Fixed Build Context Issue**: The `.llm/` directory couldn't be copied during Docker build because it's in the project root, not in `backend/`.

   **Changed from (in Dockerfile):**
   ```dockerfile
   COPY .llm/ ./.llm/
   COPY demo_agents.py ./
   ```

   **To volume mounts (in docker-compose.yml):**
   ```yaml
   volumes:
     - ../backend/app:/app/app
     - ../.llm:/app/.llm              # NEW: Mount prompts directory
     - ../backend/demo_agents.py:/app/demo_agents.py  # NEW: Mount demo script
   ```

   **Benefits:**
   - ✅ No build context issues
   - ✅ Edit prompts without rebuilding
   - ✅ Faster development cycle

3. **Rebuilt Containers**:
   ```cmd
   docker-compose down
   docker-compose up -d --build
   ```

### Verification
After rebuild, all services are healthy:

```cmd
$ docker-compose ps
NAME                        STATUS
policy-analytics-api        Up (healthy)
policy-analytics-frontend   Up
policy-analytics-postgres   Up (healthy)
policy-analytics-redis      Up (healthy)
```

Agent system health check:
```cmd
$ curl http://localhost:8000/agents/health
{
  "status": "healthy",
  "llm_providers": {
    "openai": true,
    "anthropic": true
  },
  "event_store": {
    "runs": 0
  }
}
```

### How to Rebuild When Dependencies Change

If you modify `pyproject.toml` or add new packages:

```cmd
cd infra
docker-compose down
docker-compose up -d --build
```

The `--build` flag forces Docker to rebuild the image with updated dependencies.

---

## Common Issues

### Issue: "Port 8000 already in use"

**Symptoms:**
```
Error: bind: address already in use
```

**Solution:**
Either stop the service using port 8000, or change the port:

```yaml
# In docker-compose.yml
api:
  ports:
    - "8001:8000"  # Use 8001 instead of 8000
```

### Issue: "Cannot connect to Docker daemon"

**Symptoms:**
```
ERROR: Cannot connect to the Docker daemon
```

**Solution:**
1. Make sure Docker Desktop is running
2. On Windows, check Docker Desktop settings → "Use WSL 2 based engine"

### Issue: API Keys Not Loading

**Symptoms:**
```json
{
  "status": "healthy",
  "llm_providers": {
    "openai": false,
    "anthropic": false
  }
}
```

**Solution:**
1. Check `infra/.env` file exists and contains your API keys
2. Verify keys have no quotes or spaces:
   ```env
   OPENAI_API_KEY=sk-your-key
   ANTHROPIC_API_KEY=sk-ant-your-key
   ```
3. Restart API:
   ```cmd
   docker-compose restart api
   ```
4. Verify keys are loaded:
   ```cmd
   docker-compose exec api env | grep API_KEY
   ```

### Issue: Database Connection Error

**Symptoms:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution:**
Wait for PostgreSQL to fully initialize (10-15 seconds on first run):

```cmd
# Check if postgres is healthy
docker-compose ps postgres

# View postgres logs
docker-compose logs postgres
```

### Issue: Container Keeps Restarting

**Check logs:**
```cmd
docker-compose logs api
```

**Common causes:**
- Missing environment variables
- Database not ready
- Port conflicts
- Python syntax errors

**Solution:**
Fix the issue shown in logs, then:
```cmd
docker-compose restart api
```

### Issue: Changes Not Reflected

If code changes aren't showing up:

1. **For app/ directory**: Changes are auto-reloaded (mounted as volume)
2. **For dependencies in pyproject.toml**: Must rebuild
   ```cmd
   docker-compose up -d --build api
   ```
3. **For prompts in .llm/**: Changes are immediate (mounted as volume)
4. **For Dockerfile or docker-compose.yml**: Must rebuild
   ```cmd
   docker-compose down
   docker-compose up -d --build
   ```

---

## Debugging Commands

### View Logs
```cmd
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api

# Last 50 lines
docker-compose logs --tail 50 api
```

### Execute Commands in Container
```cmd
# Run demo
docker-compose exec api python demo_agents.py

# Access Python shell
docker-compose exec api python

# Check environment variables
docker-compose exec api env

# Access bash
docker-compose exec api bash
```

### Inspect Container
```cmd
# List running containers
docker ps

# Inspect container details
docker inspect policy-analytics-api

# Check container resource usage
docker stats
```

### Database Access
```cmd
# Access PostgreSQL
docker-compose exec postgres psql -U user -d imda_policy

# Run SQL query
docker-compose exec postgres psql -U user -d imda_policy -c "SELECT * FROM datasets;"
```

---

## Performance Tips

### Speed Up Builds
Use Docker layer caching by ordering Dockerfile commands from least to most frequently changed:

1. System packages (rarely change)
2. Poetry installation (rarely change)
3. pyproject.toml (changes occasionally)
4. Application code (changes frequently)

### Clean Up Docker
If containers are using too much disk space:

```cmd
# Remove stopped containers and unused images
docker system prune -a

# Remove all volumes (WARNING: deletes data)
docker volume prune
```

### Reduce Container Size
The production Dockerfile already uses:
- Multi-stage builds
- Alpine base images where possible
- Layer optimization

---

## Getting Help

If you're still having issues:

1. Check the logs: `docker-compose logs api`
2. Verify all services are healthy: `docker-compose ps`
3. Test the health endpoint: `curl http://localhost:8000/agents/health`
4. Check the documentation:
   - [DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md)
   - [docs/AGENTS.md](docs/AGENTS.md)
5. Check Docker Desktop dashboard for detailed container info
