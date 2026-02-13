"""ARIMA price forecast tool."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.models import fit_arima

logger = structlog.get_logger(__name__)

MIN_DATA_POINTS = 60


def register(mcp: FastMCP) -> None:
    """Register price forecast tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_price_forecast(
        ticker: str, horizon_days: int = 30, model: str = "arima"
    ) -> str:
        """Forecast future prices using ARIMA time series model.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
            horizon_days: Number of days to forecast (default 30).
            model: Forecasting model to use (currently 'arima' supported).
        """
        cache_key = cache.make_key(
            "price_forecast", ticker=ticker, horizon=horizon_days, model=model
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
                            f"Insufficient data for {ticker}"
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
                    {"status": "error", "error": "Insufficient valid price data"}
                )

            # Compute log returns for ARIMA
            log_returns = np.diff(np.log(closes))
            arima_result = fit_arima(log_returns)

            # Convert log return forecasts back to price levels
            last_price = float(closes[-1])
            forecast_returns = arima_result.get("forecast", [])[:horizon_days]

            if not forecast_returns:
                return json.dumps(
                    {"status": "error", "error": "ARIMA model failed to produce forecast"}
                )

            forecast_prices = []
            cumulative = 0.0
            for ret in forecast_returns:
                cumulative += ret
                forecast_prices.append(round(last_price * np.exp(cumulative), 2))

            # Simple confidence intervals based on historical volatility
            vol = float(np.std(log_returns))
            upper = [
                round(p * np.exp(1.96 * vol * np.sqrt(i + 1)), 2)
                for i, p in enumerate(forecast_prices)
            ]
            lower = [
                round(p * np.exp(-1.96 * vol * np.sqrt(i + 1)), 2)
                for i, p in enumerate(forecast_prices)
            ]

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "model": model,
                    "current_price": round(last_price, 2),
                    "horizon_days": horizon_days,
                    "forecast": forecast_prices,
                    "upper_bound": upper,
                    "lower_bound": lower,
                    "arima_order": arima_result.get("order"),
                    "aic": arima_result.get("aic"),
                },
            }
            cache.set(cache_key, "quant_models", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("price_forecast_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
