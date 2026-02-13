# TASK-005: SEC EDGAR API Client

## Task ID
TASK-005

## Status
PENDING

## Title
Implement SEC EDGAR API Client

## Description
Implement `src/zaza/api/edgar_client.py` — an async HTTP client for SEC EDGAR APIs. Used by the filings tools (get_filings, get_filing_items), segmented revenues, institutional holdings (13F parsing), and buyback data extraction. No API key required.

SEC EDGAR requires a User-Agent header and has rate limits (10 req/sec). The client must respect these constraints.

## Acceptance Criteria

### Functional Requirements
- [ ] `EdgarClient` class implemented in `src/zaza/api/edgar_client.py`
- [ ] Uses `httpx.AsyncClient` for all HTTP requests
- [ ] `get_submissions(cik: str) -> dict` — filing metadata from `data.sec.gov/submissions/CIK{cik}.json`
- [ ] `get_company_facts(cik: str) -> dict` — XBRL company facts from `data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`
- [ ] `get_filing_content(cik: str, accession: str) -> str` — full filing text from EDGAR archives
- [ ] `ticker_to_cik(ticker: str) -> str` — resolve ticker symbol to CIK number (using SEC company tickers endpoint)
- [ ] All requests include `User-Agent: "Zaza/1.0 (contact@example.com)"` header
- [ ] Rate limiting: max 10 requests/second to SEC endpoints
- [ ] CIK numbers are zero-padded to 10 digits
- [ ] All methods integrate with FileCache
- [ ] Handles HTTP errors gracefully (404, 429, 500)

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with mocked HTTP responses via `httpx.MockTransport`
- [ ] **Performance**: Rate limiting prevents SEC EDGAR throttling
- [ ] **Observability**: Logging for API calls, rate limit waits, and errors
- [ ] **Reliability**: Retry on 429/5xx with exponential backoff (max 3 retries)

## Dependencies
- TASK-001: Project scaffolding
- TASK-002: Configuration module (for EDGAR_USER_AGENT)
- TASK-003: File-based cache system

## Technical Notes

### Endpoint URLs
```python
BASE = "https://data.sec.gov"
FULL_TEXT = "https://www.sec.gov/Archives/edgar/data"
COMPANY_TICKERS = "https://www.sec.gov/files/company_tickers.json"
```

### CIK Resolution
```python
async def ticker_to_cik(self, ticker: str) -> str:
    # SEC provides a JSON mapping of all tickers → CIK
    resp = await self.client.get(f"{self.BASE}/files/company_tickers.json")
    data = resp.json()
    for entry in data.values():
        if entry["ticker"].upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)
    raise ValueError(f"Ticker {ticker} not found in SEC database")
```

### Filing Content Retrieval
Accession numbers need reformatting: `0000320193-24-000081` → `000032019324000081` (remove dashes) for the URL path.

### Implementation Hints
1. Cache the company_tickers.json mapping with a 7-day TTL — it rarely changes
2. Use `asyncio.Semaphore(10)` for rate limiting
3. Filing content can be very large (10-20k+ tokens) — the filing tools will handle truncation
4. XBRL company facts endpoint has inconsistent coverage across companies

## Estimated Complexity
**Medium** (4-6 hours)

## References
- ZAZA_ARCHITECTURE.md Section 9.1 (Data Sources — SEC EDGAR)
- SEC EDGAR API documentation: https://www.sec.gov/edgar/sec-api-documentation
