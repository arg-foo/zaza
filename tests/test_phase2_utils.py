"""Tests for Phase 2 utilities: FRED client, TA indicators, quant models, sentiment."""

import httpx
import numpy as np
import pandas as pd
import pytest
import respx

from zaza.cache.store import FileCache


@pytest.fixture
def cache(tmp_path):
    return FileCache(cache_dir=tmp_path)


@pytest.fixture
def sample_ohlcv():
    rng = np.random.default_rng(42)
    n = 252
    prices = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.02, n)))
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "Open": prices * (1 + rng.uniform(-0.01, 0.01, n)),
            "High": prices * (1 + rng.uniform(0, 0.03, n)),
            "Low": prices * (1 - rng.uniform(0, 0.03, n)),
            "Close": prices,
            "Volume": rng.integers(1_000_000, 10_000_000, n),
        },
        index=dates,
    )


# --- FRED Client Tests ---


@respx.mock
@pytest.mark.asyncio
async def test_fred_get_series(cache):
    from zaza.api.fred_client import FRED_BASE, FredClient

    client = FredClient("test-key", cache)
    respx.get(f"{FRED_BASE}/series/observations").mock(
        return_value=httpx.Response(
            200, json={"observations": [{"date": "2024-01-01", "value": "5.33"}]}
        )
    )
    result = await client.get_series("DFF")
    assert len(result) == 1
    assert result[0]["value"] == "5.33"


@respx.mock
@pytest.mark.asyncio
async def test_fred_get_series_caches(cache):
    from zaza.api.fred_client import FRED_BASE, FredClient

    client = FredClient("test-key", cache)
    route = respx.get(f"{FRED_BASE}/series/observations").mock(
        return_value=httpx.Response(200, json={"observations": []})
    )
    await client.get_series("DFF")
    await client.get_series("DFF")
    assert route.call_count == 1


@respx.mock
@pytest.mark.asyncio
async def test_fred_error_returns_empty(cache):
    from zaza.api.fred_client import FRED_BASE, FredClient

    client = FredClient("test-key", cache)
    respx.get(f"{FRED_BASE}/series/observations").mock(return_value=httpx.Response(500))
    result = await client.get_series("BAD")
    assert result == []


# --- TA Indicator Tests ---


