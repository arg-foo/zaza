# Plan: Dockerize Zaza MCP Server

## Context

Zaza's MCP server communicates with Claude Code over stdin/stdout. Docker fully supports this via `docker run -i` (interactive stdin, no TTY). This plan creates a multi-stage Dockerfile, docker-compose.yml, and supporting files to containerize the entire stack while requiring only one minor code change.

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/zaza/config.py` | **MODIFY** | Add `ZAZA_CACHE_DIR` env var override for cache path |
| `Dockerfile` | CREATE | Multi-stage build (deps → playwright → runtime → dev) |
| `docker-compose.yml` | CREATE | Zaza + PKScreener orchestration |
| `.dockerignore` | CREATE | Exclude .venv, .git, .env, docs from build context |
| `docker/entrypoint.sh` | CREATE | Entrypoint with exec for signal handling |
| `setup-docker.sh` | CREATE | One-command build + verify script |
| `.claude/settings.docker.json` | CREATE | Template for Docker-mode MCP config |

---

## 1. Code Change: `src/zaza/config.py`

Only production code change needed. Make `CACHE_DIR` and `PKSCREENER_CONTAINER` configurable via env vars:

```python
CACHE_DIR = Path(os.getenv("ZAZA_CACHE_DIR", str(Path.home() / ".zaza" / "cache")))
PKSCREENER_CONTAINER = os.getenv("PKSCREENER_CONTAINER", "pkscreener")
```

Non-Docker usage is unaffected (falls back to existing defaults).

---

## 2. Dockerfile (multi-stage)

**Stage 1 — `deps`**: Install uv (from official image), copy `pyproject.toml` + `uv.lock`, run `uv sync --frozen --no-dev`. Optional `BUILD_PROPHET=1` arg adds the forecast extra.

**Stage 2 — `playwright`**: Copy venv from stage 1, run `playwright install-deps chromium && playwright install chromium` to get Chromium binary + system libs.

**Stage 3 — `runtime`** (default target): `python:3.12-slim` base, install only Chromium runtime libs + `docker.io` CLI (for PKScreener `docker exec`), copy venv from stage 1, copy Playwright browsers from stage 2, copy `src/`. Set `PYTHONUNBUFFERED=1`, `ZAZA_CACHE_DIR=/cache`. Estimated size: ~1.0-1.2 GB.

**Stage 4 — `dev`**: Extends runtime, adds dev deps + tests. `docker build --target dev` for CI.

Key decisions:
- `python:3.12-slim` over the 2.5 GB Playwright base image (only need Chromium, not Firefox/WebKit)
- `docker.io` package in container so `docker exec pkscreener ...` works via socket mount — zero code changes to `screener/docker.py`
- `PYTHONUNBUFFERED=1` prevents stdout buffering that would break MCP protocol
- No `-t` (TTY) — MCP is JSON-RPC, not a terminal

---

## 3. docker-compose.yml

```yaml
services:
  zaza:
    build: { context: ., target: runtime }
    stdin_open: true              # -i for MCP stdio
    volumes:
      - zaza-cache:/cache
      - /var/run/docker.sock:/var/run/docker.sock:ro
    env_file: .env
    depends_on: [pkscreener]

  pkscreener:
    image: pkjmesra/pkscreener:latest
    container_name: pkscreener
    volumes: [pkscreener-data:/PKScreener-main/actions_data]
    command: sleep infinity
    restart: unless-stopped
