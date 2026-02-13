# TASK-025: MCP Server Tool Registration & Wiring

## Task ID
TASK-025

## Status
PENDING

## Title
Wire All Tool Registrations into MCP Server

## Description
Complete the MCP server by wiring all 11 tool domain registration functions into `src/zaza/server.py`. This task replaces the stub `register_*_tools()` functions from TASK-006 with actual imports and calls to the registration functions implemented in TASK-012 through TASK-024.

This is the integration point where all tools become available to Claude Code. After this task, running `uv run python -m zaza.server` should expose all 66 MCP tools.

## Acceptance Criteria

### Functional Requirements
- [ ] `server.py` imports and calls all 11 `register_*_tools(app)` functions:
  - `register_finance_tools` (from tools/finance/ — 15 tools)
  - `register_ta_tools` (from tools/ta/ — 9 tools)
  - `register_options_tools` (from tools/options/ — 7 tools)
  - `register_sentiment_tools` (from tools/sentiment/ — 4 tools)
  - `register_macro_tools` (from tools/macro/ — 5 tools)
  - `register_quantitative_tools` (from tools/quantitative/ — 6 tools)
  - `register_institutional_tools` (from tools/institutional/ — 4 tools)
  - `register_earnings_tools` (from tools/earnings/ — 4 tools)
  - `register_backtesting_tools` (from tools/backtesting/ — 4 tools)
  - `register_screener_tools` (from tools/screener/ — 3 tools)
  - `register_browser_tools` (from tools/browser/ — 5 tools)
- [ ] Shared dependencies initialized and injected:
  - `FileCache` instance created once and shared across all clients/tools
  - `YFinanceClient` instance created with shared cache
  - `EdgarClient` instance created with shared cache
  - `RedditClient` created conditionally (only if credentials available)
  - `StockTwitsClient` created with shared cache
  - `FredClient` created conditionally (only if API key available)
- [ ] `--check` flag verifies all tools are registered and server starts cleanly
- [ ] MCP `tools/list` returns all 66 tools with correct names and schemas
- [ ] Server logs the count of registered tools on startup
- [ ] Graceful error handling if a tool domain fails to register (log error, continue with other domains)

### Non-Functional Requirements
- [ ] **Testing**: Integration test that starts the server and verifies all 66 tools appear in `tools/list`
- [ ] **Observability**: Startup log shows tool count per domain and total
- [ ] **Reliability**: One failing domain doesn't prevent other domains from registering
- [ ] **Performance**: Server startup (including all registrations) < 3 seconds

## Dependencies
- TASK-006: MCP server entry point (skeleton)
- TASK-012 through TASK-024: All tool domain implementations

## Technical Notes

### Dependency Injection Pattern
```python
# server.py
from zaza.cache.store import FileCache
from zaza.api.yfinance_client import YFinanceClient
from zaza.api.edgar_client import EdgarClient
from zaza.config import has_reddit_credentials, has_fred_key

# Initialize shared dependencies
cache = FileCache()
yf_client = YFinanceClient(cache)
edgar_client = EdgarClient(cache)

# Conditional clients
reddit_client = None
if has_reddit_credentials():
    from zaza.api.reddit_client import RedditClient
    reddit_client = RedditClient(os.getenv("REDDIT_CLIENT_ID"), os.getenv("REDDIT_CLIENT_SECRET"), cache)

fred_client = None
if has_fred_key():
    from zaza.api.fred_client import FredClient
    fred_client = FredClient(os.getenv("FRED_API_KEY"), cache)

# Register all tool domains
register_finance_tools(app, yf_client, edgar_client, cache)
register_ta_tools(app, yf_client, cache)
register_options_tools(app, yf_client, cache)
register_sentiment_tools(app, yf_client, reddit_client, stocktwits_client, cache)
register_macro_tools(app, yf_client, fred_client, cache)
register_quantitative_tools(app, yf_client, cache)
register_institutional_tools(app, yf_client, edgar_client, cache)
register_earnings_tools(app, yf_client, edgar_client, cache)
register_backtesting_tools(app, yf_client, cache)
register_screener_tools(app)
register_browser_tools(app)
```

### Implementation Hints
1. Each tool domain's `register_*_tools` function accepts the shared dependencies it needs
2. Use try/except around each registration to isolate failures
3. The `--check` flag should verify `tools/list` returns 66 entries
4. Log which optional clients are available at startup (Reddit, FRED)
5. Consider a `register_all_tools(app)` convenience function

## Estimated Complexity
**Medium** (4-6 hours)

## References
- ZAZA_ARCHITECTURE.md Section 5.1 (Server Entry Point)
- ZAZA_ARCHITECTURE.md Section 5.4 (Hybrid Tool Architecture)
