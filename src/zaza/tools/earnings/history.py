"""Earnings history tool."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register earnings history tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_earnings_history(ticker: str, limit: int = 8) -> str:
        """Get historical earnings per share (EPS) data with beat/miss analysis.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
            limit: Maximum number of quarters to return (default 8).
        """
        cache_key = cache.make_key("earnings_hist_tool", ticker=ticker, limit=limit)
        cached = cache.get(cache_key, "earnings_history")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            earnings_data = yf.get_earnings(ticker)
            history = earnings_data.get("earnings_history", [])

            if not history:
                return json.dumps(
                    {"status": "error", "error": f"No earnings history for {ticker}"}
                )

            quarters = []
            for entry in history[:limit]:
                estimate = entry.get("EPS Estimate")
                reported = entry.get("Reported EPS")
                surprise = entry.get("Surprise(%)")

                # Classify beat/miss
                if estimate is not None and reported is not None:
                    try:
                        beat_miss = "beat" if float(reported) > float(estimate) else "miss"
                    except (ValueError, TypeError):
                        beat_miss = "unknown"
                else:
                    beat_miss = "unknown"

                quarters.append({
                    "quarter_end": str(entry.get("Quarter End", "")),
                    "eps_estimate": estimate,
                    "eps_reported": reported,
                    "surprise_pct": surprise,
                    "beat_miss": beat_miss,
                })

            # Summary stats
            beats = sum(1 for q in quarters if q["beat_miss"] == "beat")
            misses = sum(1 for q in quarters if q["beat_miss"] == "miss")

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "quarters": quarters,
                    "summary": {
                        "total_quarters": len(quarters),
                        "beats": beats,
                        "misses": misses,
                        "beat_rate": round(beats / len(quarters), 2) if quarters else 0,
                    },
                },
            }
            cache.set(cache_key, "earnings_history", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("earnings_history_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
