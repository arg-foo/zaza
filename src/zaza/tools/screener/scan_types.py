"""Scan type definitions with EquityQuery builders and TA scoring functions.

Each scan type defines:
  - build_query(exchange_code) -> EquityQuery: pre-filter for yf.screen()
  - score_candidate(df, quote) -> {score: 0-100, signals: [str]}: TA scoring
  - sort_field / sort_asc: server-side sort params for yf.screen()
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd
import structlog
from yfinance import EquityQuery

from zaza.utils.indicators import (
    compute_adx,
    compute_atr,
    compute_bollinger,
    compute_cmf,
    compute_macd,
    compute_obv,
    compute_rsi,
    compute_sma,
    compute_stochastic,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ScanTypeConfig:
    """Configuration for a single scan type."""

    name: str
    description: str
    build_query: Callable[[str], EquityQuery]
    score_candidate: Callable[[pd.DataFrame, dict[str, Any]], dict[str, Any]]
    sort_field: str
    sort_asc: bool


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------

def _build_breakout_query(exchange_code: str) -> EquityQuery:
    """Breakout: 52wk % change > 80, avg vol > 500k."""
    return EquityQuery("and", [
        EquityQuery("eq", ["exchange", exchange_code]),
        EquityQuery("gt", ["fiftytwowkpercentchange", 80]),
        EquityQuery("gt", ["avgdailyvol3m", 500_000]),
    ])


def _build_momentum_query(exchange_code: str) -> EquityQuery:
    """Momentum: % change > 0, avg vol > 500k."""
    return EquityQuery("and", [
        EquityQuery("eq", ["exchange", exchange_code]),
        EquityQuery("gt", ["percentchange", 0]),
        EquityQuery("gt", ["avgdailyvol3m", 500_000]),
    ])


def _build_consolidation_query(exchange_code: str) -> EquityQuery:
    """Consolidation: % change between -1 and 1, avg vol > 200k."""
    return EquityQuery("and", [
        EquityQuery("eq", ["exchange", exchange_code]),
        EquityQuery("btwn", ["percentchange", -1, 1]),
        EquityQuery("gt", ["avgdailyvol3m", 200_000]),
    ])


def _build_volume_query(exchange_code: str) -> EquityQuery:
    """Volume: avg vol > 1M."""
    return EquityQuery("and", [
        EquityQuery("eq", ["exchange", exchange_code]),
        EquityQuery("gt", ["avgdailyvol3m", 1_000_000]),
    ])


def _build_reversal_query(exchange_code: str) -> EquityQuery:
    """Reversal: % change < -2, avg vol > 500k."""
    return EquityQuery("and", [
        EquityQuery("eq", ["exchange", exchange_code]),
        EquityQuery("lt", ["percentchange", -2]),
        EquityQuery("gt", ["avgdailyvol3m", 500_000]),
    ])


def _build_ipo_query(exchange_code: str) -> EquityQuery:
    """IPO: market cap < $5B, avg vol > 300k."""
    return EquityQuery("and", [
        EquityQuery("eq", ["exchange", exchange_code]),
        EquityQuery("lt", ["intradaymarketcap", 5_000_000_000]),
        EquityQuery("gt", ["avgdailyvol3m", 300_000]),
    ])


def _build_short_squeeze_query(exchange_code: str) -> EquityQuery:
    """Short squeeze: short % > 10, avg vol > 500k."""
    return EquityQuery("and", [
        EquityQuery("eq", ["exchange", exchange_code]),
        EquityQuery("gt", ["short_percentage_of_shares_outstanding.value", 10]),
        EquityQuery("gt", ["avgdailyvol3m", 500_000]),
    ])


def _build_bullish_query(exchange_code: str) -> EquityQuery:
    """Bullish: % change > 1, avg vol > 500k."""
    return EquityQuery("and", [
        EquityQuery("eq", ["exchange", exchange_code]),
        EquityQuery("gt", ["percentchange", 1]),
        EquityQuery("gt", ["avgdailyvol3m", 500_000]),
    ])


def _build_bearish_query(exchange_code: str) -> EquityQuery:
    """Bearish: % change < -1, avg vol > 500k."""
    return EquityQuery("and", [
        EquityQuery("eq", ["exchange", exchange_code]),
        EquityQuery("lt", ["percentchange", -1]),
        EquityQuery("gt", ["avgdailyvol3m", 500_000]),
    ])


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def _clamp(score: float) -> int:
    """Clamp score to 0-100 integer range."""
    return int(min(100, max(0, round(score))))


def _safe_volume_ratio(df: pd.DataFrame) -> float:
    """Compute recent volume / average volume ratio, safe against zero."""
    recent = df["Volume"].iloc[-5:].mean()
    avg = df["Volume"].mean()
    if avg == 0 or np.isnan(avg):
        return 1.0
    return float(recent / avg)


def _score_breakout(df: pd.DataFrame, quote: dict[str, Any]) -> dict[str, Any]:
    """Score breakout candidates.

    Weights: bollinger 30 (squeeze + position), volume ratio 20,
    52w high proximity 25, overall momentum 25.
    """
    signals: list[str] = []
    score = 0.0

    # Bollinger (30 pts): squeeze = narrow width, position near upper
    bb = compute_bollinger(df)
    if bb.get("width") is not None:
        width = bb["width"]
        position = bb["position"]
        # Tight bands (squeeze) + price near upper = breakout
        if width < 0.05:
            score += 15
            signals.append("bollinger_squeeze")
        elif width < 0.10:
            score += 8
        if position > 0.8:
            score += 15
            signals.append("near_upper_band")
        elif position > 0.6:
            score += 8

    # Volume ratio (20 pts)
    vol_ratio = _safe_volume_ratio(df)
    if vol_ratio > 2.0:
        score += 20
        signals.append(f"volume_surge_{vol_ratio:.1f}x")
    elif vol_ratio > 1.5:
        score += 12
        signals.append(f"above_avg_volume_{vol_ratio:.1f}x")
    elif vol_ratio > 1.0:
        score += 5

    # 52-week high proximity (25 pts)
    high_52w = quote.get("fiftyTwoWeekHigh")
    price = float(df["Close"].iloc[-1])
    if high_52w and high_52w > 0:
        proximity = price / high_52w
        if proximity > 0.95:
            score += 25
            signals.append("near_52w_high")
        elif proximity > 0.85:
            score += 15
        elif proximity > 0.75:
            score += 8

    # Overall momentum (25 pts): MACD signal
    macd = compute_macd(df)
    if macd.get("signal") in ("bullish", "bullish_crossover"):
        score += 25
        signals.append(f"macd_{macd['signal']}")
    elif macd.get("histogram") is not None and macd["histogram"] > 0:
        score += 12

    return {"score": _clamp(score), "signals": signals}


def _score_momentum(df: pd.DataFrame, quote: dict[str, Any]) -> dict[str, Any]:
    """Score momentum candidates.

    Weights: RSI 25, MACD 30, SMA golden cross 30, ADX 15.
    """
    signals: list[str] = []
    score = 0.0

    # RSI (25 pts): ideal range 50-70
    rsi = compute_rsi(df)
    rsi_val = rsi.get("rsi_14")
    if rsi_val is not None:
        if 50 <= rsi_val <= 70:
            score += 25
            signals.append(f"rsi_bullish_{rsi_val}")
        elif 40 <= rsi_val < 50:
            score += 15
        elif rsi_val > 70:
            score += 10
            signals.append("rsi_overbought")
        else:
            score += 5

    # MACD (30 pts)
    macd = compute_macd(df)
    if macd.get("signal") == "bullish_crossover":
        score += 30
        signals.append("macd_bullish_crossover")
    elif macd.get("signal") == "bullish":
        score += 20
        signals.append("macd_bullish")
    elif macd.get("histogram") is not None and macd["histogram"] > 0:
        score += 10

    # SMA golden cross (30 pts)
    sma = compute_sma(df)
    cross = sma.get("cross")
    if cross == "golden_cross":
        score += 30
        signals.append("golden_cross")
    elif cross == "above":
        score += 20
        signals.append("sma50_above_sma200")
    elif sma.get("sma", {}).get("price_vs_sma_50") == "above":
        score += 10

    # ADX (15 pts)
    adx = compute_adx(df)
    if adx.get("signal") == "strong_trend" and adx.get("trend_direction") == "bullish":
        score += 15
        signals.append("strong_bullish_trend")
    elif adx.get("signal") == "moderate_trend":
        score += 8

    return {"score": _clamp(score), "signals": signals}


def _score_consolidation(df: pd.DataFrame, quote: dict[str, Any]) -> dict[str, Any]:
    """Score consolidation candidates.

    Weights: bollinger width 35, ATR 30, ADX weak 35.
    """
    signals: list[str] = []
    score = 0.0

    # Bollinger width (35 pts): narrower = better consolidation
    bb = compute_bollinger(df)
    if bb.get("width") is not None:
        width = bb["width"]
        if width < 0.03:
            score += 35
            signals.append("very_tight_bands")
        elif width < 0.06:
            score += 25
            signals.append("tight_bands")
        elif width < 0.10:
            score += 15
        elif width < 0.15:
            score += 5

    # ATR (30 pts): lower relative ATR = tighter consolidation
    atr = compute_atr(df)
    price = float(df["Close"].iloc[-1])
    if atr is not None and price > 0:
        atr_pct = atr / price
        if atr_pct < 0.01:
            score += 30
            signals.append("very_low_atr")
        elif atr_pct < 0.02:
            score += 20
            signals.append("low_atr")
        elif atr_pct < 0.03:
            score += 10

    # ADX weak trend (35 pts): lower ADX = weaker trend = consolidation
    adx = compute_adx(df)
    adx_val = adx.get("adx")
    if adx_val is not None:
        if adx_val < 15:
            score += 35
            signals.append("no_trend")
        elif adx_val < 20:
            score += 25
            signals.append("weak_trend")
        elif adx_val < 25:
            score += 10

    return {"score": _clamp(score), "signals": signals}


def _score_volume(df: pd.DataFrame, quote: dict[str, Any]) -> dict[str, Any]:
    """Score volume candidates.

    Weights: OBV trend 30, CMF 30, volume ratio 40.
    """
    signals: list[str] = []
    score = 0.0

    # OBV trend (30 pts)
    obv = compute_obv(df)
    if obv.get("obv_trend") == "rising":
        score += 30
        signals.append("obv_rising")
    else:
        score += 10

    # CMF (30 pts)
    cmf = compute_cmf(df)
    if cmf is not None:
        if cmf > 0.1:
            score += 30
            signals.append(f"strong_money_inflow_{cmf:.3f}")
        elif cmf > 0.05:
            score += 20
            signals.append("money_inflow")
        elif cmf > 0:
            score += 10
        else:
            signals.append("money_outflow")

    # Volume ratio (40 pts)
    vol_ratio = _safe_volume_ratio(df)
    if vol_ratio > 3.0:
        score += 40
        signals.append(f"extreme_volume_{vol_ratio:.1f}x")
    elif vol_ratio > 2.0:
        score += 30
        signals.append(f"high_volume_{vol_ratio:.1f}x")
    elif vol_ratio > 1.5:
        score += 20
        signals.append(f"above_avg_volume_{vol_ratio:.1f}x")
    elif vol_ratio > 1.0:
        score += 10

    return {"score": _clamp(score), "signals": signals}


def _score_reversal(df: pd.DataFrame, quote: dict[str, Any]) -> dict[str, Any]:
    """Score reversal candidates.

    Weights: RSI oversold 35, stochastic 25, bullish patterns 40.
    """
    signals: list[str] = []
    score = 0.0

    # RSI oversold (35 pts)
    rsi = compute_rsi(df)
    rsi_val = rsi.get("rsi_14")
    if rsi_val is not None:
        if rsi_val < 25:
            score += 35
            signals.append(f"deeply_oversold_rsi_{rsi_val}")
        elif rsi_val < 30:
            score += 28
            signals.append(f"oversold_rsi_{rsi_val}")
        elif rsi_val < 40:
            score += 15
            signals.append("approaching_oversold")

    # Stochastic (25 pts)
    stoch = compute_stochastic(df)
    stoch_k = stoch.get("stoch_k")
    if stoch_k is not None:
        if stoch_k < 20:
            score += 25
            signals.append(f"stoch_oversold_{stoch_k:.1f}")
        elif stoch_k < 30:
            score += 15

    # Bullish patterns: price bouncing from support, MACD crossover (40 pts)
    macd = compute_macd(df)
    if macd.get("signal") == "bullish_crossover":
        score += 25
        signals.append("macd_bullish_crossover")
    elif macd.get("signal") == "bullish":
        score += 15
        signals.append("macd_turning_bullish")

    # Check for hammer-like pattern: lower shadow > 2x body
    last = df.iloc[-1]
    body = abs(last["Close"] - last["Open"])
    lower_shadow = min(last["Open"], last["Close"]) - last["Low"]
    if body > 0 and lower_shadow > 2 * body:
        score += 15
        signals.append("hammer_pattern")

    return {"score": _clamp(score), "signals": signals}


def _score_ipo(df: pd.DataFrame, quote: dict[str, Any]) -> dict[str, Any]:
    """Score IPO candidates.

    Weights: history length 30, RSI 25, volume trend 25, MACD 20.
    """
    signals: list[str] = []
    score = 0.0

    # History length (30 pts): shorter = more recent IPO
    n = len(df)
    if n < 30:
        score += 30
        signals.append("very_recent_ipo")
    elif n < 60:
        score += 20
        signals.append("recent_ipo")
    elif n < 120:
        score += 10
        signals.append("semi_recent_ipo")
    else:
        score += 5

    # RSI (25 pts): momentum in IPO context
    rsi = compute_rsi(df)
    rsi_val = rsi.get("rsi_14")
    if rsi_val is not None:
        if 50 <= rsi_val <= 70:
            score += 25
            signals.append(f"bullish_rsi_{rsi_val}")
        elif 40 <= rsi_val < 50:
            score += 15
        elif rsi_val > 70:
            score += 10
            signals.append("overbought_caution")

    # Volume trend (25 pts): increasing volume = growing interest
    vol_ratio = _safe_volume_ratio(df)
    if vol_ratio > 1.5:
        score += 25
        signals.append(f"growing_volume_{vol_ratio:.1f}x")
    elif vol_ratio > 1.0:
        score += 15
    else:
        score += 5

    # MACD (20 pts)
    macd = compute_macd(df)
    if macd.get("signal") in ("bullish", "bullish_crossover"):
        score += 20
        signals.append(f"macd_{macd['signal']}")
    elif macd.get("histogram") is not None and macd["histogram"] > 0:
        score += 10

    return {"score": _clamp(score), "signals": signals}


def _score_short_squeeze(df: pd.DataFrame, quote: dict[str, Any]) -> dict[str, Any]:
    """Score short squeeze candidates.

    Weights: short % from quote 35, RSI 25, volume surge 25, MACD 15.
    """
    signals: list[str] = []
    score = 0.0

    # Short % (35 pts)
    short_info = quote.get("short_percentage_of_shares_outstanding")
    short_pct: float | None = None
    if isinstance(short_info, dict):
        short_pct = short_info.get("value")
    elif isinstance(short_info, (int, float)):
        short_pct = float(short_info)

    if short_pct is not None:
        if short_pct > 30:
            score += 35
            signals.append(f"very_high_short_{short_pct:.1f}%")
        elif short_pct > 20:
            score += 25
            signals.append(f"high_short_{short_pct:.1f}%")
        elif short_pct > 10:
            score += 15
            signals.append(f"elevated_short_{short_pct:.1f}%")

    # RSI (25 pts): rising from oversold = squeeze trigger
    rsi = compute_rsi(df)
    rsi_val = rsi.get("rsi_14")
    if rsi_val is not None:
        if 40 <= rsi_val <= 60:
            score += 25
            signals.append("rsi_neutral_rising")
        elif rsi_val > 60:
            score += 15
            signals.append("rsi_bullish_momentum")
        elif rsi_val < 40:
            score += 10

    # Volume surge (25 pts)
    vol_ratio = _safe_volume_ratio(df)
    if vol_ratio > 2.5:
        score += 25
        signals.append(f"volume_surge_{vol_ratio:.1f}x")
    elif vol_ratio > 1.5:
        score += 15
        signals.append(f"volume_increase_{vol_ratio:.1f}x")
    elif vol_ratio > 1.0:
        score += 5

    # MACD (15 pts)
    macd = compute_macd(df)
    if macd.get("signal") in ("bullish", "bullish_crossover"):
        score += 15
        signals.append(f"macd_{macd['signal']}")
    elif macd.get("histogram") is not None and macd["histogram"] > 0:
        score += 8

    return {"score": _clamp(score), "signals": signals}


def _score_bullish(df: pd.DataFrame, quote: dict[str, Any]) -> dict[str, Any]:
    """Score bullish candidates.

    Weights: RSI 20, MACD 25, ADX 20, OBV 15, CMF 10, patterns 10.
    """
    signals: list[str] = []
    score = 0.0

    # RSI (20 pts)
    rsi = compute_rsi(df)
    rsi_val = rsi.get("rsi_14")
    if rsi_val is not None:
        if 50 <= rsi_val <= 70:
            score += 20
            signals.append(f"bullish_rsi_{rsi_val}")
        elif 40 <= rsi_val < 50:
            score += 12
        elif rsi_val > 70:
            score += 8
            signals.append("overbought_caution")

    # MACD (25 pts)
    macd = compute_macd(df)
    if macd.get("signal") == "bullish_crossover":
        score += 25
        signals.append("macd_bullish_crossover")
    elif macd.get("signal") == "bullish":
        score += 18
        signals.append("macd_bullish")
    elif macd.get("histogram") is not None and macd["histogram"] > 0:
        score += 8

    # ADX (20 pts)
    adx = compute_adx(df)
    if adx.get("signal") == "strong_trend" and adx.get("trend_direction") == "bullish":
        score += 20
        signals.append("strong_bullish_trend")
    elif adx.get("signal") == "moderate_trend" and adx.get("trend_direction") == "bullish":
        score += 12

    # OBV (15 pts)
    obv = compute_obv(df)
    if obv.get("obv_trend") == "rising":
        score += 15
        signals.append("obv_rising")
    else:
        score += 5

    # CMF (10 pts)
    cmf = compute_cmf(df)
    if cmf is not None and cmf > 0:
        score += 10
        signals.append("positive_money_flow")
    elif cmf is not None and cmf > -0.05:
        score += 5

    # Bullish pattern: price > SMA20 and SMA50 (10 pts)
    sma = compute_sma(df, periods=[20, 50])
    price = float(df["Close"].iloc[-1])
    sma_20 = sma.get("sma", {}).get("sma_20")
    sma_50 = sma.get("sma", {}).get("sma_50")
    if sma_20 is not None and sma_50 is not None:
        if price > sma_20 > sma_50:
            score += 10
            signals.append("price_above_sma20_sma50")
        elif price > sma_20:
            score += 5

    return {"score": _clamp(score), "signals": signals}


def _score_bearish(df: pd.DataFrame, quote: dict[str, Any]) -> dict[str, Any]:
    """Score bearish candidates.

    Weights: RSI overbought 25, MACD 25, ADX 20, OBV 15, CMF 15.
    """
    signals: list[str] = []
    score = 0.0

    # RSI overbought (25 pts)
    rsi = compute_rsi(df)
    rsi_val = rsi.get("rsi_14")
    if rsi_val is not None:
        if rsi_val > 75:
            score += 25
            signals.append(f"very_overbought_{rsi_val}")
        elif rsi_val > 70:
            score += 20
            signals.append(f"overbought_{rsi_val}")
        elif rsi_val > 60:
            score += 10
            signals.append("approaching_overbought")

    # MACD (25 pts)
    macd = compute_macd(df)
    if macd.get("signal") == "bearish_crossover":
        score += 25
        signals.append("macd_bearish_crossover")
    elif macd.get("signal") == "bearish":
        score += 18
        signals.append("macd_bearish")
    elif macd.get("histogram") is not None and macd["histogram"] < 0:
        score += 8

    # ADX (20 pts)
    adx = compute_adx(df)
    if adx.get("signal") == "strong_trend" and adx.get("trend_direction") == "bearish":
        score += 20
        signals.append("strong_bearish_trend")
    elif adx.get("signal") == "moderate_trend" and adx.get("trend_direction") == "bearish":
        score += 12

    # OBV falling (15 pts)
    obv = compute_obv(df)
    if obv.get("obv_trend") == "falling":
        score += 15
        signals.append("obv_falling")
    else:
        score += 5

    # CMF negative (15 pts)
    cmf = compute_cmf(df)
    if cmf is not None and cmf < -0.1:
        score += 15
        signals.append(f"strong_money_outflow_{cmf:.3f}")
    elif cmf is not None and cmf < 0:
        score += 10
        signals.append("money_outflow")
    elif cmf is not None:
        score += 3

    return {"score": _clamp(score), "signals": signals}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SCAN_TYPES: dict[str, ScanTypeConfig] = {
    "breakout": ScanTypeConfig(
        name="breakout",
        description="Stocks breaking out of consolidation with volume confirmation",
        build_query=_build_breakout_query,
        score_candidate=_score_breakout,
        sort_field="fiftytwowkpercentchange",
        sort_asc=False,
    ),
    "momentum": ScanTypeConfig(
        name="momentum",
        description="Stocks with strong upward price momentum (RSI, MACD, SMA)",
        build_query=_build_momentum_query,
        score_candidate=_score_momentum,
        sort_field="percentchange",
        sort_asc=False,
    ),
    "consolidation": ScanTypeConfig(
        name="consolidation",
        description="Stocks in tight consolidation range, potential breakout candidates",
        build_query=_build_consolidation_query,
        score_candidate=_score_consolidation,
        sort_field="percentchange",
        sort_asc=True,
    ),
    "volume": ScanTypeConfig(
        name="volume",
        description="Stocks with unusual volume activity signaling institutional interest",
        build_query=_build_volume_query,
        score_candidate=_score_volume,
        sort_field="avgdailyvol3m",
        sort_asc=False,
    ),
    "reversal": ScanTypeConfig(
        name="reversal",
        description="Oversold stocks showing potential reversal signals",
        build_query=_build_reversal_query,
        score_candidate=_score_reversal,
        sort_field="percentchange",
        sort_asc=True,
    ),
    "ipo": ScanTypeConfig(
        name="ipo",
        description="Recent IPO stocks with growing momentum and volume",
        build_query=_build_ipo_query,
        score_candidate=_score_ipo,
        sort_field="intradaymarketcap",
        sort_asc=True,
    ),
    "short_squeeze": ScanTypeConfig(
        name="short_squeeze",
        description="Heavily shorted stocks with squeeze potential",
        build_query=_build_short_squeeze_query,
        score_candidate=_score_short_squeeze,
        sort_field="short_percentage_of_shares_outstanding.value",
        sort_asc=False,
    ),
    "bullish": ScanTypeConfig(
        name="bullish",
        description="Stocks with multi-indicator bullish alignment",
        build_query=_build_bullish_query,
        score_candidate=_score_bullish,
        sort_field="percentchange",
        sort_asc=False,
    ),
    "bearish": ScanTypeConfig(
        name="bearish",
        description="Stocks with multi-indicator bearish alignment",
        build_query=_build_bearish_query,
        score_candidate=_score_bearish,
        sort_field="percentchange",
        sort_asc=True,
    ),
}
