# TASK-031: Create Docker Compose & Orchestration Config

## Task ID
TASK-031

## Status
COMPLETED

## Title
Create Docker Compose & Orchestration Config

## Description
Create `docker-compose.yml` to orchestrate the Zaza MCP server alongside the PKScreener sidecar container, and create `.claude/settings.docker.json` as a template for users to switch Claude Code to Docker mode.

Docker Compose provides a single-command way to start the full stack (Zaza + PKScreener) with proper volume mounts, environment variables, and container dependencies. The settings template shows users exactly how to configure Claude Code to launch the MCP server via Docker instead of `uv run`.

## Acceptance Criteria

### Functional Requirements
- [ ] `docker-compose.yml` created with two services:
  - `zaza`: builds from Dockerfile (runtime target), `stdin_open: true`, mounts `zaza-cache:/cache` and `/var/run/docker.sock:/var/run/docker.sock:ro`, reads `env_file: .env`, depends on `pkscreener`
  - `pkscreener`: uses `pkjmesra/pkscreener:latest` image, `container_name: pkscreener`, mounts `pkscreener-data` volume, runs `sleep infinity`, `restart: unless-stopped`
- [ ] Named volumes declared: `zaza-cache`, `pkscreener-data`
- [ ] `docker compose up -d` starts both services
- [ ] `docker compose ps` shows both services as running
- [ ] `.claude/settings.docker.json` created with correct `docker run -i --rm` MCP server config
- [ ] Settings template includes cache volume mount, Docker socket mount, and env-file flag

### Non-Functional Requirements
- [ ] **Security**: Docker socket mounted read-only (`:ro`) — sufficient for `docker exec`, prevents container modification
- [ ] **Observability**: No TTY allocation (`-t` not used) — MCP is JSON-RPC, not a terminal
- [ ] **Documentation**: Comments in docker-compose.yml explaining volume mounts and `stdin_open`

## Dependencies
- TASK-030: Dockerfile must exist (compose builds from it)

## Technical Notes

### docker-compose.yml

```yaml
services:
  zaza:
    build:
      context: .
      target: runtime
    stdin_open: true              # -i for MCP stdio transport
    volumes:
      - zaza-cache:/cache         # Persistent cache across restarts
      - /var/run/docker.sock:/var/run/docker.sock:ro  # PKScreener docker exec
    env_file: .env                # REDDIT_CLIENT_ID, FRED_API_KEY, etc.
    depends_on:
      - pkscreener

  pkscreener:
    image: pkjmesra/pkscreener:latest
    container_name: pkscreener
    volumes:
      - pkscreener-data:/PKScreener-main/actions_data
    command: sleep infinity
    restart: unless-stopped

volumes:
  zaza-cache:
  pkscreener-data:
```

### .claude/settings.docker.json

```json
{
  "mcpServers": {
    "zaza": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "zaza-cache:/cache",
        "-v", "/var/run/docker.sock:/var/run/docker.sock:ro",
        "--env-file", ".env",
        "zaza:latest"
      ]
    }
  }
}
```

Users copy this into their `.claude/settings.json` to switch from native `uv run` to Docker mode.

### Key Design Decisions

1. **`stdin_open: true`**: Maps to `docker run -i`. Required for MCP stdio transport — Claude Code sends JSON-RPC requests over stdin and reads responses from stdout.

2. **Docker socket read-only**: The `:ro` mount is sufficient for `docker exec` commands (which is all PKScreener needs). It prevents the Zaza container from creating/deleting containers.

3. **`depends_on` without health check**: Simple ordering — PKScreener starts before Zaza. The `sleep infinity` command means PKScreener is "ready" immediately. If more robust ordering is needed, add a health check in a future iteration.

4. **Named volumes**: `zaza-cache` persists the SQLite-backed diskcache across container restarts. `pkscreener-data` persists PKScreener's action data.

### Implementation Hints
1. Test with `docker compose config` to validate YAML syntax before `docker compose up`
2. If `.env` doesn't exist, `docker compose up` will warn but not fail — env vars will simply be empty (tools degrade gracefully)
3. The `--rm` flag in settings.docker.json means each MCP invocation starts a fresh container — cache persists via the named volume

## Estimated Complexity
**Small** (2-3 hours)

## References
- doc/DOCKER-PLAN.md Sections 3, 4 (docker-compose.yml, settings template)
- [Docker Compose stdin_open](https://docs.docker.com/compose/compose-file/05-services/#stdin_open)
