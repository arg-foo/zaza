# TASK-014: Financial Data Tools — SEC Filings

## Task ID
TASK-014

## Status
PENDING

## Title
Implement Financial Data Tools — SEC Filings

## Description
Implement the 2 SEC filings MCP tools: `get_filings` and `get_filing_items`. The `get_filing_items` tool has **self-healing** behavior — if the accession number is omitted or invalid, it internally resolves it by calling `get_filings` first. This prevents hallucinated accession numbers from causing failures.

These tools are critical for the Filings Research sub-agent, which extracts content from 10-K, 10-Q, and 8-K filings.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/tools/finance/filings.py` — 2 tools:
  - `get_filings(ticker, filing_type=None, limit=10)` — returns filing metadata: accession numbers, filing dates, types, URLs
  - `get_filing_items(ticker, filing_type, accession_number=None, items=None)` — returns filing section text
- [ ] **Self-healing**: If `accession_number` is None or invalid, `get_filing_items` internally:
  1. Calls the filings metadata endpoint to find the most recent matching filing
  2. Uses that accession number to fetch the content
  3. Logs a warning about the self-healing resolution
- [ ] `items` parameter supports: "Item-1A" (risk factors), "Item-7" (MD&A), "Item-1" (business), etc.
- [ ] For 8-K filings: supports extracting specific items like "Item-2.02" (earnings), "Item-8.01" (other events)
- [ ] Filing content is text-only (HTML tags stripped)
- [ ] Tools registered as MCP tools
- [ ] Filings metadata cached (24h TTL); filing content cached (7d TTL — content doesn't change)

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with mocked EDGAR responses; test self-healing path specifically
- [ ] **Performance**: Filing content can be 15-20k+ tokens — return full text (sub-agents handle summarization)
- [ ] **Reliability**: Handle EDGAR rate limits, missing filings, parse errors gracefully
- [ ] **Security**: SEC EDGAR User-Agent header must be present in all requests

## Dependencies
- TASK-001: Project scaffolding
- TASK-003: File-based cache
- TASK-005: SEC EDGAR client
- TASK-006: MCP server entry point

## Technical Notes

### Self-Healing Pattern
```python
async def get_filing_items(ticker, filing_type, accession_number=None, items=None):
    if not accession_number:
        # Self-healing: resolve accession number
        filings = await edgar_client.get_submissions(cik)
        recent = find_most_recent(filings, filing_type)
        accession_number = recent["accessionNumber"]
        logger.warning(f"Self-healed: resolved {filing_type} accession for {ticker}")

    # Fetch filing content
    content = await edgar_client.get_filing_content(cik, accession_number)
    # Parse and extract requested items
    ...
```

### Filing Item Parsing
10-K/10-Q sections are identified by "Item X" headers in the HTML/text. Parse strategy:
1. Strip HTML tags (BeautifulSoup)
2. Find section headers matching requested items
3. Extract text between the matching header and the next section header
4. Return as clean text

### Implementation Hints
1. Self-healing is the most critical feature — test this path thoroughly
2. EDGAR filing documents can be in various formats (HTML, XBRL, text) — handle all
3. Use BeautifulSoup to strip HTML and extract clean text
4. Accession number format: `0000320193-24-000081` — validate format if provided
5. The Filings Research sub-agent depends on this tool returning full text — don't truncate

## Estimated Complexity
**Medium** (6-8 hours)

## References
- ZAZA_ARCHITECTURE.md Section 7.1 (tools 14-15)
- ZAZA_ARCHITECTURE.md Section 5.4 (self-healing filings)
