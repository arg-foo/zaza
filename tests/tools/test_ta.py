"""Tests for Technical Analysis MCP tools (TASK-015)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from zaza.cache.store import FileCache


@pytest.fixture
def cache(tmp_path):
    return FileCache(cache_dir=tmp_path)


def _make_ohlcv_records(n: int = 252, seed: int = 42) -> list[dict]:
    """Generate realistic OHLCV records for testing TA tools."""
    rng = np.random.default_rng(seed)
    prices = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.02, n)))
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    records = []
    for i in range(n):
        records.append({
            "Date": str(dates[i].date()),
            "Open": round(float(prices[i] * (1 + rng.uniform(-0.01, 0.01))), 2),
            "High": round(float(prices[i] * (1 + rng.uniform(0.005, 0.03))), 2),
            "Low": round(float(prices[i] * (1 - rng.uniform(0.005, 0.03))), 2),
            "Close": round(float(prices[i]), 2),
            "Volume": int(rng.integers(1_000_000, 10_000_000)),
        })
    return records


def _make_short_ohlcv_records(n: int = 10) -> list[dict]:
    """Generate short OHLCV records to test insufficient data handling."""
    return _make_ohlcv_records(n=n, seed=99)


def _capture_tools_with_mock_yf(register_module_path: str, mock_yf):
    """Register TA tools with a mocked YFinanceClient, returning tool functions."""
    mcp = MagicMock()
    tool_funcs = {}

    def capture_tool():
        def decorator(func):
            tool_funcs[func.__name__] = func
            return func
        return decorator

    mcp.tool = capture_tool

    with patch(f"{register_module_path}.YFinanceClient", return_value=mock_yf):
        with patch(f"{register_module_path}.FileCache"):
            # Force re-import to pick up the mocked dependencies
            import importlib
            mod = importlib.import_module(register_module_path)
            mod.register(mcp)

    return tool_funcs


# ---------------------------------------------------------------------------
# get_moving_averages tests
# ---------------------------------------------------------------------------

MA_MOD = "zaza.tools.ta.moving_averages"


@pytest.mark.asyncio
async def test_moving_averages_returns_sma_ema():
    """get_moving_averages returns SMA(20,50,200) and EMA(12,26) values."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=252)

    tools = _capture_tools_with_mock_yf(MA_MOD, mock_yf)
    result_str = await tools["get_moving_averages"]("AAPL")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    assert "sma" in result["data"]
    assert "ema" in result["data"]
    assert result["data"]["sma"]["sma_20"] is not None
    assert result["data"]["sma"]["sma_50"] is not None
    assert result["data"]["sma"]["sma_200"] is not None
    assert result["data"]["ema"]["ema_12"] is not None
    assert result["data"]["ema"]["ema_26"] is not None


@pytest.mark.asyncio
async def test_moving_averages_golden_death_cross():
    """get_moving_averages includes cross signal information."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=252)

    tools = _capture_tools_with_mock_yf(MA_MOD, mock_yf)
    result_str = await tools["get_moving_averages"]("AAPL")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    # Cross signal should be present when enough data
    if "cross" in result["data"]:
        assert result["data"]["cross"] in [
            "golden_cross", "death_cross", "above", "below"
        ]


@pytest.mark.asyncio
async def test_moving_averages_insufficient_data():
    """get_moving_averages handles insufficient data for SMA-200 gracefully."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_short_ohlcv_records(n=10)

    tools = _capture_tools_with_mock_yf(MA_MOD, mock_yf)
    result_str = await tools["get_moving_averages"]("AAPL")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    # SMA-200 should be None due to insufficient data
    assert result["data"]["sma"]["sma_200"] is None


