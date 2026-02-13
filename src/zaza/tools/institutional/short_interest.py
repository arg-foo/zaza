"""Short interest analysis tool."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def _compute_squeeze_score(
    short_pct_float: float, short_ratio: float, avg_volume: float, shares_short: float
) -> float:
    """Compute short squeeze potential score (0-10 scale).

    Factors:
    - Short percent of float (higher = more squeeze potential)
    - Short ratio / days to cover (higher = harder to cover)
    - Shares short relative to average volume
    """
    score = 0.0

    # Short % of float contribution (0-4 points)
    if short_pct_float >= 0.30:
        score += 4.0
    elif short_pct_float >= 0.20:
        score += 3.0
    elif short_pct_float >= 0.10:
        score += 2.0
    elif short_pct_float >= 0.05:
        score += 1.0

    # Days to cover contribution (0-3 points)
    if short_ratio >= 7:
        score += 3.0
    elif short_ratio >= 4:
        score += 2.0
    elif short_ratio >= 2:
        score += 1.0

    # Volume pressure contribution (0-3 points)
    if avg_volume > 0 and shares_short > 0:
        coverage_days = shares_short / avg_volume
        if coverage_days >= 5:
            score += 3.0
        elif coverage_days >= 3:
            score += 2.0
        elif coverage_days >= 1:
            score += 1.0

    return round(score, 1)


def register(mcp: FastMCP) -> None:
    """Register short interest tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_short_interest(ticker: str) -> str:
        """Get short interest data with squeeze potential score.

        Returns short percent of float, shares short, short ratio (days to cover),
        and a computed squeeze score (0-10 scale).

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
        """
        cache_key = cache.make_key("short_interest", ticker=ticker)
        cached = cache.get(cache_key, "short_interest")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            quote = yf.get_quote(ticker)
            if not quote or "regularMarketPrice" not in quote:
                return json.dumps(
                    {"status": "error", "error": f"No quote data available for {ticker}"}
                )

            short_pct_float = float(quote.get("shortPercentOfFloat", 0) or 0)
            shares_short = float(quote.get("sharesShort", 0) or 0)
            short_ratio = float(quote.get("shortRatio", 0) or 0)
            avg_volume = float(quote.get("averageVolume", 0) or 0)
            shares_outstanding = float(quote.get("sharesOutstanding", 0) or 0)

            squeeze_score = _compute_squeeze_score(
                short_pct_float, short_ratio, avg_volume, shares_short
            )

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "short_percent_of_float": round(short_pct_float, 4),
                    "shares_short": int(shares_short),
                    "short_ratio": round(short_ratio, 2),
                    "average_volume": int(avg_volume),
                    "shares_outstanding": int(shares_outstanding),
                    "squeeze_score": squeeze_score,
                    "squeeze_risk": (
                        "high" if squeeze_score >= 7
                        else "moderate" if squeeze_score >= 4
                        else "low"
                    ),
                },
            }
            cache.set(cache_key, "short_interest", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("short_interest_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
