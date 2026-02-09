# Guardrails

Instructions and constraints for AI assistants working on this project.

## Frontend Development Mode

**IMPORTANT**: Before rebuilding the frontend Docker container, check if it's running in development/debug mode.

### How to detect dev mode

The frontend may be running in dev mode if:
1. The `policy-analytics-frontend` container is stopped but other services (api, postgres, redis) are running
2. There's a separate `node:20-alpine` container running with port 3000 mapped
3. The user mentions they're debugging or running in dev mode

### What to do

- **If dev mode is detected**: Do NOT run `docker-compose build frontend` or `docker-compose up frontend`. Instead, inform the user that their dev server should auto-reload with the changes.
- **If unsure**: Ask the user if they're running the frontend in dev mode before rebuilding.

### Dev mode setup (for reference)

See `docs/1_README.md` section "Frontend Debug Mode" for details:
```bash
# Stop production frontend (keep API running)
docker-compose -f infra/docker-compose.yml stop frontend

# Run dev server with hot reload
docker run --rm -it -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://localhost:8000 -v "$(pwd)/frontend:/app" -w /app node:20-alpine sh -c "npm install && npm run dev"
```

In dev mode, changes to frontend source files are automatically picked up - no rebuild needed.

## Code Comments

### What NOT to write

- **Task/ticket references**: Do not add comments like `# Task 320: ...` or `// JIRA-123: ...`. The git history and task management system track this.
- **Obvious comments**: Do not comment what the code clearly does (e.g., `# increment counter` above `counter += 1`)
- **Changelog comments**: Do not add `# Added on 2024-01-15` or similar. Git tracks this.
- **Author comments**: Do not add `# Written by John` or similar.

### What TO write

- **Why, not what**: Explain non-obvious business logic or design decisions
- **Warnings**: Alert about edge cases, gotchas, or important constraints
- **TODOs**: Mark incomplete work that needs follow-up (but prefer creating tasks)
- **Complex algorithms**: Explain the approach for genuinely complex logic
