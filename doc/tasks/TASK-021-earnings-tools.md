# TASK-021: Earnings & Events Tools

## Task ID
TASK-021

## Status
COMPLETED

## Title
Implement Earnings & Events Tools (4 Tools)

## Description
Implement 4 earnings and events MCP tools: `get_earnings_history`, `get_earnings_calendar`, `get_event_calendar`, and `get_buyback_data`. These track earnings surprises, upcoming catalysts, corporate events, and share repurchase programs.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/tools/earnings/history.py` — `get_earnings_history(ticker, limit=8)`:
  - Per quarter: reported vs estimated EPS/revenue, surprise %, 1-day and 5-day post-earnings drift, beat/miss streak, historical beat rate
- [ ] `src/zaza/tools/earnings/calendar.py` — `get_earnings_calendar(ticker)`:
  - Next earnings date, days until, time (BMO/AMC), consensus EPS/revenue estimates, expected move from options (straddle price as % of stock)
- [ ] `src/zaza/tools/earnings/events.py` — `get_event_calendar(ticker)`:
  - Upcoming: ex-dividend date + amount + yield, stock splits, index rebalancing, conference dates, lockup expiry
- [ ] `src/zaza/tools/earnings/buybacks.py` — `get_buyback_data(ticker)`:
  - Active program (authorized amount, remaining), shares repurchased last quarter + trend, buyback yield, total shareholder yield
- [ ] All 4 tools registered via `register_earnings_tools(app)`
- [ ] Cache TTLs: history 7d, calendar 24h, events 24h, buybacks 7d

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with known earnings data; verify post-earnings drift computation
- [ ] **Reliability**: Missing data returns partial results (not all companies have buybacks or upcoming events)
- [ ] **Documentation**: Tool descriptions explain the significance of each metric

## Dependencies
- TASK-001: Project scaffolding
- TASK-003: File-based cache
- TASK-004: yfinance client
- TASK-005: SEC EDGAR client (for buyback data from 10-Q)
- TASK-006: MCP server entry point

## Technical Notes

### Post-Earnings Drift
```python
# PEAD: stocks that beat tend to drift in same direction for 1-2 weeks
# Compute: 1-day return after earnings, 5-day cumulative return after earnings
# Use get_prices to fetch price data around each earnings date
```

### Expected Move from Options
```python
# Expected move = ATM straddle price / stock price * 100
# ATM = nearest strike to current price
# Straddle = ATM call price + ATM put price
# Requires options data for the expiry nearest to earnings
```

### Buyback Data from 10-Q
```python
# Parse "Issuer Purchases of Equity Securities" table from 10-Q
# Located in Part II, Item 2 of 10-Q filings
# Extract: total shares purchased, average price, max authorized, remaining authorization
```

### Implementation Hints
1. yfinance `.earnings_history` provides basic EPS history but may not include revenue
2. Expected move requires combining earnings calendar with options chain data
3. Buyback data parsing from 10-Q is semi-structured — use regex or table extraction
4. Post-earnings drift is one of the most documented market anomalies

## Estimated Complexity
**Medium** (6-8 hours)

## References
- ZAZA_ARCHITECTURE.md Section 7.10 (Earnings & Events Tools)
