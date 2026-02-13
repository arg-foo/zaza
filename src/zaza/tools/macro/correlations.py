"""Intermarket correlation tool."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)

BENCHMARK_TICKERS = {
    "SP500": "^GSPC",
    "Treasury_10Y": "^TNX",
    "US_Dollar": "DX-Y.NYB",
    "Crude_Oil": "CL=F",
    "Gold": "GC=F",
}


def _compute_rolling_corr(
    returns_a: np.ndarray, returns_b: np.ndarray, window: int
) -> float | None:
    """Compute rolling correlation over the last `window` days."""
    if len(returns_a) < window or len(returns_b) < window:
        return None
    a = returns_a[-window:]
    b = returns_b[-window:]
    if np.std(a) == 0 or np.std(b) == 0:
        return None
    corr = float(np.corrcoef(a, b)[0, 1])
    return round(corr, 4)


def register(mcp: FastMCP) -> None:
    """Register intermarket correlations tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_intermarket_correlations(ticker: str) -> str:
        """Get rolling correlations between a ticker and major benchmarks.

        Computes 30, 60, and 90-day rolling correlations with S&P 500, 10Y Treasury,
        US Dollar, Crude Oil, and Gold.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
        """
        cache_key = cache.make_key("correlations", ticker=ticker)
        cached = cache.get(cache_key, "correlations")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            # Fetch target ticker history
            target_history = yf.get_history(ticker, period="6mo")
            if not target_history or len(target_history) < 30:
                return json.dumps(
                    {"status": "error", "error": f"Insufficient data for {ticker}"}
                )

            target_closes = np.array(
                [r["Close"] for r in target_history if r.get("Close") is not None],
                dtype=float,
            )
            if len(target_closes) < 30:
                return json.dumps(
                    {"status": "error", "error": f"Insufficient price data for {ticker}"}
                )

            target_returns = np.diff(np.log(target_closes))

            correlations: dict[str, dict[str, float | None]] = {}

            for label, bench_ticker in BENCHMARK_TICKERS.items():
                bench_history = yf.get_history(bench_ticker, period="6mo")
                if not bench_history:
                    correlations[label] = {"30d": None, "60d": None, "90d": None}
                    continue

                bench_closes = np.array(
                    [r["Close"] for r in bench_history if r.get("Close") is not None],
                    dtype=float,
                )
                if len(bench_closes) < 30:
                    correlations[label] = {"30d": None, "60d": None, "90d": None}
                    continue

                bench_returns = np.diff(np.log(bench_closes))

                # Align lengths
                min_len = min(len(target_returns), len(bench_returns))
                t_ret = target_returns[-min_len:]
                b_ret = bench_returns[-min_len:]

                correlations[label] = {
                    "30d": _compute_rolling_corr(t_ret, b_ret, 30),
                    "60d": _compute_rolling_corr(t_ret, b_ret, 60),
                    "90d": _compute_rolling_corr(t_ret, b_ret, 90),
                }

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "correlations": correlations,
                },
            }
            cache.set(cache_key, "correlations", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("correlations_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
