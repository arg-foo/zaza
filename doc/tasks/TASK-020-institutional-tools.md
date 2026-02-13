# TASK-020: Institutional Flow Tools

## Task ID
TASK-020

## Status
PENDING

## Title
Implement Institutional Flow Tools (4 Tools)

## Description
Implement 4 institutional flow MCP tools: `get_short_interest`, `get_institutional_holdings`, `get_fund_flows`, and `get_dark_pool_activity`. These track positioning of institutions, short sellers, and dark pool participants.

Data sources: yfinance for short interest and institutional holders, SEC EDGAR for 13F filings, FINRA ADF for dark pool data (web scrape).

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/tools/institutional/short_interest.py` — `get_short_interest(ticker)`:
  - Shares short, short % of float, short ratio (days to cover), change from prior report, short squeeze score, sector median comparison
- [ ] `src/zaza/tools/institutional/holdings.py` — `get_institutional_holdings(ticker)`:
  - Top 10 holders (name, %, shares, value), total institutional %, quarterly change, notable new/exited positions, insider %
- [ ] `src/zaza/tools/institutional/flows.py` — `get_fund_flows(ticker)`:
  - Related ETFs, net ETF inflows/outflows (1w, 1mo), sector ETF trend, accumulation/distribution signal
- [ ] `src/zaza/tools/institutional/dark_pool.py` — `get_dark_pool_activity(ticker)`:
  - Off-exchange volume %, dark pool vs lit ratio, volume trend (5d, 20d), block trade detection, vs sector average
- [ ] All 4 tools registered via `register_institutional_tools(app)`
- [ ] Appropriate cache TTLs (short interest: 24h, holdings: 7d, flows: 24h, dark pool: 24h)

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with mocked data; test short squeeze score computation
- [ ] **Reliability**: Dark pool scraping may fail — return partial data with warning
- [ ] **Observability**: Log data source availability and fallback paths

## Dependencies
- TASK-001: Project scaffolding
- TASK-003: File-based cache
- TASK-004: yfinance client
- TASK-005: SEC EDGAR client (for 13F)
- TASK-006: MCP server entry point

## Technical Notes

### Short Squeeze Score
```python
def compute_squeeze_score(si_pct, float_size, cost_to_borrow=None):
    score = 0
    if si_pct > 20: score += 3
    elif si_pct > 10: score += 2
    elif si_pct > 5: score += 1
    if float_size < 50_000_000: score += 2
    elif float_size < 100_000_000: score += 1
    if cost_to_borrow and cost_to_borrow > 50: score += 2
    return min(score, 10)  # 0-10 scale
```

### FINRA Dark Pool Data
FINRA ATS transparency data is publicly available but requires web scraping. Alternative: use `finra-data` endpoints if available.

### Implementation Hints
1. yfinance `.info` contains `shortPercentOfFloat`, `sharesShort`, `shortRatio`
2. 13F data has 45-day reporting lag — note this in the tool response
3. Fund flows are proxied via ETF holding changes — not a perfect measure
4. Dark pool data has 2-4 week lag from FINRA
5. Short squeeze score is a composite heuristic, not a precise prediction

## Estimated Complexity
**Medium** (6-8 hours)

## References
- ZAZA_ARCHITECTURE.md Section 7.9 (Institutional Flow Tools)
