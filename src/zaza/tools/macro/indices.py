"""Market indices and VIX tool."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)

INDEX_TICKERS = {
    "VIX": "^VIX",
    "SP500": "^GSPC",
    "Dow_Jones": "^DJI",
    "Nasdaq": "^IXIC",
    "US_Dollar": "DX-Y.NYB",
}


def _interpret_vix(vix_value: float) -> str:
    """Classify VIX level."""
    if vix_value < 15:
        return "low"
    elif vix_value < 20:
        return "moderate"
    elif vix_value < 30:
        return "elevated"
    else:
        return "high"


def register(mcp: FastMCP) -> None:
    """Register market indices tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_market_indices() -> str:
        """Get major market indices with daily changes and VIX interpretation.

        Returns current values and daily percentage changes for S&P 500, Dow Jones,
        Nasdaq, VIX, and US Dollar Index.
        """
        cache_key = cache.make_key("market_indices")
        cached = cache.get(cache_key, "market_indices")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            indices: dict[str, dict[str, Any]] = {}
            vix_value: float | None = None

            for label, ticker in INDEX_TICKERS.items():
                quote = yf.get_quote(ticker)
                price = quote.get("regularMarketPrice")
                prev_close = quote.get("regularMarketPreviousClose")

                if price is None:
                    continue

                daily_change = None
                daily_change_pct = None
                if prev_close and prev_close > 0:
                    daily_change = round(float(price) - float(prev_close), 2)
                    daily_change_pct = round(
                        (float(price) - float(prev_close)) / float(prev_close) * 100, 2
                    )

                indices[label] = {
                    "value": round(float(price), 2),
                    "daily_change": daily_change,
                    "daily_change_pct": daily_change_pct,
                }

                if label == "VIX":
                    vix_value = float(price)

            if not indices:
                return json.dumps({"status": "error", "error": "No market index data available"})

            vix_interp = _interpret_vix(vix_value) if vix_value is not None else "unknown"

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "indices": indices,
                    "vix_interpretation": vix_interp,
                },
            }
            cache.set(cache_key, "market_indices", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("market_indices_error", error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
