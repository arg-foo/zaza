"""Company facts MCP tool.

Tools:
  - get_company_facts: Sector, industry, employees, exchange, website, description, market cap.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def _make_company_facts(yf: YFinanceClient, ticker: str) -> str:
    """Build company facts JSON from a YFinanceClient instance."""
    try:
        data = yf.get_quote(ticker)
        if not data:
            return json.dumps({"error": f"No data found for ticker {ticker}"})
        result: dict[str, Any] = {
            "ticker": ticker,
            "name": data.get("shortName"),
            "sector": data.get("sector"),
            "industry": data.get("industry"),
            "employees": data.get("fullTimeEmployees"),
            "exchange": data.get("exchange"),
            "website": data.get("website"),
            "description": data.get("longBusinessSummary"),
            "market_cap": data.get("marketCap"),
            "currency": data.get("currency"),
        }
        return json.dumps(result, default=str)
    except Exception as e:
        logger.error("company_facts_error", ticker=ticker, error=str(e))
        return json.dumps({"error": f"Failed to get company facts for {ticker}: {e}"})


def register(mcp: FastMCP) -> None:
    """Register company facts tool with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_company_facts(ticker: str) -> str:
        """Get company profile: sector, industry, employees, exchange, website, description."""
        return _make_company_facts(yf, ticker)
