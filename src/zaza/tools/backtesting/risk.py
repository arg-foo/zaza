"""Risk metrics tool -- Sharpe, Sortino, max drawdown, beta, alpha, VaR/CVaR.

Uses compute_return_stats, compute_var, compute_cvar from utils/models.py.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.indicators import ohlcv_to_dataframe
from zaza.utils.models import compute_cvar, compute_return_stats, compute_var

logger = structlog.get_logger(__name__)


def _compute_risk_metrics(
    returns: np.ndarray, benchmark_returns: np.ndarray
) -> dict[str, Any]:
    """Compute comprehensive risk metrics."""
    # Basic stats
    stats = compute_return_stats(returns)

    # Sharpe ratio (annualized, risk-free rate assumed 0 for simplicity)
    mean_ret = float(np.mean(returns))
    std_ret = float(np.std(returns, ddof=1))
    sharpe = round(mean_ret / std_ret * np.sqrt(252), 4) if std_ret > 0 else None

    # Sortino ratio (downside deviation)
    downside = returns[returns < 0]
    downside_std = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0.0
    sortino = (
        round(mean_ret / downside_std * np.sqrt(252), 4) if downside_std > 0 else None
    )

    # Beta and alpha (vs benchmark)
    min_len = min(len(returns), len(benchmark_returns))
    r = returns[:min_len]
    b = benchmark_returns[:min_len]

    cov = np.cov(r, b)
    beta = round(float(cov[0, 1] / cov[1, 1]), 4) if cov[1, 1] > 0 else None

    alpha = None
    if beta is not None:
        # Jensen's alpha (annualized)
        alpha = round(
            (float(np.mean(r)) - beta * float(np.mean(b))) * 252, 6
        )

    # VaR and CVaR
    var_data = compute_var(returns, confidence=0.95)
    cvar_val = compute_cvar(returns, confidence=0.95)

    return {
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": stats["max_drawdown"],
        "beta": beta,
        "alpha": alpha,
        "var_95": var_data,
        "cvar_95": cvar_val,
        "annualized_return": round(mean_ret * 252, 6),
        "annualized_volatility": round(std_ret * np.sqrt(252), 6),
        "skewness": stats["skewness"],
        "kurtosis": stats["kurtosis"],
    }


def register(mcp: FastMCP) -> None:
    """Register the risk metrics tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_risk_metrics(
        ticker: str,
        benchmark: str = "SPY",
        period: str = "1y",
    ) -> str:
        """Compute risk metrics for a ticker vs a benchmark.

        Args:
            ticker: Stock ticker symbol.
            benchmark: Benchmark ticker (default SPY).
            period: Historical period (default 1y).

        Returns:
            JSON with Sharpe, Sortino, max drawdown, beta, alpha, VaR, CVaR.
        """
        try:
            cache_key = cache.make_key(
                "risk_metrics", ticker=ticker, benchmark=benchmark, period=period
            )
            cached = cache.get(cache_key, "risk_metrics")
            if cached is not None:
                return json.dumps(cached, default=str)

            ticker_history = yf.get_history(ticker, period=period)
            if not ticker_history:
                return json.dumps(
                    {"error": f"No historical data for {ticker}"},
                    default=str,
                )

            benchmark_history = yf.get_history(benchmark, period=period)
            if not benchmark_history:
                return json.dumps(
                    {"error": f"No historical data for benchmark {benchmark}"},
                    default=str,
                )

            ticker_df = ohlcv_to_dataframe(ticker_history)
            benchmark_df = ohlcv_to_dataframe(benchmark_history)

            ticker_returns = ticker_df["Close"].pct_change().dropna().values
            benchmark_returns = benchmark_df["Close"].pct_change().dropna().values

            if len(ticker_returns) < 10:
                return json.dumps(
                    {"error": "Insufficient data to compute risk metrics"},
                    default=str,
                )

            metrics = _compute_risk_metrics(ticker_returns, benchmark_returns)
            result = {
                "ticker": ticker,
                "benchmark": benchmark,
                "period": period,
                "data_points": len(ticker_returns),
                **metrics,
            }

            cache.set(cache_key, "risk_metrics", result)
            return json.dumps(result, default=str)

        except Exception as e:
            logger.warning("risk_metrics_error", ticker=ticker, error=str(e))
            return json.dumps({"error": str(e)}, default=str)
