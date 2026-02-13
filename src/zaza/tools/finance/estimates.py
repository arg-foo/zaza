"""Analyst estimates MCP tool.

Tools:
  - get_analyst_estimates: Consensus estimates and price targets.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def _make_analyst_estimates(yf: YFinanceClient, ticker: str) -> str:
    """Build analyst estimates JSON from a YFinanceClient instance."""
    try:
        data = yf.get_quote(ticker)
        if not data:
            return json.dumps({"error": f"No data found for ticker {ticker}"})

        result: dict[str, Any] = {
            "ticker": ticker,
            "current_price": data.get("currentPrice") or data.get("regularMarketPrice"),
            "price_target": {
                "mean": data.get("targetMeanPrice"),
                "median": data.get("targetMedianPrice"),
                "high": data.get("targetHighPrice"),
                "low": data.get("targetLowPrice"),
            },
            "recommendation": {
                "key": data.get("recommendationKey"),
                "mean_score": data.get("recommendationMean"),
            },
            "analyst_count": data.get("numberOfAnalystOpinions"),
        }
        return json.dumps(result, default=str)
    except Exception as e:
        logger.error("analyst_estimates_error", ticker=ticker, error=str(e))
        return json.dumps({"error": f"Failed to get analyst estimates for {ticker}: {e}"})


def register(mcp: FastMCP) -> None:
    """Register analyst estimates tool with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_analyst_estimates(ticker: str) -> str:
        """Get analyst consensus estimates and price targets for a stock.

        Returns mean/median/high/low price targets, recommendation key, and analyst count.
        """
        return _make_analyst_estimates(yf, ticker)