@pytest.mark.asyncio
async def test_moving_averages_empty_history():
    """get_moving_averages returns error when no history is available."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = []

    tools = _capture_tools_with_mock_yf(MA_MOD, mock_yf)
    result_str = await tools["get_moving_averages"]("INVALID")
    result = json.loads(result_str)

    assert "error" in result


# ---------------------------------------------------------------------------
# get_momentum_indicators tests
# ---------------------------------------------------------------------------

MOM_MOD = "zaza.tools.ta.momentum"


@pytest.mark.asyncio
async def test_momentum_returns_rsi_macd_stochastic():
    """get_momentum_indicators returns RSI, MACD, and Stochastic values."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=252)

    tools = _capture_tools_with_mock_yf(MOM_MOD, mock_yf)
    result_str = await tools["get_momentum_indicators"]("AAPL")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    assert "rsi" in result["data"]
    assert "macd" in result["data"]
    assert "stochastic" in result["data"]
    assert result["data"]["rsi"]["rsi_14"] is not None
    assert result["data"]["macd"]["macd"] is not None


@pytest.mark.asyncio
async def test_momentum_signal_classifications():
    """get_momentum_indicators includes signal classifications for all indicators."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=252)

    tools = _capture_tools_with_mock_yf(MOM_MOD, mock_yf)
    result_str = await tools["get_momentum_indicators"]("AAPL")
    result = json.loads(result_str)

    assert "signal" in result["data"]["rsi"]
    assert "signal" in result["data"]["macd"]
    assert "signal" in result["data"]["stochastic"]


@pytest.mark.asyncio
async def test_momentum_empty_history():
    """get_momentum_indicators returns error when no history available."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = []

    tools = _capture_tools_with_mock_yf(MOM_MOD, mock_yf)
    result_str = await tools["get_momentum_indicators"]("INVALID")
    result = json.loads(result_str)

    assert "error" in result


# ---------------------------------------------------------------------------
# get_volatility_indicators tests
# ---------------------------------------------------------------------------

VOL_MOD = "zaza.tools.ta.volatility"


@pytest.mark.asyncio
async def test_volatility_returns_bollinger_atr():
    """get_volatility_indicators returns Bollinger Bands and ATR."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=252)

    tools = _capture_tools_with_mock_yf(VOL_MOD, mock_yf)
    result_str = await tools["get_volatility_indicators"]("AAPL")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    assert "bollinger" in result["data"]
    assert "atr" in result["data"]
    assert result["data"]["bollinger"]["upper"] > result["data"]["bollinger"]["lower"]


@pytest.mark.asyncio
async def test_volatility_atr_positive():
    """get_volatility_indicators returns positive ATR value."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=252)

    tools = _capture_tools_with_mock_yf(VOL_MOD, mock_yf)
    result_str = await tools["get_volatility_indicators"]("AAPL")
    result = json.loads(result_str)

    assert result["data"]["atr"]["atr_14"] > 0


@pytest.mark.asyncio
async def test_volatility_empty_history():
    """get_volatility_indicators returns error when no history available."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = []

    tools = _capture_tools_with_mock_yf(VOL_MOD, mock_yf)
    result_str = await tools["get_volatility_indicators"]("INVALID")
    result = json.loads(result_str)

    assert "error" in result


# ---------------------------------------------------------------------------
# get_volume_analysis tests
# ---------------------------------------------------------------------------

VLMA_MOD = "zaza.tools.ta.volume"


@pytest.mark.asyncio
async def test_volume_returns_obv_vwap():
    """get_volume_analysis returns OBV, VWAP, and volume trend."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=252)

    tools = _capture_tools_with_mock_yf(VLMA_MOD, mock_yf)
    result_str = await tools["get_volume_analysis"]("AAPL")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    assert "obv" in result["data"]
    assert "vwap" in result["data"]
    assert "volume_trend" in result["data"]


