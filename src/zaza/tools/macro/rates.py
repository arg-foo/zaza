"""Treasury yield curve tool."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)

# Treasury ticker mapping
TREASURY_TICKERS = {
    "3_month": "^IRX",
    "5_year": "^FVX",
    "10_year": "^TNX",
    "30_year": "^TYX",
}


def _classify_curve(yields: dict[str, float]) -> str:
    """Classify yield curve shape: normal, flat, or inverted."""
    short = yields.get("3_month", 0)
    long_10y = yields.get("10_year", 0)

    if short == 0 or long_10y == 0:
        return "unknown"

    spread_3m_10y = long_10y - short

    if spread_3m_10y < -0.1:
        return "inverted"
    elif abs(spread_3m_10y) <= 0.1:
        return "flat"
    else:
        return "normal"


def _compute_trend(yields: dict[str, float]) -> str:
    """Simple trend assessment based on spread."""
    short = yields.get("3_month", 0)
    long_30y = yields.get("30_year", 0)
    if short == 0 or long_30y == 0:
        return "unknown"
    spread = long_30y - short
    if spread > 0.5:
        return "steepening"
    elif spread < -0.5:
        return "flattening"
    return "stable"


def register(mcp: FastMCP) -> None:
    """Register treasury yields tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_treasury_yields() -> str:
        """Get current US Treasury yield curve with shape classification.

        Returns yields for 3-month, 5-year, 10-year, and 30-year Treasuries,
        along with curve shape (normal/flat/inverted) and trend assessment.
        """
        cache_key = cache.make_key("treasury_yields")
        cached = cache.get(cache_key, "treasury_yields")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            yields: dict[str, float] = {}
            for label, ticker in TREASURY_TICKERS.items():
                quote = yf.get_quote(ticker)
                price = quote.get("regularMarketPrice")
                if price is not None:
                    yields[label] = round(float(price), 3)

            if not yields:
                return json.dumps({"status": "error", "error": "No treasury yield data available"})

            curve_shape = _classify_curve(yields)
            trend = _compute_trend(yields)

            # Compute key spreads
            spreads: dict[str, float] = {}
            if "3_month" in yields and "10_year" in yields:
                spreads["3m_10y"] = round(yields["10_year"] - yields["3_month"], 3)
            if "10_year" in yields and "30_year" in yields:
                spreads["10y_30y"] = round(yields["30_year"] - yields["10_year"], 3)
            if "5_year" in yields and "30_year" in yields:
                spreads["5y_30y"] = round(yields["30_year"] - yields["5_year"], 3)

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "yields": yields,
                    "curve_shape": curve_shape,
                    "trend": trend,
                    "spreads": spreads,
                },
            }
            cache.set(cache_key, "treasury_yields", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("treasury_yields_error", error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
