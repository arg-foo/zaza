"""SEC filings MCP tools — filing metadata and section extraction."""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

from zaza.api.edgar_client import EdgarClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register SEC filings tools with the MCP server."""
    cache = FileCache()
    edgar = EdgarClient(cache)

    @mcp.tool()
    async def get_filings(
        ticker: str,
        filing_type: str | None = None,
        limit: int = 10,
    ) -> str:
        """Get SEC filing metadata for a company.

        Returns filing accession numbers, dates, types, and URLs.
        Optionally filter by filing type (e.g. '10-K', '10-Q', '8-K').

        Args:
            ticker: Stock ticker symbol.
            filing_type: Optional filing type to filter by.
            limit: Maximum number of filings to return (default 10).
        """
        try:
            cik = await edgar.ticker_to_cik(ticker)
            submissions = await edgar.get_submissions(cik)

            recent = submissions.get("recentFilings", {})
            if not recent:
                return json.dumps({
                    "status": "ok",
                    "ticker": ticker.upper(),
                    "data": {"filings": []},
                }, default=str)

            accession_numbers = recent.get("accessionNumber", [])
            filing_dates = recent.get("filingDate", [])
            forms = recent.get("form", [])
            primary_docs = recent.get("primaryDocument", [])

            filings: list[dict[str, Any]] = []
            for i in range(len(accession_numbers)):
                entry: dict[str, Any] = {
                    "accession_number": accession_numbers[i],
                    "filing_date": filing_dates[i] if i < len(filing_dates) else None,
                    "form": forms[i] if i < len(forms) else None,
                    "primary_document": primary_docs[i] if i < len(primary_docs) else None,
                }

                if filing_type and entry["form"] != filing_type:
                    continue
                filings.append(entry)

                if len(filings) >= limit:
                    break

            return json.dumps({
                "status": "ok",
                "ticker": ticker.upper(),
                "data": {"filings": filings},
            }, default=str)

        except Exception as e:
            logger.warning("get_filings_error", ticker=ticker, error=str(e))
            return json.dumps({"error": str(e)}, default=str)

    @mcp.tool()
    async def get_filing_items(
        ticker: str,
        filing_type: str,
        accession_number: str | None = None,
        items: list[str] | None = None,
    ) -> str:
        """Get parsed sections from an SEC filing.

        Self-healing: if accession_number is not provided, automatically
        resolves the most recent filing of the given type.

        Uses BeautifulSoup to strip HTML and extract sections by Item headers.

        Args:
            ticker: Stock ticker symbol.
            filing_type: Filing type (e.g. '10-K', '10-Q').
            accession_number: Optional accession number. Auto-resolved if omitted.
            items: Optional list of specific items to extract (e.g. ['Item 1A']).
        """
        try:
            cik = await edgar.ticker_to_cik(ticker)

            # Self-healing: resolve accession_number if not provided
            if accession_number is None:
                logger.warning(
                    "self_healing_accession",
                    ticker=ticker,
                    filing_type=filing_type,
                    message="No accession_number provided, resolving from submissions",
                )
                submissions = await edgar.get_submissions(cik)
                recent = submissions.get("recentFilings", {})
                accession_numbers = recent.get("accessionNumber", [])
                forms = recent.get("form", [])

                resolved = None
                for i, form in enumerate(forms):
                    if form == filing_type:
                        resolved = accession_numbers[i]
                        break

                if resolved is None:
                    return json.dumps({
                        "error": f"No {filing_type} filing found for {ticker.upper()}"
                    }, default=str)

                accession_number = resolved
                logger.info(
                    "self_healing_resolved",
                    ticker=ticker,
                    accession_number=accession_number,
                )

            # Fetch filing content
            content = await edgar.get_filing_content(cik, accession_number)
            if not content:
                return json.dumps({
                    "error": f"Filing content not available for {accession_number}"
                }, default=str)

            # Parse HTML and extract sections
            parsed_items = _parse_filing_items(content)

            # Filter to requested items if specified
            if items:
                items_lower = [item.lower() for item in items]
                parsed_items = [
                    item for item in parsed_items
                    if any(req in item["item"].lower() for req in items_lower)
                ]

            return json.dumps({
                "status": "ok",
                "ticker": ticker.upper(),
                "accession_number": accession_number,
                "filing_type": filing_type,
                "data": {"items": parsed_items},
            }, default=str)

        except Exception as e:
            logger.warning("get_filing_items_error", ticker=ticker, error=str(e))
            return json.dumps({"error": str(e)}, default=str)


def _parse_filing_items(html_content: str) -> list[dict[str, str]]:
    """Parse an SEC filing HTML document and extract Item sections.

    Looks for headings matching the pattern "Item X" or "Item X." and
    extracts the text content between consecutive item headers.

    Args:
        html_content: Raw HTML content of the filing.

    Returns:
        List of dicts with 'item' (header) and 'content' (text) keys.
    """
    soup = BeautifulSoup(html_content, "lxml")

    # Remove script and style elements
    for element in soup(["script", "style"]):
        element.decompose()

    text = soup.get_text(separator="\n")

    # Find Item sections using regex
    # Matches patterns like "Item 1.", "Item 1A.", "Item 7.", etc.
    item_pattern = re.compile(
        r"^(Item\s+\d+[A-Za-z]?\.?\s*.*)$",
        re.MULTILINE | re.IGNORECASE,
    )

    matches = list(item_pattern.finditer(text))
    if not matches:
        # Fallback: return entire text as single item
        clean_text = text.strip()
        if clean_text:
            return [{"item": "Full Document", "content": clean_text[:5000]}]
        return []

    items: list[dict[str, str]] = []
    for i, match in enumerate(matches):
        header = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        # Truncate very long sections
        if len(content) > 5000:
            content = content[:5000] + "... [truncated]"

        items.append({"item": header, "content": content})

    return items