@pytest.mark.asyncio
async def test_volume_trend_direction():
    """get_volume_analysis volume_trend has valid direction."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=252)

    tools = _capture_tools_with_mock_yf(VLMA_MOD, mock_yf)
    result_str = await tools["get_volume_analysis"]("AAPL")
    result = json.loads(result_str)

    assert result["data"]["volume_trend"]["direction"] in ["increasing", "decreasing", "stable"]


@pytest.mark.asyncio
async def test_volume_empty_history():
    """get_volume_analysis returns error when no history available."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = []

    tools = _capture_tools_with_mock_yf(VLMA_MOD, mock_yf)
    result_str = await tools["get_volume_analysis"]("INVALID")
    result = json.loads(result_str)

    assert "error" in result


# ---------------------------------------------------------------------------
# get_support_resistance tests
# ---------------------------------------------------------------------------

SR_MOD = "zaza.tools.ta.support_resistance"


@pytest.mark.asyncio
async def test_support_resistance_returns_pivots_fib():
    """get_support_resistance returns pivot points, Fibonacci, and 52w high/low."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=252)

    tools = _capture_tools_with_mock_yf(SR_MOD, mock_yf)
    result_str = await tools["get_support_resistance"]("AAPL")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    assert "pivot_points" in result["data"]
    assert "fibonacci" in result["data"]
    assert "high_low_52w" in result["data"]
    assert result["data"]["pivot_points"]["r1"] > result["data"]["pivot_points"]["s1"]


@pytest.mark.asyncio
async def test_support_resistance_fibonacci_levels():
    """get_support_resistance Fibonacci levels are properly ordered."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=252)

    tools = _capture_tools_with_mock_yf(SR_MOD, mock_yf)
    result_str = await tools["get_support_resistance"]("AAPL")
    result = json.loads(result_str)

    fib = result["data"]["fibonacci"]
    assert fib["level_0"] >= fib["level_236"] >= fib["level_500"] >= fib["level_1"]


@pytest.mark.asyncio
async def test_support_resistance_empty_history():
    """get_support_resistance returns error when no history available."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = []

    tools = _capture_tools_with_mock_yf(SR_MOD, mock_yf)
    result_str = await tools["get_support_resistance"]("INVALID")
    result = json.loads(result_str)

    assert "error" in result


# ---------------------------------------------------------------------------
# get_trend_strength tests
# ---------------------------------------------------------------------------

TS_MOD = "zaza.tools.ta.trend_strength"


@pytest.mark.asyncio
async def test_trend_strength_returns_adx():
    """get_trend_strength returns ADX, +DI, -DI, and trend classification."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=252)

    tools = _capture_tools_with_mock_yf(TS_MOD, mock_yf)
    result_str = await tools["get_trend_strength"]("AAPL")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    assert "adx" in result["data"]
    assert result["data"]["adx"]["adx"] is not None
    assert result["data"]["adx"]["plus_di"] is not None
    assert result["data"]["adx"]["minus_di"] is not None


@pytest.mark.asyncio
async def test_trend_strength_trend_classification():
    """get_trend_strength includes trend direction and strength classification."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=252)

    tools = _capture_tools_with_mock_yf(TS_MOD, mock_yf)
    result_str = await tools["get_trend_strength"]("AAPL")
    result = json.loads(result_str)

    assert result["data"]["adx"]["trend_direction"] in ["bullish", "bearish"]
    assert result["data"]["adx"]["signal"] in [
        "strong_trend", "moderate_trend", "weak_trend"
    ]


@pytest.mark.asyncio
async def test_trend_strength_empty_history():
    """get_trend_strength returns error when no history available."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = []

    tools = _capture_tools_with_mock_yf(TS_MOD, mock_yf)
    result_str = await tools["get_trend_strength"]("INVALID")
    result = json.loads(result_str)

    assert "error" in result


# ---------------------------------------------------------------------------
# get_price_patterns tests
# ---------------------------------------------------------------------------

PAT_MOD = "zaza.tools.ta.patterns"


