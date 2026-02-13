"""Return distribution analysis tool."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.models import compute_cvar, compute_return_stats, compute_var

logger = structlog.get_logger(__name__)

MIN_DATA_POINTS = 30


def register(mcp: FastMCP) -> None:
    """Register return distribution tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_return_distribution(ticker: str, period: str = "1y") -> str:
        """Analyze return distribution with statistical tests, VaR, and CVaR.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
            period: Historical period for analysis (default '1y').
        """
        cache_key = cache.make_key(
            "return_dist", ticker=ticker, period=period
        )
        cached = cache.get(cache_key, "quant_models")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            history = yf.get_history(ticker, period=period)
            if not history or len(history) < MIN_DATA_POINTS:
                return json.dumps(
                    {
                        "status": "error",
                        "error": (
                            f"Insufficient data for {ticker}"
                            f" (need >= {MIN_DATA_POINTS},"
                            f" got {len(history) if history else 0})"
                        ),
                    }
                )

            closes = np.array(
                [r["Close"] for r in history if r.get("Close") is not None],
                dtype=float,
            )
            if len(closes) < MIN_DATA_POINTS:
                return json.dumps(
                    {"status": "error", "error": "Insufficient valid price data"}
                )

            returns = np.diff(closes) / closes[:-1]

            stats = compute_return_stats(returns)
            var_95 = compute_var(returns, confidence=0.95)
            var_99 = compute_var(returns, confidence=0.99)
            cvar_95 = compute_cvar(returns, confidence=0.95)
            cvar_99 = compute_cvar(returns, confidence=0.99)

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "period": period,
                    "observations": len(returns),
                    **stats,
                    "var": {
                        "95_pct": var_95,
                        "99_pct": var_99,
                    },
                    "cvar": {
                        "95_pct": cvar_95,
                        "99_pct": cvar_99,
                    },
                    "annualized_return": round(float(np.mean(returns) * 252), 4),
                    "annualized_vol": round(float(np.std(returns, ddof=1) * np.sqrt(252)), 4),
                },
            }
            cache.set(cache_key, "quant_models", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("return_distribution_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
