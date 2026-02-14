# TASK-001: Project Scaffolding & Package Configuration

## Task ID
TASK-001

## Status
COMPLETED

## Title
Project Scaffolding & Package Configuration

## Description
Set up the foundational project structure for the Zaza MCP server. This includes the Python package layout, pyproject.toml with all dependencies, the `__init__.py` files for all subpackages, `.env.example` for environment variables, and the `.claude/settings.json` MCP server configuration.

This is the first task — everything else depends on the package structure being in place.

## Acceptance Criteria

### Functional Requirements
- [ ] `pyproject.toml` created with all dependencies: `mcp`, `yfinance`, `pandas`, `ta`, `statsmodels`, `arch`, `prophet`, `scipy`, `numpy`, `praw`, `playwright`, `httpx`, `beautifulsoup4`
- [ ] Dev dependencies: `pytest`, `pytest-asyncio`, `ruff`, `mypy`
- [ ] Package name: `zaza`, entry point: `python -m zaza.server`
- [ ] Directory structure created per architecture: `src/zaza/`, `src/zaza/api/`, `src/zaza/cache/`, `src/zaza/tools/` (with all 11 subdirectories), `src/zaza/utils/`, `tests/`, `tests/tools/`
- [ ] All `__init__.py` files created (can be empty initially)
- [ ] `.env.example` with `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `FRED_API_KEY`
- [ ] `.claude/settings.json` with MCP server configuration pointing to `uv run python -m zaza.server`
- [ ] `src/zaza/__main__.py` created to support `python -m zaza.server`
- [ ] `uv sync` runs successfully
- [ ] `uv run python -c "import zaza"` works

### Non-Functional Requirements
- [ ] **Testing**: `uv run pytest tests/` runs (even with no tests yet)
- [ ] **Lint**: `uv run ruff check src/ tests/` passes
- [ ] **Type checking**: `uv run mypy src/` passes (with empty modules)
- [ ] **Documentation**: pyproject.toml includes project metadata (name, version, description, python-requires)

## Dependencies
None — this is the root task.

## Technical Notes

### pyproject.toml
```toml
[project]
name = "zaza"
version = "0.1.0"
description = "Financial research MCP server for Claude Code"
requires-python = ">=3.12"
dependencies = [
    "mcp>=1.0",
    "yfinance>=0.2.30",
    "pandas>=2.0",
    "ta>=0.11",
    "statsmodels>=0.14",
    "arch>=6.0",
    "prophet>=1.1",
    "scipy>=1.11",
    "numpy>=1.26",
    "praw>=7.7",
    "playwright>=1.40",
    "httpx>=0.25",
    "beautifulsoup4>=4.12",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-asyncio>=0.21",
    "ruff>=0.1",
    "mypy>=1.7",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/zaza"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = false
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Directory structure
```
src/zaza/
├── __init__.py
├── __main__.py
├── server.py          (stub)
├── config.py          (stub)
├── api/
│   └── __init__.py
├── cache/
│   └── __init__.py
├── tools/
│   ├── __init__.py
│   ├── finance/__init__.py
│   ├── ta/__init__.py
│   ├── options/__init__.py
│   ├── sentiment/__init__.py
│   ├── macro/__init__.py
│   ├── quantitative/__init__.py
│   ├── institutional/__init__.py
│   ├── earnings/__init__.py
│   ├── backtesting/__init__.py
│   ├── screener/__init__.py
│   └── browser/__init__.py
└── utils/
    └── __init__.py
```

### .claude/settings.json
```json
{
  "mcpServers": {
    "zaza": {
      "command": "uv",
      "args": ["run", "--directory", ".", "python", "-m", "zaza.server"]
    }
  }
}
```

### Implementation Hints
1. Use `hatchling` as the build backend for `src/` layout support
2. The `__main__.py` should import and run `server.main()`
3. Keep all stub files minimal — just enough for imports to work
4. The `.env.example` documents optional keys only; core tools (yfinance, EDGAR) need no keys

## Estimated Complexity
**Small** (2-3 hours)

## References
- ZAZA_ARCHITECTURE.md Section 4 (Project Structure)
- ZAZA_ARCHITECTURE.md Section 13 (Configuration & Setup)