@pytest.mark.asyncio
async def test_patterns_returns_detected_patterns():
    """get_price_patterns returns list of detected candlestick patterns."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=90)

    tools = _capture_tools_with_mock_yf(PAT_MOD, mock_yf)
    result_str = await tools["get_price_patterns"]("AAPL")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    assert "patterns" in result["data"]
    assert isinstance(result["data"]["patterns"], list)


@pytest.mark.asyncio
async def test_patterns_empty_history():
    """get_price_patterns returns error when no history available."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = []

    tools = _capture_tools_with_mock_yf(PAT_MOD, mock_yf)
    result_str = await tools["get_price_patterns"]("INVALID")
    result = json.loads(result_str)

    assert "error" in result


# ---------------------------------------------------------------------------
# get_money_flow tests
# ---------------------------------------------------------------------------

MF_MOD = "zaza.tools.ta.money_flow"


@pytest.mark.asyncio
async def test_money_flow_returns_cmf_mfi():
    """get_money_flow returns CMF, MFI, and Williams %R."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=252)

    tools = _capture_tools_with_mock_yf(MF_MOD, mock_yf)
    result_str = await tools["get_money_flow"]("AAPL")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    assert "cmf" in result["data"]
    assert "mfi" in result["data"]
    assert "williams_r" in result["data"]


@pytest.mark.asyncio
async def test_money_flow_mfi_range():
    """get_money_flow MFI should be between 0 and 100."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = _make_ohlcv_records(n=252)

    tools = _capture_tools_with_mock_yf(MF_MOD, mock_yf)
    result_str = await tools["get_money_flow"]("AAPL")
    result = json.loads(result_str)

    mfi_val = result["data"]["mfi"]["mfi"]
    assert 0 <= mfi_val <= 100


@pytest.mark.asyncio
async def test_money_flow_empty_history():
    """get_money_flow returns error when no history available."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = []

    tools = _capture_tools_with_mock_yf(MF_MOD, mock_yf)
    result_str = await tools["get_money_flow"]("INVALID")
    result = json.loads(result_str)

    assert "error" in result


# ---------------------------------------------------------------------------
# get_relative_performance tests
# ---------------------------------------------------------------------------

REL_MOD = "zaza.tools.ta.relative"


@pytest.mark.asyncio
async def test_relative_performance_vs_spy():
    """get_relative_performance returns comparison vs S&P 500."""
    mock_yf = MagicMock()
    records = _make_ohlcv_records(n=252, seed=42)
    spy_records = _make_ohlcv_records(n=252, seed=123)
    # First call is for the ticker, second for SPY, third for sector ETF
    mock_yf.get_history.side_effect = [records, spy_records, spy_records]
    mock_yf.get_quote.return_value = {"sector": "Technology"}

    tools = _capture_tools_with_mock_yf(REL_MOD, mock_yf)
    result_str = await tools["get_relative_performance"]("AAPL")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    assert "vs_spy" in result["data"]
    assert "ticker_return" in result["data"]["vs_spy"]
    assert "spy_return" in result["data"]["vs_spy"]


@pytest.mark.asyncio
async def test_relative_performance_correlation():
    """get_relative_performance includes correlation and beta."""
    mock_yf = MagicMock()
    records = _make_ohlcv_records(n=252, seed=42)
    spy_records = _make_ohlcv_records(n=252, seed=123)
    mock_yf.get_history.side_effect = [records, spy_records, spy_records]
    mock_yf.get_quote.return_value = {"sector": "Technology"}

    tools = _capture_tools_with_mock_yf(REL_MOD, mock_yf)
    result_str = await tools["get_relative_performance"]("AAPL")
    result = json.loads(result_str)

    assert "correlation" in result["data"]["vs_spy"]
    assert "beta" in result["data"]["vs_spy"]
    # Correlation should be between -1 and 1
    corr = result["data"]["vs_spy"]["correlation"]
    assert -1 <= corr <= 1


@pytest.mark.asyncio
async def test_relative_performance_empty_history():
    """get_relative_performance returns error when no history available."""
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = []

    tools = _capture_tools_with_mock_yf(REL_MOD, mock_yf)
    result_str = await tools["get_relative_performance"]("INVALID")
    result = json.loads(result_str)

    assert "error" in result
