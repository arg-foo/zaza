"""Tests for quantitative tools (TASK-019).

Covers: forecast, volatility, monte carlo, distribution, mean reversion, regime.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from zaza.cache.store import FileCache
from zaza.tools.quantitative.distribution import register as register_distribution
from zaza.tools.quantitative.forecast import register as register_forecast
from zaza.tools.quantitative.mean_reversion import register as register_mean_reversion
from zaza.tools.quantitative.monte_carlo import register as register_monte_carlo
from zaza.tools.quantitative.regime import register as register_regime
from zaza.tools.quantitative.volatility import register as register_volatility

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_mcp():
    """Create a mock FastMCP that captures tool registrations."""
    mcp = MagicMock()
    tools: dict[str, object] = {}

    def tool_decorator():
        def decorator(fn):
            tools[fn.__name__] = fn
            return fn
        return decorator

    mcp.tool = tool_decorator
    mcp._registered_tools = tools
    return mcp


@pytest.fixture()
def tmp_cache(tmp_path):
    return FileCache(cache_dir=tmp_path / "cache")


@pytest.fixture()
def price_history():
    """Generate deterministic price history (300 days) for quant tests."""
    rng = np.random.default_rng(42)
    returns = rng.normal(0.0005, 0.02, 300)
    prices = 100 * np.cumprod(1 + returns)
    return [
        {"Close": float(p), "Date": f"2024-{(i // 30) + 1:02d}-{(i % 30) + 1:02d}"}
        for i, p in enumerate(prices)
    ]


# ---------------------------------------------------------------------------
# Price Forecast (ARIMA)
# ---------------------------------------------------------------------------


class TestPriceForecast:
    """Tests for get_price_forecast tool."""

    @pytest.mark.asyncio
    async def test_arima_forecast_returns_predictions(self, mock_mcp, tmp_cache, price_history):
        """get_price_forecast returns forecast with confidence intervals."""
        with patch("zaza.tools.quantitative.forecast.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.quantitative.forecast.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_history.return_value = price_history
                register_forecast(mock_mcp)

                fn = mock_mcp._registered_tools["get_price_forecast"]
                result = json.loads(await fn(ticker="AAPL", horizon_days=30, model="arima"))

        assert result["status"] == "ok"
        assert "forecast" in result["data"]
        assert len(result["data"]["forecast"]) > 0

    @pytest.mark.asyncio
    async def test_insufficient_data_returns_error(self, mock_mcp, tmp_cache):
        """Returns error when insufficient price data."""
        with patch("zaza.tools.quantitative.forecast.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.quantitative.forecast.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_history.return_value = [{"Close": 100.0, "Date": "2025-01-01"}]
                register_forecast(mock_mcp)

                fn = mock_mcp._registered_tools["get_price_forecast"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Volatility Forecast (GARCH)
# ---------------------------------------------------------------------------


class TestVolatilityForecast:
    """Tests for get_volatility_forecast tool."""

    @pytest.mark.asyncio
    async def test_garch_forecast_returns_volatility(self, mock_mcp, tmp_cache, price_history):
        """get_volatility_forecast returns GARCH vol forecast."""
        with patch("zaza.tools.quantitative.volatility.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.quantitative.volatility.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_history.return_value = price_history
                register_volatility(mock_mcp)

                fn = mock_mcp._registered_tools["get_volatility_forecast"]
                result = json.loads(await fn(ticker="AAPL", horizon_days=30))

        assert result["status"] == "ok"
        assert "annualized_vol" in result["data"] or "forecasted_vol" in result["data"]

    @pytest.mark.asyncio
    async def test_insufficient_data_returns_error(self, mock_mcp, tmp_cache):
        """Returns error when insufficient price data for GARCH."""
        short_history = [
            {"Close": float(100 + i * 0.5), "Date": f"2025-01-{i+1:02d}"}
            for i in range(50)
        ]
        with patch("zaza.tools.quantitative.volatility.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.quantitative.volatility.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_history.return_value = short_history
                register_volatility(mock_mcp)

                fn = mock_mcp._registered_tools["get_volatility_forecast"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Monte Carlo Simulation
# ---------------------------------------------------------------------------


class TestMonteCarloSimulation:
    """Tests for get_monte_carlo_simulation tool."""

    @pytest.mark.asyncio
    async def test_simulation_returns_percentiles(self, mock_mcp, tmp_cache, price_history):
        """get_monte_carlo_simulation returns percentiles and probabilities."""
        with patch("zaza.tools.quantitative.monte_carlo.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.quantitative.monte_carlo.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_history.return_value = price_history
                register_monte_carlo(mock_mcp)

                fn = mock_mcp._registered_tools["get_monte_carlo_simulation"]
                result = json.loads(await fn(ticker="AAPL", horizon_days=30, simulations=1000))

        assert result["status"] == "ok"
        assert "percentiles" in result["data"]
        assert "prob_up_5pct" in result["data"]
        assert "prob_down_5pct" in result["data"]

    @pytest.mark.asyncio
    async def test_deterministic_with_seed(self, mock_mcp, tmp_cache, price_history):
        """Results are reproducible when using same seed (via underlying model)."""
        results = []
        for _ in range(2):
            with patch("zaza.tools.quantitative.monte_carlo.FileCache", return_value=tmp_cache):
                with patch("zaza.tools.quantitative.monte_carlo.YFinanceClient") as MockYF:
                    client = MockYF.return_value
                    client.get_history.return_value = price_history
                    register_monte_carlo(mock_mcp)

                    fn = mock_mcp._registered_tools["get_monte_carlo_simulation"]
                    result = json.loads(await fn(ticker="AAPL", horizon_days=30, simulations=1000))
                    results.append(result)

        assert results[0]["data"]["percentiles"] == results[1]["data"]["percentiles"]

    @pytest.mark.asyncio
    async def test_empty_data_returns_error(self, mock_mcp, tmp_cache):
        """Returns error on empty price data."""
        with patch("zaza.tools.quantitative.monte_carlo.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.quantitative.monte_carlo.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_history.return_value = []
                register_monte_carlo(mock_mcp)

                fn = mock_mcp._registered_tools["get_monte_carlo_simulation"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Return Distribution
# ---------------------------------------------------------------------------


class TestReturnDistribution:
    """Tests for get_return_distribution tool."""

    @pytest.mark.asyncio
    async def test_returns_distribution_stats(self, mock_mcp, tmp_cache, price_history):
        """get_return_distribution returns stats, VaR, CVaR."""
        with patch("zaza.tools.quantitative.distribution.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.quantitative.distribution.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_history.return_value = price_history
                register_distribution(mock_mcp)

                fn = mock_mcp._registered_tools["get_return_distribution"]
                result = json.loads(await fn(ticker="AAPL", period="1y"))

        assert result["status"] == "ok"
        data = result["data"]
        assert "mean" in data
        assert "std" in data
        assert "var" in data
        assert "cvar" in data

    @pytest.mark.asyncio
    async def test_empty_data_returns_error(self, mock_mcp, tmp_cache):
        """Returns error on empty price data."""
        with patch("zaza.tools.quantitative.distribution.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.quantitative.distribution.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_history.return_value = []
                register_distribution(mock_mcp)

                fn = mock_mcp._registered_tools["get_return_distribution"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Mean Reversion
# ---------------------------------------------------------------------------


class TestMeanReversion:
    """Tests for get_mean_reversion tool."""

    @pytest.mark.asyncio
    async def test_returns_hurst_and_half_life(self, mock_mcp, tmp_cache, price_history):
        """get_mean_reversion returns Hurst exponent and half-life."""
        with patch("zaza.tools.quantitative.mean_reversion.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.quantitative.mean_reversion.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_history.return_value = price_history
                register_mean_reversion(mock_mcp)

                fn = mock_mcp._registered_tools["get_mean_reversion"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "ok"
        data = result["data"]
        assert "hurst_exponent" in data
        assert 0.0 <= data["hurst_exponent"] <= 1.0
        assert "z_score" in data

    @pytest.mark.asyncio
    async def test_empty_data_returns_error(self, mock_mcp, tmp_cache):
        """Returns error on empty price data."""
        with patch("zaza.tools.quantitative.mean_reversion.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.quantitative.mean_reversion.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_history.return_value = []
                register_mean_reversion(mock_mcp)

                fn = mock_mcp._registered_tools["get_mean_reversion"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Regime Detection
# ---------------------------------------------------------------------------


class TestRegimeDetection:
    """Tests for get_regime_detection tool."""

    @pytest.mark.asyncio
    async def test_returns_regime_classification(self, mock_mcp, tmp_cache, price_history):
        """get_regime_detection returns regime and confidence."""
        with patch("zaza.tools.quantitative.regime.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.quantitative.regime.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_history.return_value = price_history
                register_regime(mock_mcp)

                fn = mock_mcp._registered_tools["get_regime_detection"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "ok"
        data = result["data"]
        assert "regime" in data
        assert data["regime"] in ["trending_up", "trending_down", "range_bound", "high_volatility"]
        assert "confidence" in data

    @pytest.mark.asyncio
    async def test_empty_data_returns_error(self, mock_mcp, tmp_cache):
        """Returns error on empty price data."""
        with patch("zaza.tools.quantitative.regime.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.quantitative.regime.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_history.return_value = []
                register_regime(mock_mcp)

                fn = mock_mcp._registered_tools["get_regime_detection"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "error"
