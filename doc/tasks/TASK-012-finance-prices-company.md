# TASK-012: Financial Data Tools — Prices & Company Info

## Task ID
TASK-012

## Status
COMPLETED

## Title
Implement Financial Data Tools — Prices & Company Info

## Description
Implement the first 5 financial data MCP tools: `get_price_snapshot`, `get_prices`, `get_company_facts`, `get_company_news`, and `get_insider_trades`. These are the most frequently called tools — used inline for simple queries and as building blocks for sub-agents.

All tools use the `YFinanceClient` and `FileCache`.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/tools/finance/prices.py` — `get_price_snapshot(ticker)` and `get_prices(ticker, start_date, end_date)`
  - `get_price_snapshot` returns: current price, change %, volume, market cap, 52w high/low, day range
  - `get_prices` returns: historical OHLCV data as list of records
- [ ] `src/zaza/tools/finance/facts.py` — `get_company_facts(ticker)`
  - Returns: sector, industry, employees, exchange, website, description, market cap
- [ ] `src/zaza/tools/finance/news.py` — `get_company_news(ticker, start_date?, end_date?)`
  - Returns: list of recent news articles with title, publisher, link, publish date
- [ ] `src/zaza/tools/finance/insider.py` — `get_insider_trades(ticker, start_date?, end_date?)`
  - Returns: insider transactions with insider name, title, type (buy/sell), shares, value, date
- [ ] All 5 tools registered as MCP tools via `register_finance_tools(app)` (partial — this task covers 5 of 15)
- [ ] All tools accept proper MCP parameter schemas
- [ ] All tools integrate with FileCache (check cache before calling yfinance)
- [ ] All tools return structured JSON with clear field names

### Non-Functional Requirements
- [ ] **Testing**: Unit tests per tool with mocked YFinanceClient; test cache hits, empty responses, invalid tickers
- [ ] **Observability**: Logging for tool invocations and errors
- [ ] **Reliability**: Invalid ticker returns meaningful error message, not crash
- [ ] **Documentation**: MCP tool descriptions are clear and concise

## Dependencies
- TASK-001: Project scaffolding
- TASK-003: File-based cache
- TASK-004: yfinance API client
- TASK-006: MCP server entry point

## Technical Notes

### MCP Tool Registration Pattern
```python
from mcp.server import Server

def register_finance_tools(app: Server):
    @app.tool()
    async def get_price_snapshot(ticker: str) -> str:
        """Get current price, volume, market cap, and daily change for a stock."""
        # Use YFinanceClient + cache
        data = yf_client.get_quote(ticker)
        result = {
            "ticker": ticker,
            "price": data.get("regularMarketPrice"),
            "change_pct": data.get("regularMarketChangePercent"),
            "volume": data.get("regularMarketVolume"),
            "market_cap": data.get("marketCap"),
            "day_high": data.get("dayHigh"),
            "day_low": data.get("dayLow"),
            "week_52_high": data.get("fiftyTwoWeekHigh"),
            "week_52_low": data.get("fiftyTwoWeekLow"),
        }
        return json.dumps(result)
```

### Implementation Hints
1. MCP tools return strings (JSON serialized) — not dicts
2. Each tool file should export a `register(app)` function
3. The top-level `register_finance_tools` aggregates all finance sub-registrations
4. Use consistent error response format: `{"error": "message"}`
5. Date parameters should accept ISO format strings (YYYY-MM-DD)

## Estimated Complexity
**Medium** (4-6 hours)

## References
- ZAZA_ARCHITECTURE.md Section 7.1 (Financial Data Tools — tools 1-2, 10-13)
