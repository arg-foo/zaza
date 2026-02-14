# TASK-008: FRED API Client

## Task ID
TASK-008

## Status
COMPLETED

## Title
Implement FRED API Client

## Description
Implement `src/zaza/api/fred_client.py` — an async HTTP client for the Federal Reserve Economic Data (FRED) API. Used by the `get_economic_calendar` macro tool. Free with registration. Gracefully degrades when API key is absent.

## Acceptance Criteria

### Functional Requirements
- [ ] `FredClient` class in `src/zaza/api/fred_client.py`
- [ ] Constructor accepts `api_key: str`
- [ ] `get_series(series_id: str, start_date: str = None, end_date: str = None) -> list[dict]` — economic data series (e.g., 'DFF' for Fed funds rate)
- [ ] `get_release_dates(days_ahead: int = 14) -> list[dict]` — upcoming economic release dates
- [ ] Uses `httpx.AsyncClient` with base URL `https://api.stlouisfed.org/fred`
- [ ] All responses cached with FileCache (category: "economic_calendar")
- [ ] Returns empty list when API key is missing (checked via `config.has_fred_key()`)
- [ ] Handles HTTP errors and API errors gracefully

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with mocked HTTP responses
- [ ] **Security**: API key passed as query parameter (FRED standard), never logged
- [ ] **Observability**: Logging for API calls and degraded mode

## Dependencies
- TASK-001: Project scaffolding
- TASK-002: Configuration module
- TASK-003: File-based cache system

## Technical Notes

### Key FRED Endpoints
```python
BASE = "https://api.stlouisfed.org/fred"

# Series data
f"{BASE}/series/observations?series_id={id}&api_key={key}&file_type=json"

# Release dates
f"{BASE}/releases/dates?api_key={key}&file_type=json&include_release_dates_with_no_data=true"
```

### Key Economic Series IDs
- `DFF` — Federal Funds Effective Rate
- `DGS10` — 10-Year Treasury Constant Maturity Rate
- `CPIAUCSL` — Consumer Price Index
- `UNRATE` — Unemployment Rate
- `GDP` — Gross Domestic Product

### Implementation Hints
1. FRED API always requires `file_type=json` parameter
2. The `get_release_dates` endpoint returns upcoming data releases — filter to next N days
3. FRED has a 120 requests/minute limit — unlikely to hit with Zaza's usage pattern
4. When API key is absent, log a warning and return empty data

## Estimated Complexity
**Small** (2-3 hours)

## References
- ZAZA_ARCHITECTURE.md Section 9.1 (FRED)
- FRED API docs: https://fred.stlouisfed.org/docs/api/fred/
