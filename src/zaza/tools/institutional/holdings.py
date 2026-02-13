"""Institutional holdings tool."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register institutional holdings tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_institutional_holdings(ticker: str) -> str:
        """Get institutional holdings data including top holders and ownership percentages.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
        """
        cache_key = cache.make_key("inst_holdings_tool", ticker=ticker)
        cached = cache.get(cache_key, "institutional_holdings")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            holders_data = yf.get_institutional_holders(ticker)
            holders = holders_data.get("institutional_holders", [])
            major = holders_data.get("major_holders", [])

            if not holders:
                return json.dumps(
                    {"status": "error", "error": f"No institutional holder data for {ticker}"}
                )

            # Get top 10 holders
            top_holders = holders[:10]

            # Extract total institutional ownership from major_holders
            institutional_pct = None
            insider_pct = None
            for row in major:
                val = row.get("0", "")
                desc = row.get("1", "")
                if "institution" in desc.lower():
                    try:
                        institutional_pct = float(str(val).replace("%", ""))
                    except (ValueError, TypeError):
                        pass
                elif "insider" in desc.lower():
                    try:
                        insider_pct = float(str(val).replace("%", ""))
                    except (ValueError, TypeError):
                        pass

            # Compute total shares held by top holders
            total_top_shares = sum(
                h.get("Shares", 0) or 0 for h in top_holders
            )

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "top_holders": top_holders,
                    "total_top_10_shares": total_top_shares,
                    "institutional_ownership_pct": institutional_pct,
                    "insider_ownership_pct": insider_pct,
                    "holder_count": len(holders),
                },
            }
            cache.set(cache_key, "institutional_holdings", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("institutional_holdings_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
