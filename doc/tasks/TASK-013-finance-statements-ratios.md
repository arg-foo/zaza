# TASK-013: Financial Data Tools — Statements & Ratios

## Task ID
TASK-013

## Status
COMPLETED

## Title
Implement Financial Data Tools — Statements & Ratios

## Description
Implement 8 financial data MCP tools for financial statements, ratios, and estimates: `get_income_statements`, `get_balance_sheets`, `get_cash_flow_statements`, `get_all_financial_statements`, `get_key_ratios_snapshot`, `get_key_ratios`, `get_analyst_estimates`, and `get_segmented_revenues`.

These are core fundamental analysis tools used by the Comparative Research sub-agent and inline fundamental queries.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/tools/finance/statements.py` — 4 tools:
  - `get_income_statements(ticker, period="annual", limit=5)` — revenue, gross profit, operating income, net income, EPS
  - `get_balance_sheets(ticker, period="annual", limit=5)` — assets, liabilities, equity, debt, cash
  - `get_cash_flow_statements(ticker, period="annual", limit=5)` — operating, investing, financing cash flows, FCF
  - `get_all_financial_statements(ticker, period="annual", limit=5)` — combined all three
- [ ] `src/zaza/tools/finance/ratios.py` — 2 tools:
  - `get_key_ratios_snapshot(ticker)` — current P/E, EV/EBITDA, ROE, margins, dividend yield from `.info`
  - `get_key_ratios(ticker, period="annual", limit=5)` — historical ratios computed from statements
- [ ] `src/zaza/tools/finance/estimates.py` — `get_analyst_estimates(ticker)` — consensus estimates, price targets
- [ ] `src/zaza/tools/finance/segments.py` — `get_segmented_revenues(ticker)` — revenue by segment/geography from SEC EDGAR XBRL
- [ ] Period parameter accepts: "annual", "quarterly"
- [ ] All tools registered as MCP tools
- [ ] All tools use cache with "fundamentals" category (24h TTL)
- [ ] `get_key_ratios` computes derived ratios from historical financial statements

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with sample financial data; verify ratio computations are correct
- [ ] **Reliability**: Handle companies with missing data gracefully (return partial data with nulls)
- [ ] **Documentation**: Clear MCP tool descriptions

## Dependencies
- TASK-001: Project scaffolding
- TASK-003: File-based cache
- TASK-004: yfinance API client
- TASK-005: SEC EDGAR client (for segmented revenues)
- TASK-006: MCP server entry point

## Technical Notes

### Historical Ratio Computation
`get_key_ratios` is unique — yfinance doesn't provide historical ratio time series. Compute from statements:
```python
# From income + balance sheet:
# P/E = market_cap / net_income (approximate with last known market cap)
# ROE = net_income / shareholder_equity
# Gross margin = gross_profit / revenue
# Operating margin = operating_income / revenue
# Net margin = net_income / revenue
# Debt/Equity = total_debt / shareholder_equity
```

### Segmented Revenues (EDGAR XBRL)
```python
# Uses EdgarClient.get_company_facts() to find XBRL revenue segment tags
# Coverage is inconsistent — return empty dict if no segment data found
# Common tags: us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax
```

### Implementation Hints
1. Financial statements from yfinance come as DataFrames with dates as columns — transpose for time series
2. `get_all_financial_statements` should call the other three internally, not duplicate logic
3. For quarterly data, use `.quarterly_financials`, `.quarterly_balance_sheet`, `.quarterly_cashflow`
4. Handle the case where a company has fewer periods than `limit` requested

## Estimated Complexity
**Medium** (6-8 hours)

## References
- ZAZA_ARCHITECTURE.md Section 7.1 (Financial Data Tools — tools 3-9, 12)
