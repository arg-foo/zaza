"""GARCH volatility forecast tool."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.models import fit_garch

logger = structlog.get_logger(__name__)

MIN_DATA_POINTS = 252


def register(mcp: FastMCP) -> None:
    """Register volatility forecast tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_volatility_forecast(ticker: str, horizon_days: int = 30) -> str:
        """Forecast volatility using GARCH(1,1) model.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
            horizon_days: Number of days to forecast (default 30).
        """
        cache_key = cache.make_key(
            "vol_forecast", ticker=ticker, horizon=horizon_days
        )
        cached = cache.get(cache_key, "quant_models")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            history = yf.get_history(ticker, period="2y")
            if not history or len(history) < MIN_DATA_POINTS:
                return json.dumps(
                    {
                        "status": "error",
                        "error": (
                            f"Insufficient data for GARCH"
                            f" (need >= {MIN_DATA_POINTS} data points,"
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
                    {"status": "error", "error": "Insufficient valid price data for GARCH"}
                )

            returns = np.diff(np.log(closes))
            garch_result = fit_garch(returns)

            if "error" in garch_result:
                return json.dumps({"status": "error", "error": garch_result["error"]})

            # Current realized volatility for comparison
            realized_vol_30d = round(float(np.std(returns[-30:]) * np.sqrt(252)), 4)
            realized_vol_60d = round(float(np.std(returns[-60:]) * np.sqrt(252)), 4)

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "horizon_days": horizon_days,
                    "annualized_vol": garch_result.get("annualized_vol"),
                    "forecasted_vol": garch_result.get("forecasted_vol_30d", [])[:horizon_days],
                    "garch_params": garch_result.get("params"),
                    "aic": garch_result.get("aic"),
                    "realized_vol_30d": realized_vol_30d,
                    "realized_vol_60d": realized_vol_60d,
                },
            }
            cache.set(cache_key, "quant_models", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("volatility_forecast_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