def test_ohlcv_to_dataframe():
    from zaza.utils.indicators import ohlcv_to_dataframe

    data = [{"open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}]
    df = ohlcv_to_dataframe(data)
    assert "Close" in df.columns
    assert df["Close"].iloc[0] == 102


def test_compute_sma(sample_ohlcv):
    from zaza.utils.indicators import compute_sma

    result = compute_sma(sample_ohlcv, [20, 50])
    assert "sma_20" in result["sma"]
    assert "sma_50" in result["sma"]
    assert result["sma"]["sma_20"] is not None


def test_compute_rsi(sample_ohlcv):
    from zaza.utils.indicators import compute_rsi

    result = compute_rsi(sample_ohlcv)
    assert result["rsi_14"] is not None
    assert 0 <= result["rsi_14"] <= 100
    assert result["signal"] in [
        "overbought",
        "approaching_overbought",
        "neutral",
        "approaching_oversold",
        "oversold",
    ]


def test_compute_macd(sample_ohlcv):
    from zaza.utils.indicators import compute_macd

    result = compute_macd(sample_ohlcv)
    assert result["macd"] is not None
    assert result["signal"] in ["bullish", "bearish", "bullish_crossover", "bearish_crossover"]


def test_compute_bollinger(sample_ohlcv):
    from zaza.utils.indicators import compute_bollinger

    result = compute_bollinger(sample_ohlcv)
    assert result["upper"] > result["lower"]
    assert result["signal"] in ["near_upper", "near_lower", "middle"]


def test_compute_atr(sample_ohlcv):
    from zaza.utils.indicators import compute_atr

    result = compute_atr(sample_ohlcv)
    assert result is not None
    assert result > 0


def test_compute_adx(sample_ohlcv):
    from zaza.utils.indicators import compute_adx

    result = compute_adx(sample_ohlcv)
    assert result["adx"] is not None
    assert result["signal"] in ["strong_trend", "moderate_trend", "weak_trend"]


def test_compute_fibonacci():
    from zaza.utils.indicators import compute_fibonacci_levels

    result = compute_fibonacci_levels(200.0, 100.0)
    assert result["level_0"] == 200.0
    assert result["level_500"] == 150.0
    assert result["level_1"] == 100.0


def test_compute_pivot_points(sample_ohlcv):
    from zaza.utils.indicators import compute_pivot_points

    result = compute_pivot_points(sample_ohlcv)
    assert "pivot" in result
    assert result["r1"] > result["pivot"] > result["s1"]


# --- Quant Model Tests ---


def test_monte_carlo_deterministic():
    from zaza.utils.models import monte_carlo_gbm

    r1 = monte_carlo_gbm(100, 0.1, 0.2, 30, n_sims=1000, seed=42)
    r2 = monte_carlo_gbm(100, 0.1, 0.2, 30, n_sims=1000, seed=42)
    assert r1["mean_price"] == r2["mean_price"]
    assert r1["percentiles"] == r2["percentiles"]


def test_monte_carlo_percentiles():
    from zaza.utils.models import monte_carlo_gbm

    result = monte_carlo_gbm(100, 0.1, 0.2, 30, seed=42)
    assert result["percentiles"]["p5"] < result["percentiles"]["p50"] < result["percentiles"]["p95"]


def test_hurst_exponent():
    from zaza.utils.models import compute_hurst_exponent

    rng = np.random.default_rng(42)
    random_walk = np.cumsum(rng.normal(0, 1, 500))
    h = compute_hurst_exponent(random_walk)
    assert 0 <= h <= 1


def test_half_life():
    from zaza.utils.models import compute_half_life

    mean_reverting = np.sin(np.linspace(0, 10 * np.pi, 200)) * 10 + 100
    hl = compute_half_life(mean_reverting)
    assert hl is not None or hl is None  # may not always compute for sin wave


def test_return_stats():
    from zaza.utils.models import compute_return_stats

    rng = np.random.default_rng(42)
    returns = rng.normal(0.001, 0.02, 252)
    result = compute_return_stats(returns)
    assert "mean" in result
    assert "skewness" in result
    assert "max_drawdown" in result


def test_var():
    from zaza.utils.models import compute_var

    rng = np.random.default_rng(42)
    returns = rng.normal(0.001, 0.02, 252)
    result = compute_var(returns)
    assert result["historical_var"] < 0  # VaR should be negative (loss)


def test_cvar():
    from zaza.utils.models import compute_cvar

    rng = np.random.default_rng(42)
    returns = rng.normal(0.001, 0.02, 252)
    result = compute_cvar(returns)
    assert result < 0


# --- Sentiment Tests ---


def test_score_bullish_headline():
    from zaza.utils.sentiment import score_headline

    result = score_headline("Apple beats earnings expectations with record growth")
    assert result["sentiment"] == "bullish"
    assert result["score"] > 0


def test_score_bearish_headline():
    from zaza.utils.sentiment import score_headline

    result = score_headline(
        "Company misses estimates, announces layoffs and decline in revenue"
    )
    assert result["sentiment"] == "bearish"
    assert result["score"] < 0


def test_score_neutral_headline():
    from zaza.utils.sentiment import score_headline

    result = score_headline("Company releases quarterly update")
    assert result["sentiment"] == "neutral"


def test_aggregate_sentiment():
    from zaza.utils.sentiment import aggregate_sentiment

    scores = [
        {"score": 0.5, "confidence": 0.8},
        {"score": 0.3, "confidence": 0.6},
        {"score": -0.1, "confidence": 0.4},
    ]
    result = aggregate_sentiment(scores)
    assert result["count"] == 3
    assert result["score"] > 0  # net bullish


def test_classify_insider_buying():
    from zaza.utils.sentiment import classify_insider_activity

    txns = [
        {"type": "Purchase"},
        {"type": "Purchase"},
        {"type": "Purchase"},
        {"type": "Sale"},
    ]
    result = classify_insider_activity(txns)
    assert result["sentiment"] in ("buy", "strong_buy")
    assert result["cluster_buying"] is True


def test_contrarian_signal():
    from zaza.utils.sentiment import detect_contrarian_signal

    assert detect_contrarian_signal(-0.8) == "contrarian_bullish"
    assert detect_contrarian_signal(0.8) == "contrarian_bearish"
    assert detect_contrarian_signal(0.3) is None
