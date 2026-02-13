"""Insider sentiment analysis tool."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.sentiment import classify_insider_activity

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP, yf: YFinanceClient, cache: FileCache) -> None:
    """Register insider sentiment tool on the MCP server."""

    @mcp.tool()
    async def get_insider_sentiment(ticker: str, months: int = 6) -> str:
        """Analyze insider transaction patterns for a ticker.

        Classifies buying/selling activity, detects cluster buying,
        and returns a directional sentiment signal.
        Cached for 24 hours.
        """
        try:
            ticker_upper = ticker.upper()

            # Check cache
            cache_key = cache.make_key("insider_sentiment", ticker=ticker_upper, months=months)
            cached = cache.get(cache_key, "insider_sentiment")
            if cached is not None:
                return json.dumps(cached, default=str)

            transactions = yf.get_insider_transactions(ticker_upper)
            analysis = classify_insider_activity(transactions)

            result: dict[str, Any] = {
                "ticker": ticker_upper,
                "months": months,
                "analysis": analysis,
                "transactions": transactions,
                "transaction_count": len(transactions),
            }
            cache.set(cache_key, "insider_sentiment", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("get_insider_sentiment_error", ticker=ticker, error=str(e))
            return json.dumps({"error": f"Failed to get insider sentiment for {ticker}: {e}"})
