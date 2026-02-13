"""Market regime detection tool."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)

MIN_DATA_POINTS = 60


def _detect_regime(
    returns: np.ndarray, closes: np.ndarray
) -> tuple[str, float, dict[str, Any]]:
    """Detect market regime from returns and prices.

    Returns (regime, confidence, metrics).
    """
    # Rolling metrics
    short_window = min(20, len(returns))
    long_window = min(60, len(returns))

    recent_returns = returns[-short_window:]
    recent_vol = float(np.std(recent_returns, ddof=1) * np.sqrt(252))
    long_vol = float(np.std(returns[-long_window:], ddof=1) * np.sqrt(252))

    # Mean return (annualized)
    mean_return_short = float(np.mean(recent_returns) * 252)
    mean_return_long = float(np.mean(returns[-long_window:]) * 252)

    # Trend via simple moving average comparison
    sma_20 = float(np.mean(closes[-20:])) if len(closes) >= 20 else float(closes[-1])
    sma_50 = float(np.mean(closes[-50:])) if len(closes) >= 50 else sma_20
    current_price = float(closes[-1])

    metrics = {
        "short_term_vol": round(recent_vol, 4),
        "long_term_vol": round(long_vol, 4),
        "short_term_return": round(mean_return_short, 4),
        "long_term_return": round(mean_return_long, 4),
        "sma_20": round(sma_20, 2),
        "sma_50": round(sma_50, 2),
        "price_vs_sma20": round((current_price / sma_20 - 1) * 100, 2),
        "price_vs_sma50": round((current_price / sma_50 - 1) * 100, 2),
    }

    # Classification logic
    vol_threshold = 0.30  # 30% annualized vol considered "high"
    trend_threshold = 0.10  # 10% annualized return threshold

    # High volatility regime takes priority
    if recent_vol > vol_threshold:
        confidence = min(recent_vol / vol_threshold, 1.0)
        return "high_volatility", round(confidence, 4), metrics

    # Trending up
    if mean_return_short > trend_threshold and current_price > sma_20 > sma_50:
        confidence = min(abs(mean_return_short) / trend_threshold * 0.5, 1.0)
        return "trending_up", round(confidence, 4), metrics

    # Trending down
    if mean_return_short < -trend_threshold and current_price < sma_20 < sma_50:
        confidence = min(abs(mean_return_short) / trend_threshold * 0.5, 1.0)
        return "trending_down", round(confidence, 4), metrics

    # Range-bound
    high = float(np.max(closes[-short_window:]))
    low = float(np.min(closes[-short_window:]))
    price_range = (high - low) / current_price
    confidence = max(0.3, 1.0 - price_range * 5)  # Higher confidence for tighter ranges
    return "range_bound", round(min(confidence, 1.0), 4), metrics


def register(mcp: FastMCP) -> None:
    """Register regime detection tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_regime_detection(ticker: str) -> str:
        """Detect current market regime for a ticker.

        Classifies regime as trending_up, trending_down, range_bound, or high_volatility
        using rolling returns, volatility, and moving average analysis.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
        """
        cache_key = cache.make_key("regime", ticker=ticker)
        cached = cache.get(cache_key, "quant_models")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            history = yf.get_history(ticker, period="6mo")
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

            returns = np.diff(np.log(closes))
            regime, confidence, metrics = _detect_regime(returns, closes)

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "regime": regime,
                    "confidence": confidence,
                    "current_price": round(float(closes[-1]), 2),
                    "metrics": metrics,
                },
            }
            cache.set(cache_key, "quant_models", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("regime_detection_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
