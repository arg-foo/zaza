# TASK-030: Create Multi-Stage Dockerfile

## Task ID
TASK-030

## Status
COMPLETED

## Title
Create Multi-Stage Dockerfile

## Description
Create the Dockerfile that containerizes the Zaza MCP server using a multi-stage build strategy. The image must support all 66 MCP tools: HTTP-based tools (yfinance, EDGAR, scraping), computation tools (pandas, statsmodels, GARCH), Playwright browser automation (Chromium), and PKScreener Docker-in-Docker exec.

The multi-stage approach minimizes image size by separating dependency installation, Playwright browser setup, and runtime. A `dev` target is also provided for CI/testing.

This task also creates `.dockerignore` and `docker/entrypoint.sh`, which are prerequisites for the Dockerfile.

## Acceptance Criteria

### Functional Requirements
- [ ] `.dockerignore` created — excludes `.git/`, `.venv/`, `__pycache__/`, `.env`, `doc/`, `CLAUDE.md`, `ZAZA_ARCHITECTURE.md`, `.claude/`, `.coverage`, `.pytest_cache/`; includes `uv.lock` and `tests/`
- [ ] `docker/entrypoint.sh` created — uses `exec "$@"` pattern for proper signal forwarding
- [ ] `Dockerfile` created with 4 stages:
  - **Stage 1 (`deps`)**: `python:3.12-slim` base, install `uv` from official image, copy `pyproject.toml` + `uv.lock`, run `uv sync --frozen --no-dev`; optional `BUILD_PROPHET=1` arg for forecast extra
  - **Stage 2 (`playwright`)**: Copy venv from stage 1, run `playwright install-deps chromium && playwright install chromium`
  - **Stage 3 (`runtime`)**: `python:3.12-slim` base, install Chromium runtime libs + `docker.io` CLI, copy venv from stage 1, copy Playwright browsers from stage 2, copy `src/`, set `PYTHONUNBUFFERED=1` and `ZAZA_CACHE_DIR=/cache`
  - **Stage 4 (`dev`)**: Extends runtime, adds dev deps (`uv sync --frozen`), copies `tests/`
- [ ] `docker build --target runtime -t zaza .` succeeds
- [ ] `docker build --target dev -t zaza-dev .` succeeds
- [ ] `docker run --rm zaza python -m zaza.server --check` passes health check
- [ ] Runtime image size is under 1.5 GB

### Non-Functional Requirements
- [ ] **Performance**: Layer caching optimized — `pyproject.toml` + `uv.lock` copied before `src/` so dependency layer is cached when only code changes
- [ ] **Security**: No secrets baked into image; no `.env` in build context
- [ ] **Security**: Non-root user for runtime (optional but recommended)
- [ ] **Observability**: `PYTHONUNBUFFERED=1` set so logs appear immediately
- [ ] **Documentation**: Comments in Dockerfile explaining each stage and key decisions

## Dependencies
- TASK-029: Config env var overrides (`ZAZA_CACHE_DIR` must work for runtime stage)
- TASK-001: Project scaffolding (pyproject.toml, uv.lock must exist)

## Technical Notes

### .dockerignore

```
.git/
.venv/
__pycache__/
*.pyc
.env
.env.*
doc/
CLAUDE.md
ZAZA_ARCHITECTURE.md
.claude/
.coverage
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
build/
```

### docker/entrypoint.sh

```bash
#!/bin/sh
set -e
exec "$@"
```

The `exec` replaces the shell process so PID 1 is the Python process, enabling proper SIGTERM handling for graceful shutdown.

### Dockerfile Structure

```dockerfile
# Stage 1: Install Python dependencies
FROM python:3.12-slim AS deps

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

ARG BUILD_PROPHET=0
RUN if [ "$BUILD_PROPHET" = "1" ]; then \
      uv sync --frozen --no-dev --extra forecast; \
    else \
      uv sync --frozen --no-dev; \
    fi

# Stage 2: Install Playwright Chromium
FROM deps AS playwright

RUN uv run playwright install-deps chromium \
 && uv run playwright install chromium

# Stage 3: Runtime image
FROM python:3.12-slim AS runtime

# Chromium runtime libs + Docker CLI for PKScreener
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libx11-6 libx11-xcb1 libxcomposite1 libxcursor1 \
    libxdamage1 libxfixes3 libxi6 libxrandr2 libxrender1 \
    libxtst6 libglib2.0-0 libasound2 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libpango-1.0-0 \
    libcairo2 fonts-liberation libxss1 docker.io \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy venv from deps stage
COPY --from=deps /app/.venv /app/.venv
# Copy Playwright browsers from playwright stage
COPY --from=playwright /root/.cache/ms-playwright /root/.cache/ms-playwright

# Copy application code
COPY src/ src/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV ZAZA_CACHE_DIR=/cache

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "zaza.server"]

# Stage 4: Development image
FROM runtime AS dev

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY tests/ tests/
CMD ["python", "-m", "pytest", "tests/"]
```

### Key Design Decisions

1. **`python:3.12-slim` over Playwright base image**: The full Playwright image is ~2.5 GB and includes Firefox + WebKit we don't need. Installing only Chromium runtime libs on slim saves ~1.3 GB.

2. **`docker.io` CLI in container**: The PKScreener tools use `asyncio.create_subprocess_exec("docker", "exec", ...)`. Installing the Docker CLI and mounting the host socket lets this work with zero code changes.

3. **`PYTHONUNBUFFERED=1`**: Critical for MCP. Python's default stdout buffering would delay JSON-RPC responses and break the protocol.

4. **No `-t` (TTY)**: MCP is JSON-RPC over stdin/stdout, not an interactive terminal. The container must be run with `-i` (interactive stdin) but NOT `-t`.

5. **Layer caching**: `pyproject.toml` + `uv.lock` are copied before `src/` so the expensive dependency install layer is cached when only application code changes.

### Implementation Hints
1. Test the Chromium runtime lib list by running `ldd` on the Chromium binary in the playwright stage — if you get missing `.so` errors at runtime, add the missing lib package
2. The `uv` binary must be copied from the official image, not pip-installed
3. Playwright browser path may vary — check `PLAYWRIGHT_BROWSERS_PATH` if the copy path doesn't work
4. Use `--no-install-recommends` with `apt-get` to minimize image bloat

## Estimated Complexity
**Medium** (4-6 hours)

## References
- doc/DOCKER-PLAN.md Sections 2, 6 (Dockerfile, .dockerignore)
- [uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/)
- [Playwright Docker guide](https://playwright.dev/python/docs/docker)
