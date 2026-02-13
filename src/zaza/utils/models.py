"""Shared quantitative model helpers."""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


def fit_arima(returns: np.ndarray, order: tuple[int, int, int] | None = None) -> dict[str, Any]:
    """Fit ARIMA model with automatic order selection."""
    import warnings

    from statsmodels.tsa.arima.model import ARIMA

    warnings.filterwarnings("ignore")

    if order:
        try:
            model = ARIMA(returns, order=order).fit()
            forecast = model.forecast(steps=30)
            return {
                "order": list(order),
                "aic": round(float(model.aic), 2),
                "forecast": [round(float(x), 6) for x in forecast],
            }
        except Exception as e:
            logger.warning("arima_fit_error", order=order, error=str(e))
            return {"order": list(order), "aic": None, "forecast": [], "error": str(e)}

    best_aic = float("inf")
    best_order = (1, 1, 1)
    for p in range(3):
        for d in range(2):
            for q in range(3):
                try:
                    m = ARIMA(returns, order=(p, d, q)).fit()
                    if m.aic < best_aic:
                        best_aic, best_order = m.aic, (p, d, q)
                except Exception:
                    continue
    try:
        model = ARIMA(returns, order=best_order).fit()
        forecast = model.forecast(steps=30)
        return {
            "order": list(best_order),
            "aic": round(float(model.aic), 2),
            "forecast": [round(float(x), 6) for x in forecast],
        }
    except Exception as e:
        return {"order": list(best_order), "aic": None, "forecast": [], "error": str(e)}


def fit_garch(returns: np.ndarray) -> dict[str, Any]:
    """Fit GARCH(1,1) volatility model."""
    import warnings

    from arch import arch_model

    warnings.filterwarnings("ignore")

    if len(returns) < 252:
        return {"error": "Insufficient data (need >= 252 observations)"}
    try:
        scaled = returns * 100
        model = arch_model(scaled, vol="Garch", p=1, q=1, mean="constant")
        result = model.fit(disp="off")
        forecast = result.forecast(horizon=30)
        var_forecast = forecast.variance.iloc[-1].values
        vol_forecast = np.sqrt(var_forecast) / 100
        return {
            "params": {k: round(float(v), 6) for k, v in result.params.items()},
            "aic": round(float(result.aic), 2),
            "forecasted_vol_30d": [round(float(v), 6) for v in vol_forecast],
            "annualized_vol": round(float(np.mean(vol_forecast) * np.sqrt(252)), 4),
        }
    except Exception as e:
        logger.warning("garch_error", error=str(e))
        return {"error": str(e)}


def monte_carlo_gbm(
    price: float,
    mu: float,
    sigma: float,
    days: int,
    n_sims: int = 10000,
    seed: int | None = None,
) -> dict[str, Any]:
    """Run Geometric Brownian Motion Monte Carlo simulation."""
    rng = np.random.default_rng(seed)
    dt = 1 / 252
    paths = np.zeros((n_sims, days + 1))
    paths[:, 0] = price
    for t in range(1, days + 1):
        z = rng.standard_normal(n_sims)
        paths[:, t] = paths[:, t - 1] * np.exp(
            (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z
        )
    final = paths[:, -1]
    percentiles = {
        f"p{p}": round(float(np.percentile(final, p)), 2) for p in [5, 25, 50, 75, 95]
    }
    prob_up_5 = float(np.mean(final > price * 1.05))
    prob_down_5 = float(np.mean(final < price * 0.95))
    return {
        "percentiles": percentiles,
        "prob_up_5pct": round(prob_up_5, 4),
        "prob_down_5pct": round(prob_down_5, 4),
        "mean_price": round(float(np.mean(final)), 2),
        "median_price": round(float(np.median(final)), 2),
    }


def compute_hurst_exponent(prices: np.ndarray) -> float:
    """Compute Hurst exponent via rescaled range analysis."""
    n = len(prices)
    if n < 20:
        return 0.5
    max_k = min(n // 2, 100)
    rs_list = []
    sizes = []
    for size in range(10, max_k + 1, 5):
        rs_vals = []
        for start in range(0, n - size + 1, size):
            chunk = prices[start : start + size]
            mean = np.mean(chunk)
            deviations = np.cumsum(chunk - mean)
            r = np.max(deviations) - np.min(deviations)
            s = np.std(chunk, ddof=1)
            if s > 0:
                rs_vals.append(r / s)
        if rs_vals:
            rs_list.append(np.mean(rs_vals))
            sizes.append(size)
    if len(rs_list) < 2:
        return 0.5
    log_sizes = np.log(sizes)
    log_rs = np.log(rs_list)
    slope = np.polyfit(log_sizes, log_rs, 1)[0]
    return round(float(np.clip(slope, 0, 1)), 4)


def compute_half_life(prices: np.ndarray) -> float | None:
    """Compute Ornstein-Uhlenbeck half-life of mean reversion."""
    if len(prices) < 20:
        return None
    log_prices = np.log(prices)
    lag = log_prices[:-1]
    diff = np.diff(log_prices)
    lag_centered = lag - np.mean(lag)
    if np.sum(lag_centered**2) == 0:
        return None
    beta = np.sum(lag_centered * diff) / np.sum(lag_centered**2)
    if beta >= 0:
        return None
    half_life = -np.log(2) / beta
    return round(float(half_life), 2)


def compute_return_stats(returns: np.ndarray) -> dict[str, Any]:
    """Compute return distribution statistics."""
    from scipy import stats

    return {
        "mean": round(float(np.mean(returns)), 6),
        "std": round(float(np.std(returns, ddof=1)), 6),
        "skewness": round(float(stats.skew(returns)), 4),
        "kurtosis": round(float(stats.kurtosis(returns)), 4),
        "jarque_bera_stat": round(float(stats.jarque_bera(returns).statistic), 4),
        "jarque_bera_pvalue": round(float(stats.jarque_bera(returns).pvalue), 4),
        "max_drawdown": round(float(_max_drawdown(returns)), 4),
    }


def _max_drawdown(returns: np.ndarray) -> float:
    """Compute maximum drawdown from returns."""
    cumulative = np.cumprod(1 + returns)
    peak = np.maximum.accumulate(cumulative)
    drawdown = (peak - cumulative) / peak
    return float(np.max(drawdown)) if len(drawdown) > 0 else 0.0


def compute_var(returns: np.ndarray, confidence: float = 0.95) -> dict[str, float]:
    """Compute Value at Risk."""
    sorted_returns = np.sort(returns)
    idx = int(len(sorted_returns) * (1 - confidence))
    historical_var = float(sorted_returns[idx]) if idx < len(sorted_returns) else 0.0
    parametric_var = float(np.mean(returns) - np.std(returns) * 1.645)
    return {
        "historical_var": round(historical_var, 6),
        "parametric_var": round(parametric_var, 6),
    }


def compute_cvar(returns: np.ndarray, confidence: float = 0.95) -> float:
    """Compute Conditional VaR (Expected Shortfall)."""
    sorted_returns = np.sort(returns)
    idx = int(len(sorted_returns) * (1 - confidence))
    tail = sorted_returns[: idx + 1]
    return round(float(np.mean(tail)), 6) if len(tail) > 0 else 0.0
