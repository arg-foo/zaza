"""Commodity prices tool."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)

COMMODITY_TICKERS = {
    "crude_oil": "CL=F",
    "gold": "GC=F",
    "silver": "SI=F",
    "copper": "HG=F",
    "natural_gas": "NG=F",
}


def _compute_pct_change(history: list[dict[str, Any]], current: float) -> dict[str, float | None]:
    """Compute 1-week and 1-month percentage changes from history."""
    result: dict[str, float | None] = {"1w_change_pct": None, "1m_change_pct": None}
    if not history or current is None:
        return result

    closes = [r.get("Close") for r in history if r.get("Close") is not None]
    if not closes:
        return result

    # 1-week change (last ~5 trading days)
    if len(closes) >= 5:
        week_ago = closes[-5]
        if week_ago > 0:
            result["1w_change_pct"] = round((current - week_ago) / week_ago * 100, 2)
    elif len(closes) >= 1:
        first = closes[0]
        if first > 0:
            result["1w_change_pct"] = round((current - first) / first * 100, 2)

    # 1-month change (last ~22 trading days)
    if len(closes) >= 22:
        month_ago = closes[-22]
        if month_ago > 0:
            result["1m_change_pct"] = round((current - month_ago) / month_ago * 100, 2)
    elif len(closes) >= 1:
        first = closes[0]
        if first > 0:
            result["1m_change_pct"] = round((current - first) / first * 100, 2)

    return result


def register(mcp: FastMCP) -> None:
    """Register commodity prices tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_commodity_prices() -> str:
        """Get current commodity prices with weekly and monthly percentage changes.

        Returns prices for crude oil, gold, silver, copper, and natural gas
        along with 1-week and 1-month percentage changes.
        """
        cache_key = cache.make_key("commodities")
        cached = cache.get(cache_key, "commodities")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            commodities: dict[str, dict[str, Any]] = {}

            for label, ticker in COMMODITY_TICKERS.items():
                quote = yf.get_quote(ticker)
                price = quote.get("regularMarketPrice")
                if price is None:
                    continue

                history = yf.get_history(ticker, period="1mo")
                changes = _compute_pct_change(history, float(price))

                commodities[label] = {
                    "price": round(float(price), 2),
                    "daily_change": round(
                        float(price) - float(quote.get("regularMarketPreviousClose", price)), 2
                    ),
                    **changes,
                }

            if not commodities:
                return json.dumps(
                    {"status": "error", "error": "No commodity data available"}
                )

            result: dict[str, Any] = {
                "status": "ok",
                "data": commodities,
            }
            cache.set(cache_key, "commodities", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("commodity_prices_error", error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
