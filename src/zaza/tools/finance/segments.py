"""Segmented revenues MCP tool.

Tools:
  - get_segmented_revenues: Revenue by segment from SEC EDGAR XBRL data.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.edgar_client import EdgarClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)

# XBRL concepts that commonly contain segmented revenue data
_REVENUE_CONCEPTS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
    "SalesRevenueServicesNet",
    "SalesRevenueGoodsNet",
]


def _extract_segments(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract segmented revenue data from EDGAR XBRL company facts.

    Looks for revenue-related XBRL concepts that have segment annotations
    in the us-gaap taxonomy.
    """
    segments: list[dict[str, Any]] = []
    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    for concept_name in _REVENUE_CONCEPTS:
        concept = us_gaap.get(concept_name)
        if not concept:
            continue

        units = concept.get("units", {})
        usd_entries = units.get("USD", [])

        for entry in usd_entries:
            segment = entry.get("segment")
            if segment:
                segments.append({
                    "concept": concept_name,
                    "segment": segment,
                    "value": entry.get("val"),
                    "end_date": entry.get("end"),
                    "fiscal_year": entry.get("fy"),
                    "fiscal_period": entry.get("fp"),
                    "form": entry.get("form"),
                    "filed": entry.get("filed"),
                    "frame": entry.get("frame"),
                })

    return segments


async def _make_segmented_revenues(edgar: EdgarClient, ticker: str) -> str:
    """Build segmented revenues JSON from an EdgarClient instance."""
    try:
        cik = await edgar.ticker_to_cik(ticker)
        facts = await edgar.get_company_facts(cik)

        if not facts:
            return json.dumps({"error": f"No EDGAR data found for {ticker}"})

        segments = _extract_segments(facts)

        if not segments:
            return json.dumps({
                "ticker": ticker,
                "entity_name": facts.get("entityName"),
                "segments": [],
                "message": "No segmented revenue data found in XBRL filings",
            })

        return json.dumps({
            "ticker": ticker,
            "entity_name": facts.get("entityName"),
            "segment_count": len(segments),
            "segments": segments,
        }, default=str)
    except ValueError as e:
        # ticker_to_cik raises ValueError for unknown tickers
        return json.dumps({"error": str(e)})
    except Exception as e:
        logger.error("segmented_revenues_error", ticker=ticker, error=str(e))
        return json.dumps({"error": f"Failed to get segmented revenues for {ticker}: {e}"})


def register(mcp: FastMCP) -> None:
    """Register segmented revenues tool with the MCP server."""
    cache = FileCache()
    edgar = EdgarClient(cache)

    @mcp.tool()
    async def get_segmented_revenues(ticker: str) -> str:
        """Get revenue breakdown by segment from SEC EDGAR XBRL filings.

        Uses the SEC EDGAR company facts API to extract revenue data with segment
        annotations from 10-K and 10-Q XBRL filings.
        """
        return await _make_segmented_revenues(edgar, ticker)