```

Docker socket is mounted read-only — sufficient for `docker exec`.

---

## 4. Claude Code Settings Template (`.claude/settings.docker.json`)

```json
{
  "mcpServers": {
    "zaza": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
               "-v", "zaza-cache:/cache",
               "-v", "/var/run/docker.sock:/var/run/docker.sock:ro",
               "--env-file", ".env",
               "zaza:latest"]
    }
  }
}
```

Users copy this into `.claude/settings.json` to switch to Docker mode.

---

## 5. setup-docker.sh

Automates: check Docker → create .env → build image → start PKScreener → verify `--check`.

---

## 6. .dockerignore

Excludes: `.git/`, `.venv/`, `__pycache__/`, `.env`, `doc/`, `CLAUDE.md`, `ZAZA_ARCHITECTURE.md`, `.claude/`, `.coverage`, `.pytest_cache/`. Keeps `uv.lock` (reproducible builds) and `tests/` (dev target needs them).

---

## Tool Compatibility in Docker

### Works out of the box (HTTP calls + pure computation)

| Domain | Tools | Why it works |
|--------|-------|-------------|
| **Finance** (15) | prices, statements, ratios, news, filings, etc. | yfinance + httpx → outbound HTTP, Docker handles networking |
| **TA** (9) | moving averages, momentum, volatility, patterns, etc. | yfinance fetch + pandas/ta computation → no system deps |
| **Options** (7) | chains, IV, flow, max pain, GEX, etc. | yfinance → outbound HTTP |
| **Quantitative** (6) | ARIMA, GARCH, Monte Carlo, distribution, etc. | statsmodels/scipy/arch/numpy → pure computation |
| **Institutional** (4) | short interest, holdings, flows, dark pool | yfinance + httpx (EDGAR, FINRA scraping) → outbound HTTP |
| **Earnings** (4) | history, calendar, events, buybacks | yfinance → outbound HTTP |
| **Backtesting** (4) | signal test, simulation, scoring, risk | Pure computation on historical data |
| **Macro** (5) | yields, indices, commodities, calendar, correlations | yfinance + httpx (FRED) → outbound HTTP |

**Total: 54/66 tools — zero special handling needed.**

### Needs env vars (but otherwise works)

| Domain | Tools | Requirement |
|--------|-------|------------|
| **Sentiment** (4) | news, social, insider, fear/greed | `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` for social sentiment (passed via `--env-file .env`). News/insider/fear_greed work without keys. |
| **Macro** (1 of 5) | economic calendar | `FRED_API_KEY` for FRED data (passed via `--env-file .env`). Falls back gracefully if absent. |

### Needs Docker socket mount (addressed in plan)

| Domain | Tools | Solution |
|--------|-------|---------|
| **Screener** (3) | screen_stocks, get_screening_strategies, get_buy_sell_levels | Uses `docker exec pkscreener ...` via `asyncio.create_subprocess_exec`. Requires: (1) `docker.io` CLI installed in container, (2) `/var/run/docker.sock` mounted read-only. **Zero code changes** — existing `screener/docker.py` works as-is. |

### Needs Playwright + Chromium (addressed in plan)

| Domain | Tools | Solution |
|--------|-------|---------|
| **Browser** (5) | navigate, snapshot, act, read, close | Uses `playwright.chromium.launch(headless=True)`. Requires: (1) Chromium binary (`playwright install chromium`), (2) ~30 system libs (libnss3, libx11, fonts, etc.). Handled by multi-stage build — Stage 2 installs Chromium + deps, Stage 3 copies the binary and installs runtime libs only. |

### Cache (addressed in plan)

All 66 tools use `CACHE_DIR` from `config.py` for file-based JSON caching. In Docker, `ZAZA_CACHE_DIR=/cache` maps to a named volume (`zaza-cache:/cache`), persisting across container restarts. The one code change in `config.py` handles this.

### Summary

- **54 tools**: Work as-is (HTTP + computation)
- **5 tools**: Need env vars passed at runtime (already planned via `--env-file .env`)
- **3 tools**: Need Docker socket mount (already planned)
- **5 tools**: Need Playwright/Chromium in image (already planned via multi-stage build)
- **Code changes**: 1 file (`config.py`) — 2 lines

---

## Implementation Order

1. Modify `config.py` (env var overrides)
2. Create `.dockerignore`
3. Create `docker/entrypoint.sh`
4. Create `Dockerfile`
5. Create `docker-compose.yml`
6. Create `setup-docker.sh`
7. Create `.claude/settings.docker.json`
8. Run tests to verify config change doesn't break anything

---

## Verification

1. `docker build --target runtime -t zaza .` — builds successfully
2. `docker run --rm zaza python -m zaza.server --check` — health check passes
3. `echo '{}' | docker run -i --rm zaza` — stdin/stdout pipe works
4. `docker build --target dev -t zaza-dev . && docker run --rm zaza-dev` — tests pass
5. `docker compose up -d && docker compose ps` — both services running
6. Existing `uv run pytest tests/` still passes (config change backward-compatible)
