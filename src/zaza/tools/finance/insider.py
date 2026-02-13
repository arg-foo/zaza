"""Insider trades MCP tool.

Tools:
  - get_insider_trades: Recent insider transactions for a ticker.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def _make_insider_trades(yf: YFinanceClient, ticker: str) -> str:
    """Build insider trades JSON from a YFinanceClient instance."""
    try:
        transactions = yf.get_insider_transactions(ticker)
        result: dict[str, Any] = {
            "ticker": ticker,
            "transaction_count": len(transactions),
            "transactions": transactions,
        }
        return json.dumps(result, default=str)
    except Exception as e:
        logger.error("insider_trades_error", ticker=ticker, error=str(e))
        return json.dumps({"error": f"Failed to get insider trades for {ticker}: {e}"})


def register(mcp: FastMCP) -> None:
    """Register insider trades tool with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_insider_trades(ticker: str) -> str:
        """Get recent insider transactions for a stock."""
        return _make_insider_trades(yf, ticker)
