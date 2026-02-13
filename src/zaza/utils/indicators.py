"""Shared technical analysis computation helpers."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import structlog
import ta

logger = structlog.get_logger(__name__)


def ohlcv_to_dataframe(data: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert OHLCV list of dicts to a DataFrame with standard column names."""
    df = pd.DataFrame(data)
    # Standardize column names
    col_map = {}
    for col in df.columns:
        lower = col.lower()
        if lower in ("open",):
            col_map[col] = "Open"
        elif lower in ("high",):
            col_map[col] = "High"
        elif lower in ("low",):
            col_map[col] = "Low"
        elif lower in ("close", "adj close", "adjclose"):
            col_map[col] = "Close"
        elif lower in ("volume",):
            col_map[col] = "Volume"
    df = df.rename(columns=col_map)
    for required in ["Open", "High", "Low", "Close", "Volume"]:
        if required not in df.columns:
            df[required] = np.nan
    return df


def compute_sma(df: pd.DataFrame, periods: list[int] | None = None) -> dict[str, Any]:
    """Compute Simple Moving Averages."""
    periods = periods or [20, 50, 200]
    close = df["Close"]
    current = float(close.iloc[-1])
    result: dict[str, Any] = {"current_price": current, "sma": {}}
    for p in periods:
        if len(df) >= p:
            sma_val = float(close.rolling(p).mean().iloc[-1])
            result["sma"][f"sma_{p}"] = round(sma_val, 2)
            result["sma"][f"price_vs_sma_{p}"] = "above" if current > sma_val else "below"
        else:
            result["sma"][f"sma_{p}"] = None
    # Golden/Death cross
    if len(df) >= 200:
        sma50 = close.rolling(50).mean()
        sma200 = close.rolling(200).mean()
        if sma50.iloc[-1] > sma200.iloc[-1] and sma50.iloc[-2] <= sma200.iloc[-2]:
            result["cross"] = "golden_cross"
        elif sma50.iloc[-1] < sma200.iloc[-1] and sma50.iloc[-2] >= sma200.iloc[-2]:
            result["cross"] = "death_cross"
        else:
            result["cross"] = "above" if sma50.iloc[-1] > sma200.iloc[-1] else "below"
    return result


def compute_ema(df: pd.DataFrame, periods: list[int] | None = None) -> dict[str, Any]:
    """Compute Exponential Moving Averages."""
    periods = periods or [12, 26]
    close = df["Close"]
    result: dict[str, Any] = {}
    for p in periods:
        if len(df) >= p:
            result[f"ema_{p}"] = round(float(close.ewm(span=p).mean().iloc[-1]), 2)
        else:
            result[f"ema_{p}"] = None
    return result


def compute_rsi(df: pd.DataFrame, period: int = 14) -> dict[str, Any]:
    """Compute RSI with signal classification."""
    rsi = ta.momentum.RSIIndicator(df["Close"], window=period).rsi()
    value = round(float(rsi.iloc[-1]), 2) if not np.isnan(rsi.iloc[-1]) else None
    if value is None:
        return {"rsi_14": None, "signal": "insufficient_data"}
    if value > 70:
        signal = "overbought"
    elif value > 60:
        signal = "approaching_overbought"
    elif value < 30:
        signal = "oversold"
    elif value < 40:
        signal = "approaching_oversold"
    else:
        signal = "neutral"
    return {"rsi_14": value, "signal": signal}


def compute_macd(df: pd.DataFrame) -> dict[str, Any]:
    """Compute MACD(12,26,9) with signal and histogram."""
    macd_ind = ta.trend.MACD(df["Close"], window_slow=26, window_fast=12, window_sign=9)
    macd_val = macd_ind.macd().iloc[-1]
    signal_val = macd_ind.macd_signal().iloc[-1]
    hist_val = macd_ind.macd_diff().iloc[-1]
    if np.isnan(macd_val):
        return {"macd": None, "signal_line": None, "histogram": None, "signal": "insufficient_data"}
    signal = "bullish" if macd_val > signal_val else "bearish"
    if hist_val > 0 and macd_ind.macd_diff().iloc[-2] <= 0:
        signal = "bullish_crossover"
    elif hist_val < 0 and macd_ind.macd_diff().iloc[-2] >= 0:
        signal = "bearish_crossover"
    return {
        "macd": round(float(macd_val), 4),
        "signal_line": round(float(signal_val), 4),
        "histogram": round(float(hist_val), 4),
        "signal": signal,
    }


def compute_stochastic(df: pd.DataFrame) -> dict[str, Any]:
    """Compute Stochastic %K/%D."""
    stoch = ta.momentum.StochasticOscillator(df["High"], df["Low"], df["Close"])
    k = stoch.stoch().iloc[-1]
    d = stoch.stoch_signal().iloc[-1]
    if np.isnan(k):
        return {"stoch_k": None, "stoch_d": None, "signal": "insufficient_data"}
    if k > 80:
        signal = "overbought"
    elif k < 20:
        signal = "oversold"
    else:
        signal = "neutral"
    return {"stoch_k": round(float(k), 2), "stoch_d": round(float(d), 2), "signal": signal}


