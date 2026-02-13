# TASK-023: PKScreener Docker Integration & Screener Tools

## Task ID
TASK-023

## Status
PENDING

## Title
Implement PKScreener Docker Integration & Screener Tools

## Description
Implement the Docker client for PKScreener (`src/zaza/tools/screener/docker.py`) and 3 stock discovery MCP tools: `screen_stocks`, `get_screening_strategies`, and `get_buy_sell_levels`. PKScreener runs as a long-lived Docker container; communication is via `docker exec` with CLI arguments.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/tools/screener/docker.py` — `run_pkscreener(args, timeout=120) -> str`:
  - Executes commands inside the `pkscreener` Docker container via `subprocess.run`
  - Handles container-not-running errors gracefully
  - Configurable timeout (screening can take 30-60 seconds)
- [ ] `src/zaza/tools/screener/pkscreener.py`:
  - `screen_stocks(scan_type, market="NASDAQ", filters=None)` — runs PKScreener scan, parses text output to JSON
    - Supported scan types: breakout, momentum, consolidation, volume, reversal, VCP, NR4/NR7, chart patterns, RSI/MACD/CCI signals, golden/death cross
  - `get_screening_strategies()` — returns hardcoded list of available scan types with descriptions (no container call needed)
  - `get_buy_sell_levels(ticker)` — single-ticker analysis via PKScreener, returns S/R levels, breakout price, stop-loss
- [ ] PKScreener CLI argument mapping implemented:
  - Breakout: `-a Y -o X:12:10 -e`
  - Momentum: `-a Y -o X:12:31 -e`
  - Single ticker: `-a Y -o X:12:0:{ticker} -e`
- [ ] Text/tabular output from PKScreener parsed to structured JSON
- [ ] All 3 tools registered via `register_screener_tools(app)`
- [ ] No Zaza-level caching (PKScreener manages its own cache)

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with mocked `subprocess.run`; test output parsing with sample PKScreener outputs
- [ ] **Reliability**: Clear error message when Docker container is not running
- [ ] **Observability**: Log PKScreener commands, execution time, and output size
- [ ] **Security**: Validate scan_type against allowed list to prevent command injection

## Dependencies
- TASK-001: Project scaffolding
- TASK-006: MCP server entry point

## Technical Notes

### Docker Client
```python
import subprocess
CONTAINER_NAME = "pkscreener"

def run_pkscreener(args: list[str], timeout: int = 120) -> str:
    result = subprocess.run(
        ["docker", "exec", CONTAINER_NAME,
         "python3", "pkscreener/pkscreenercli.py"] + args,
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"PKScreener error: {result.stderr}")
    return result.stdout
```

### Scan Type Mapping
```python
SCAN_TYPES = {
    "breakout": {"args": ["-a", "Y", "-o", "X:12:10", "-e"], "description": "Probable breakouts"},
    "momentum": {"args": ["-a", "Y", "-o", "X:12:31", "-e"], "description": "High momentum stocks"},
    "consolidation": {"args": ["-a", "Y", "-o", "X:12:7", "-e"], "description": "Consolidating stocks"},
    # ... more mappings
}
```

### Output Parsing
PKScreener outputs tables in text format. Parse using:
- Split by newlines
- Identify header row (contains column names)
- Parse subsequent rows into dicts
- Handle variable column widths

### Implementation Hints
1. PKScreener Docker container must be started separately (`docker run -d --name pkscreener ...`)
2. First scan may be slow (PKScreener downloads data); subsequent scans are faster
3. Volume mount `pkscreener-data` persists PKScreener's internal cache
4. Validate `scan_type` against `SCAN_TYPES` keys — don't pass raw user input to CLI
5. Consider running `docker exec` in `asyncio.to_thread()` for async context

## Estimated Complexity
**Medium** (4-6 hours)

## References
- ZAZA_ARCHITECTURE.md Section 5.3 (PKScreener Docker Sidecar)
- ZAZA_ARCHITECTURE.md Section 7.4 (Stock Discovery Tools)
