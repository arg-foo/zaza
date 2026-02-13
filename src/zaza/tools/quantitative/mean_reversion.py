"""Mean reversion analysis tool."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.models import compute_half_life, compute_hurst_exponent

logger = structlog.get_logger(__name__)

MIN_DATA_POINTS = 60


def register(mcp: FastMCP) -> None:
    """Register mean reversion tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_mean_reversion(ticker: str) -> str:
        """Analyze mean reversion characteristics using Hurst exponent, half-life, and z-scores.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
        """
        cache_key = cache.make_key("mean_reversion", ticker=ticker)
        cached = cache.get(cache_key, "quant_models")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            history = yf.get_history(ticker, period="1y")
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

            # Compute Hurst exponent on log returns
            log_returns = np.diff(np.log(closes))
            hurst = compute_hurst_exponent(log_returns)

            # Compute half-life of mean reversion
            half_life = compute_half_life(closes)

            # Compute z-scores at various windows
            current = float(closes[-1])
            z_scores: dict[str, float] = {}
            for window in [20, 50, 100, 200]:
                if len(closes) >= window:
                    window_data = closes[-window:]
                    mean = float(np.mean(window_data))
                    std = float(np.std(window_data, ddof=1))
                    if std > 0:
                        z_scores[f"{window}d"] = round((current - mean) / std, 4)

            # Classify mean reversion tendency
            if hurst < 0.4:
                tendency = "mean_reverting"
            elif hurst > 0.6:
                tendency = "trending"
            else:
                tendency = "random_walk"

            if hurst < 0.4:
                hurst_label = "Mean-reverting"
            elif hurst > 0.6:
                hurst_label = "Trending"
            else:
                hurst_label = "Random walk"

            hl_text = (
                f"Half-life: {half_life} days."
                if half_life
                else "No significant mean reversion detected."
            )

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "current_price": round(current, 2),
                    "hurst_exponent": hurst,
                    "half_life_days": half_life,
                    "tendency": tendency,
                    "z_score": z_scores.get("20d", 0.0),
                    "z_scores": z_scores,
                    "interpretation": (
                        f"Hurst={hurst}: {hurst_label}. {hl_text}"
                    ),
                },
            }
            cache.set(cache_key, "quant_models", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("mean_reversion_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
