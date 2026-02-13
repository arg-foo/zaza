"""Signal backtest tool -- backtest a technical signal on historical data.

Supports RSI, MACD, golden/death cross, Bollinger, and volume spike signals.
No look-ahead bias: only data available at signal date is used.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
import structlog
import ta
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.indicators import ohlcv_to_dataframe

logger = structlog.get_logger(__name__)

SUPPORTED_SIGNALS = [
    "rsi_below_30",
    "rsi_above_70",
    "macd_crossover",
    "golden_cross",
    "death_cross",
    "bollinger_lower_touch",
    "volume_spike",
]


def _detect_signals(df: pd.DataFrame, signal: str) -> list[int]:
    """Return list of bar indices where signal fires.

    Only uses data up to and including each bar (no look-ahead).
    """
    indices: list[int] = []
    close = df["Close"]

    if signal == "rsi_below_30":
        rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
        for i in range(14, len(df)):
            if rsi.iloc[i] < 30:
                indices.append(i)

    elif signal == "rsi_above_70":
        rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
        for i in range(14, len(df)):
            if rsi.iloc[i] > 70:
                indices.append(i)

    elif signal == "macd_crossover":
        macd_ind = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
        hist = macd_ind.macd_diff()
        for i in range(27, len(df)):
            if not np.isnan(hist.iloc[i]) and not np.isnan(hist.iloc[i - 1]):
                if hist.iloc[i] > 0 and hist.iloc[i - 1] <= 0:
                    indices.append(i)

    elif signal == "golden_cross":
        sma50 = close.rolling(50).mean()
        sma200 = close.rolling(200).mean()
        for i in range(200, len(df)):
            if (
                not np.isnan(sma50.iloc[i])
                and not np.isnan(sma200.iloc[i])
                and sma50.iloc[i] > sma200.iloc[i]
                and sma50.iloc[i - 1] <= sma200.iloc[i - 1]
            ):
                indices.append(i)

    elif signal == "death_cross":
        sma50 = close.rolling(50).mean()
        sma200 = close.rolling(200).mean()
        for i in range(200, len(df)):
            if (
                not np.isnan(sma50.iloc[i])
                and not np.isnan(sma200.iloc[i])
                and sma50.iloc[i] < sma200.iloc[i]
                and sma50.iloc[i - 1] >= sma200.iloc[i - 1]
            ):
                indices.append(i)

    elif signal == "bollinger_lower_touch":
        bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        lower = bb.bollinger_lband()
        for i in range(20, len(df)):
            if not np.isnan(lower.iloc[i]) and df["Low"].iloc[i] <= lower.iloc[i]:
                indices.append(i)

    elif signal == "volume_spike":
        vol = df["Volume"]
        for i in range(20, len(df)):
            avg_vol = vol.iloc[i - 20 : i].mean()
            if avg_vol > 0 and vol.iloc[i] > 2 * avg_vol:
                indices.append(i)

    return indices


def _compute_forward_returns(
    df: pd.DataFrame, signal_indices: list[int]
) -> dict[str, Any]:
    """Compute forward returns at 5d, 20d, 60d horizons for each signal.

    No look-ahead bias: returns are computed from signal date forward.
    Signals too close to the end of the data are excluded for that horizon.
    """
    horizons = {"5d": 5, "20d": 20, "60d": 60}
    returns_by_horizon: dict[str, list[float]] = {k: [] for k in horizons}
    all_returns: list[float] = []

    for idx in signal_indices:
        entry_price = float(df["Close"].iloc[idx])
        for label, days in horizons.items():
            exit_idx = idx + days
            if exit_idx < len(df):
                exit_price = float(df["Close"].iloc[exit_idx])
                ret = (exit_price - entry_price) / entry_price
                returns_by_horizon[label].append(ret)
        # Use max available horizon for best/worst
        max_exit = min(idx + 60, len(df) - 1)
        if max_exit > idx:
            ret = (float(df["Close"].iloc[max_exit]) - entry_price) / entry_price
            all_returns.append(ret)

    result: dict[str, Any] = {"total_signals": len(signal_indices)}

    for label in horizons:
        rets = returns_by_horizon[label]
        if rets:
            wins = sum(1 for r in rets if r > 0)
            result[f"win_rate_{label}"] = round(wins / len(rets), 4)
            result[f"avg_return_{label}"] = round(float(np.mean(rets)), 6)
        else:
            result[f"win_rate_{label}"] = None
            result[f"avg_return_{label}"] = None

    if all_returns:
        result["best_trade"] = round(max(all_returns), 6)
        result["worst_trade"] = round(min(all_returns), 6)
        gains = [r for r in all_returns if r > 0]
        losses = [abs(r) for r in all_returns if r < 0]
        total_gain = sum(gains) if gains else 0
        total_loss = sum(losses) if losses else 0
        result["profit_factor"] = (
            round(total_gain / total_loss, 4) if total_loss > 0 else None
        )
    else:
        result["best_trade"] = None
        result["worst_trade"] = None
        result["profit_factor"] = None

    return result


def register(mcp: FastMCP) -> None:
    """Register the signal backtest tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_signal_backtest(
        ticker: str,
        signal: str,
        lookback_years: int = 5,
    ) -> str:
        """Backtest a technical signal on historical data.

        Args:
            ticker: Stock ticker symbol.
            signal: Signal type. One of: rsi_below_30, rsi_above_70,
                    macd_crossover, golden_cross, death_cross,
                    bollinger_lower_touch, volume_spike.
            lookback_years: Number of years of history to use (default 5).

        Returns:
            JSON with total signals, win rates at 5d/20d/60d, avg return,
            best/worst trade, and profit factor.
        """
        try:
            if signal not in SUPPORTED_SIGNALS:
                return json.dumps(
                    {"error": f"Unsupported signal '{signal}'. Supported: {SUPPORTED_SIGNALS}"},
                    default=str,
                )

            cache_key = cache.make_key(
                "signal_backtest", ticker=ticker, signal=signal, years=lookback_years
            )
            cached = cache.get(cache_key, "backtest_results")
            if cached is not None:
                return json.dumps(cached, default=str)

            period = f"{lookback_years}y"
            history = yf.get_history(ticker, period=period)
            if not history:
                return json.dumps(
                    {"error": f"No historical data for {ticker}"},
                    default=str,
                )

            df = ohlcv_to_dataframe(history)
            signal_indices = _detect_signals(df, signal)
            forward = _compute_forward_returns(df, signal_indices)

            result = {
                "ticker": ticker,
                "signal": signal,
                "lookback_years": lookback_years,
                "data_points": len(df),
                **forward,
            }

            cache.set(cache_key, "backtest_results", result)
            return json.dumps(result, default=str)

        except Exception as e:
            logger.warning("signal_backtest_error", ticker=ticker, error=str(e))
            return json.dumps({"error": str(e)}, default=str)
