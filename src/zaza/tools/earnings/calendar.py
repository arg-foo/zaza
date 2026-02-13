"""Earnings calendar tool."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register earnings calendar tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_earnings_calendar(ticker: str) -> str:
        """Get next earnings date and analyst estimates.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
        """
        cache_key = cache.make_key("earnings_cal_tool", ticker=ticker)
        cached = cache.get(cache_key, "earnings_calendar")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            earnings_data = yf.get_earnings(ticker)
            calendar = earnings_data.get("calendar", {})

            if not calendar:
                return json.dumps(
                    {"status": "error", "error": f"No earnings calendar data for {ticker}"}
                )

            # Extract earnings date (may be string or list)
            earnings_date = calendar.get("Earnings Date", "")
            if isinstance(earnings_date, list):
                earnings_date = earnings_date[0] if earnings_date else ""

            eps_estimate = calendar.get("EPS Estimate")
            revenue_estimate = calendar.get("Revenue Estimate")
            eps_low = calendar.get("EPS Low")
            eps_high = calendar.get("EPS High")
            revenue_low = calendar.get("Revenue Low")
            revenue_high = calendar.get("Revenue High")

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "earnings_date": str(earnings_date),
                    "eps_estimate": eps_estimate,
                    "eps_low": eps_low,
                    "eps_high": eps_high,
                    "revenue_estimate": revenue_estimate,
                    "revenue_low": revenue_low,
                    "revenue_high": revenue_high,
                },
            }
            cache.set(cache_key, "earnings_calendar", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("earnings_calendar_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