def compute_bollinger(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> dict[str, Any]:
    """Compute Bollinger Bands."""
    bb = ta.volatility.BollingerBands(df["Close"], window=period, window_dev=std)
    upper = bb.bollinger_hband().iloc[-1]
    middle = bb.bollinger_mavg().iloc[-1]
    lower = bb.bollinger_lband().iloc[-1]
    price = float(df["Close"].iloc[-1])
    if np.isnan(upper):
        return {"upper": None, "middle": None, "lower": None, "signal": "insufficient_data"}
    width = (upper - lower) / middle
    position = (price - lower) / (upper - lower) if upper != lower else 0.5
    return {
        "upper": round(float(upper), 2),
        "middle": round(float(middle), 2),
        "lower": round(float(lower), 2),
        "width": round(float(width), 4),
        "position": round(float(position), 4),
        "signal": "near_upper" if position > 0.8 else "near_lower" if position < 0.2 else "middle",
    }


def compute_atr(df: pd.DataFrame, period: int = 14) -> float | None:
    """Compute Average True Range."""
    atr = ta.volatility.AverageTrueRange(df["High"], df["Low"], df["Close"], window=period)
    val = atr.average_true_range().iloc[-1]
    return round(float(val), 4) if not np.isnan(val) else None


def compute_adx(df: pd.DataFrame, period: int = 14) -> dict[str, Any]:
    """Compute ADX with +DI/-DI."""
    adx_ind = ta.trend.ADXIndicator(df["High"], df["Low"], df["Close"], window=period)
    adx_val = adx_ind.adx().iloc[-1]
    plus_di = adx_ind.adx_pos().iloc[-1]
    minus_di = adx_ind.adx_neg().iloc[-1]
    if np.isnan(adx_val):
        return {"adx": None, "plus_di": None, "minus_di": None, "signal": "insufficient_data"}
    if adx_val > 25:
        signal = "strong_trend"
    elif adx_val > 20:
        signal = "moderate_trend"
    else:
        signal = "weak_trend"
    return {
        "adx": round(float(adx_val), 2),
        "plus_di": round(float(plus_di), 2),
        "minus_di": round(float(minus_di), 2),
        "trend_direction": "bullish" if plus_di > minus_di else "bearish",
        "signal": signal,
    }


def compute_obv(df: pd.DataFrame) -> dict[str, Any]:
    """Compute On-Balance Volume."""
    obv = ta.volume.OnBalanceVolumeIndicator(df["Close"], df["Volume"]).on_balance_volume()
    current = float(obv.iloc[-1])
    prev_20 = float(obv.iloc[-20]) if len(obv) >= 20 else float(obv.iloc[0])
    trend = "rising" if current > prev_20 else "falling"
    return {"obv": current, "obv_trend": trend}


def compute_vwap(df: pd.DataFrame) -> float | None:
    """Compute VWAP (Volume Weighted Average Price)."""
    try:
        typical = (df["High"] + df["Low"] + df["Close"]) / 3
        vwap = (typical * df["Volume"]).cumsum() / df["Volume"].cumsum()
        return round(float(vwap.iloc[-1]), 2)
    except Exception:
        return None


def compute_cmf(df: pd.DataFrame, period: int = 20) -> float | None:
    """Compute Chaikin Money Flow."""
    cmf = ta.volume.ChaikinMoneyFlowIndicator(
        df["High"], df["Low"], df["Close"], df["Volume"], window=period
    )
    val = cmf.chaikin_money_flow().iloc[-1]
    return round(float(val), 4) if not np.isnan(val) else None


def compute_mfi(df: pd.DataFrame, period: int = 14) -> dict[str, Any]:
    """Compute Money Flow Index."""
    mfi = ta.volume.MFIIndicator(df["High"], df["Low"], df["Close"], df["Volume"], window=period)
    val = mfi.money_flow_index().iloc[-1]
    if np.isnan(val):
        return {"mfi": None, "signal": "insufficient_data"}
    if val > 80:
        signal = "overbought"
    elif val < 20:
        signal = "oversold"
    else:
        signal = "neutral"
    return {"mfi": round(float(val), 2), "signal": signal}


def compute_fibonacci_levels(high: float, low: float) -> dict[str, float]:
    """Compute Fibonacci retracement levels."""
    diff = high - low
    return {
        "level_0": round(high, 2),
        "level_236": round(high - diff * 0.236, 2),
        "level_382": round(high - diff * 0.382, 2),
        "level_500": round(high - diff * 0.5, 2),
        "level_618": round(high - diff * 0.618, 2),
        "level_786": round(high - diff * 0.786, 2),
        "level_1": round(low, 2),
    }


def compute_pivot_points(df: pd.DataFrame) -> dict[str, float]:
    """Compute standard pivot points with support/resistance."""
    h = float(df["High"].iloc[-1])
    low = float(df["Low"].iloc[-1])
    c = float(df["Close"].iloc[-1])
    pivot = (h + low + c) / 3
    return {
        "pivot": round(pivot, 2),
        "r1": round(2 * pivot - low, 2),
        "r2": round(pivot + (h - low), 2),
        "s1": round(2 * pivot - h, 2),
        "s2": round(pivot - (h - low), 2),
    }
