"""Event calendar tool."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def _timestamp_to_date(ts: int | float | None) -> str | None:
    """Convert Unix timestamp to date string."""
    if ts is None or ts == 0:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, OSError, OverflowError):
        return None


def register(mcp: FastMCP) -> None:
    """Register event calendar tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_event_calendar(ticker: str) -> str:
        """Get upcoming corporate events: ex-dividend dates, splits, earnings.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
        """
        cache_key = cache.make_key("event_cal", ticker=ticker)
        cached = cache.get(cache_key, "event_calendar")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            quote = yf.get_quote(ticker)
            earnings_data = yf.get_earnings(ticker)
            calendar = earnings_data.get("calendar", {})

            events: list[dict[str, Any]] = []

            # Dividend events
            ex_div_ts = quote.get("exDividendDate")
            ex_div_date = _timestamp_to_date(ex_div_ts)
            if ex_div_date:
                events.append({
                    "type": "ex_dividend",
                    "date": ex_div_date,
                    "details": {
                        "dividend_rate": quote.get("dividendRate"),
                        "dividend_yield": quote.get("dividendYield"),
                    },
                })

            div_date_ts = quote.get("dividendDate")
            div_date = _timestamp_to_date(div_date_ts)
            if div_date:
                events.append({
                    "type": "dividend_payment",
                    "date": div_date,
                    "details": {
                        "dividend_rate": quote.get("dividendRate"),
                    },
                })

            # Last split info (historical, for reference)
            last_split_ts = quote.get("lastSplitDate")
            last_split_date = _timestamp_to_date(last_split_ts)
            if last_split_date:
                events.append({
                    "type": "last_split",
                    "date": last_split_date,
                    "details": {
                        "split_factor": quote.get("lastSplitFactor"),
                    },
                })

            # Earnings date from calendar
            earnings_date = calendar.get("Earnings Date", "")
            if isinstance(earnings_date, list):
                earnings_date = earnings_date[0] if earnings_date else ""
            if earnings_date:
                events.append({
                    "type": "earnings",
                    "date": str(earnings_date),
                    "details": {
                        "eps_estimate": calendar.get("EPS Estimate"),
                    },
                })

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "events": events,
                },
            }
            cache.set(cache_key, "event_calendar", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("event_calendar_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
