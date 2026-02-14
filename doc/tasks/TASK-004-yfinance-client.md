# TASK-004: yfinance API Client

## Task ID
TASK-004

## Status
COMPLETED

## Title
Implement yfinance API Client

## Description
Implement `src/zaza/api/yfinance_client.py` — a wrapper around the `yfinance` library that provides cached access to Yahoo Finance data. This is the primary data source for the project, used by Financial (15), TA (9), Options (7), Macro (3), Institutional (partial), and Earnings (3) tool domains.

The client wraps common yfinance patterns with caching, error handling, and consistent return types.

## Acceptance Criteria

### Functional Requirements
- [ ] `YFinanceClient` class implemented in `src/zaza/api/yfinance_client.py`
- [ ] Constructor accepts a `FileCache` instance
- [ ] `get_quote(ticker: str) -> dict` — current price, volume, market cap via `yf.Ticker.info`
- [ ] `get_history(ticker: str, start: str, end: str, interval: str = "1d") -> list[dict]` — historical OHLCV
- [ ] `get_financials(ticker: str, period: str = "annual") -> dict` — income, balance sheet, cash flow
- [ ] `get_options_expirations(ticker: str) -> list[str]` — available option expiry dates
- [ ] `get_options_chain(ticker: str, date: str) -> dict` — calls + puts for a specific expiry
- [ ] `get_insider_transactions(ticker: str) -> list[dict]` — insider buy/sell transactions
- [ ] `get_institutional_holders(ticker: str) -> dict` — top holders + major holders
- [ ] `get_earnings(ticker: str) -> dict` — earnings history + dates
- [ ] `get_news(ticker: str) -> list[dict]` — recent news articles
- [ ] All methods check cache before making yfinance calls
- [ ] All methods handle yfinance errors gracefully (return empty dict/list, log warning)
- [ ] Converts pandas DataFrames to serializable dicts/lists

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with mocked `yf.Ticker` — no live API calls; test cache hit/miss paths
- [ ] **Performance**: Cache integration prevents redundant Yahoo Finance requests
- [ ] **Observability**: Logging for cache hits, cache misses, and API errors
- [ ] **Documentation**: Docstrings for all public methods

## Dependencies
- TASK-001: Project scaffolding
- TASK-003: File-based cache system

## Technical Notes

### DataFrame Serialization
yfinance returns pandas DataFrames for financials and history. Convert to dicts:
```python
def _df_to_records(self, df) -> list[dict]:
    if df is None or df.empty:
        return []
    df = df.reset_index()
    return df.to_dict(orient="records")
```

### Error Handling
```python
def get_quote(self, ticker: str) -> dict:
    cache_key = self.cache.make_key("quote", ticker=ticker)
    cached = self.cache.get(cache_key, "prices")
    if cached:
        return cached
    try:
        info = yf.Ticker(ticker).info
        if not info or "regularMarketPrice" not in info:
            return {}
        self.cache.set(cache_key, "prices", info)
        return info
    except Exception as e:
        logger.warning(f"yfinance error for {ticker}: {e}")
        return {}
```

### Implementation Hints
1. yfinance `.info` can be slow (~1-2s) — caching is critical
2. `.financials` returns annual by default; use `.quarterly_financials` for quarterly
3. Options chain returns a named tuple with `.calls` and `.puts` DataFrames
4. Always validate that the ticker exists (check for empty `.info` response)
5. Use `logger = logging.getLogger(__name__)` for all logging

## Estimated Complexity
**Medium** (4-6 hours)

## References
- ZAZA_ARCHITECTURE.md Section 9.1 (Data Sources — yfinance)
- ZAZA_ARCHITECTURE.md Section 7.1 (Financial Data Tools)
- yfinance documentation: https://github.com/ranaroussi/yfinance
