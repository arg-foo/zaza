# TASK-018: Macro & Cross-Asset Tools

## Task ID
TASK-018

## Status
PENDING

## Title
Implement Macro & Cross-Asset Tools (5 Tools)

## Description
Implement 5 macro and cross-asset MCP tools for market-wide context: `get_treasury_yields`, `get_market_indices`, `get_commodity_prices`, `get_economic_calendar`, and `get_intermarket_correlations`. Most require no ticker (market-wide); `get_intermarket_correlations` takes a ticker for cross-asset correlation analysis.

All macro tickers are available through yfinance as standard symbols. Economic calendar uses FRED API (optional) or web scraping.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/tools/macro/rates.py` — `get_treasury_yields()`:
  - Uses yfinance tickers: ^IRX (3mo), ^FVX (5Y), ^TNX (10Y), ^TYX (30Y)
  - Returns current yields, yield curve shape (normal/flat/inverted), 2s10s spread, trend vs 30 days ago
- [ ] `src/zaza/tools/macro/indices.py` — `get_market_indices()`:
  - Uses: ^VIX, ^GSPC, ^DJI, ^IXIC, DX-Y.NYB
  - Returns values, daily/weekly change, VIX term structure (contango/backwardation)
- [ ] `src/zaza/tools/macro/commodities.py` — `get_commodity_prices()`:
  - Uses: CL=F (crude), GC=F (gold), SI=F (silver), HG=F (copper), NG=F (natural gas)
  - Returns prices, 1w/1m % change, inflation/risk signal interpretations
- [ ] `src/zaza/tools/macro/calendar.py` — `get_economic_calendar(days_ahead=14)`:
  - Uses FRED API when available, web scrape as fallback
  - Returns upcoming events: date, name, previous, consensus, importance (high/medium/low)
  - Filters to market-moving events: FOMC, CPI, NFP, GDP, PCE, ISM
- [ ] `src/zaza/tools/macro/correlations.py` — `get_intermarket_correlations(ticker)`:
  - Computes 30/60/90-day rolling correlation with S&P 500, 10Y yield, DXY, crude, gold
  - Returns correlations, vs 1Y average, beta to each factor, dominant macro driver
- [ ] All 5 tools registered via `register_macro_tools(app)`
- [ ] All cached with appropriate TTLs (yields/indices/commodities: 1h, calendar: 24h, correlations: 6h)

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with mocked yfinance data for macro tickers
- [ ] **Reliability**: Economic calendar degrades gracefully without FRED API key
- [ ] **Documentation**: Clear tool descriptions explaining macro signal interpretations

## Dependencies
- TASK-001: Project scaffolding
- TASK-003: File-based cache
- TASK-004: yfinance client
- TASK-006: MCP server entry point
- TASK-008: FRED client (for economic calendar)

## Technical Notes

### Yield Curve Classification
```python
def classify_yield_curve(yields):
    spread_2s10s = yields["10Y"] - yields["2Y"]
    if spread_2s10s < -0.1:
        return "inverted"
    elif spread_2s10s < 0.25:
        return "flat"
    else:
        return "normal"
```

### VIX Term Structure
```python
# VIX term structure: front-month > second-month = backwardation (fear)
# Use VIX (^VIX) vs VIX3M (^VIX3M) or VIX9D (^VIX9D)
```

### Correlation Computation
```python
import pandas as pd

def compute_correlations(ticker_returns, macro_returns, windows=[30, 60, 90]):
    results = {}
    for window in windows:
        corr = ticker_returns.rolling(window).corr(macro_returns).iloc[-1]
        results[f"{window}d"] = round(corr, 3)
    return results
```

### Implementation Hints
1. All macro tickers are standard yfinance symbols — no special API needed
2. VIX > 30 = high fear, VIX < 15 = complacency
3. Copper rising + gold falling = risk-on; gold rising + copper falling = risk-off
4. 2Y yield requires ^FVX or alternative source — check yfinance availability
5. Economic calendar may need multiple data source fallbacks

## Estimated Complexity
**Medium** (6-8 hours)

## References
- ZAZA_ARCHITECTURE.md Section 7.7 (Macro & Cross-Asset Tools)
- ZAZA_ARCHITECTURE.md Section 6.2.8 (Macro Context Agent)
