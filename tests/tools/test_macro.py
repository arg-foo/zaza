"""Tests for macro tools (TASK-018).

Covers: treasury yields, market indices, commodities, calendar, correlations.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zaza.cache.store import FileCache
from zaza.tools.macro.calendar import register as register_calendar
from zaza.tools.macro.commodities import register as register_commodities
from zaza.tools.macro.correlations import register as register_correlations
from zaza.tools.macro.indices import register as register_indices
from zaza.tools.macro.rates import register as register_rates

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
    """Provide a FileCache backed by a temp directory."""
    return FileCache(cache_dir=tmp_path / "cache")


# ---------------------------------------------------------------------------
# Treasury Yields
# ---------------------------------------------------------------------------


class TestTreasuryYields:
    """Tests for get_treasury_yields tool."""

    def _make_quote_data(self, price: float) -> dict:
        return {"regularMarketPrice": price}

    @pytest.mark.asyncio
    async def test_returns_yields_and_curve_shape(self, mock_mcp, tmp_cache):
        """get_treasury_yields returns yields and curve classification."""
        with patch("zaza.tools.macro.rates.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.macro.rates.YFinanceClient") as MockYF:
                client = MockYF.return_value
                # Normal curve: 3mo < 5Y < 10Y < 30Y
                def quote_side_effect(ticker):
                    data = {
                        "^IRX": {"regularMarketPrice": 3.8},
                        "^FVX": {"regularMarketPrice": 4.2},
                        "^TNX": {"regularMarketPrice": 4.3},
                        "^TYX": {"regularMarketPrice": 4.6},
                    }
                    return data.get(ticker, {})

                client.get_quote.side_effect = quote_side_effect
                register_rates(mock_mcp)

                fn = mock_mcp._registered_tools["get_treasury_yields"]
                result = json.loads(await fn())

        assert result["status"] == "ok"
        assert "yields" in result["data"]
        yields = result["data"]["yields"]
        assert yields["3_month"] == 3.8
        assert yields["30_year"] == 4.6
        assert result["data"]["curve_shape"] == "normal"

    @pytest.mark.asyncio
    async def test_inverted_curve(self, mock_mcp, tmp_cache):
        """Detects inverted yield curve when 3mo > 10Y."""
        with patch("zaza.tools.macro.rates.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.macro.rates.YFinanceClient") as MockYF:
                client = MockYF.return_value

                def quote_side_effect(ticker):
                    data = {
                        "^IRX": {"regularMarketPrice": 5.5},
                        "^FVX": {"regularMarketPrice": 4.2},
                        "^TNX": {"regularMarketPrice": 4.0},
                        "^TYX": {"regularMarketPrice": 4.1},
                    }
                    return data.get(ticker, {})

                client.get_quote.side_effect = quote_side_effect
                register_rates(mock_mcp)

                fn = mock_mcp._registered_tools["get_treasury_yields"]
                result = json.loads(await fn())

        assert result["data"]["curve_shape"] == "inverted"

    @pytest.mark.asyncio
    async def test_handles_empty_data(self, mock_mcp, tmp_cache):
        """Returns error when yfinance returns empty data."""
        with patch("zaza.tools.macro.rates.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.macro.rates.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_quote.return_value = {}
                register_rates(mock_mcp)

                fn = mock_mcp._registered_tools["get_treasury_yields"]
                result = json.loads(await fn())

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Market Indices
# ---------------------------------------------------------------------------


class TestMarketIndices:
    """Tests for get_market_indices tool."""

    @pytest.mark.asyncio
    async def test_returns_indices_with_vix_interpretation(self, mock_mcp, tmp_cache):
        """get_market_indices returns values with VIX interpretation."""
        with patch("zaza.tools.macro.indices.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.macro.indices.YFinanceClient") as MockYF:
                client = MockYF.return_value

                def quote_side_effect(ticker):
                    data = {
                        "^VIX": {
                            "regularMarketPrice": 13.0,
                            "regularMarketPreviousClose": 13.5,
                        },
                        "^GSPC": {
                            "regularMarketPrice": 5000.0,
                            "regularMarketPreviousClose": 4980.0,
                        },
                        "^DJI": {
                            "regularMarketPrice": 38000.0,
                            "regularMarketPreviousClose": 37900.0,
                        },
                        "^IXIC": {
                            "regularMarketPrice": 16000.0,
                            "regularMarketPreviousClose": 15950.0,
                        },
                        "DX-Y.NYB": {
                            "regularMarketPrice": 104.5,
                            "regularMarketPreviousClose": 104.0,
                        },
                    }
                    return data.get(ticker, {})

                client.get_quote.side_effect = quote_side_effect
                register_indices(mock_mcp)

                fn = mock_mcp._registered_tools["get_market_indices"]
                result = json.loads(await fn())

        assert result["status"] == "ok"
        indices = result["data"]["indices"]
        assert indices["VIX"]["value"] == 13.0
        assert result["data"]["vix_interpretation"] == "low"

    @pytest.mark.asyncio
    async def test_high_vix_interpretation(self, mock_mcp, tmp_cache):
        """VIX above 30 is classified as high."""
        with patch("zaza.tools.macro.indices.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.macro.indices.YFinanceClient") as MockYF:
                client = MockYF.return_value

                def quote_side_effect(ticker):
                    data = {
                        "^VIX": {
                            "regularMarketPrice": 35.0,
                            "regularMarketPreviousClose": 32.0,
                        },
                        "^GSPC": {
                            "regularMarketPrice": 4500.0,
                            "regularMarketPreviousClose": 4600.0,
                        },
                        "^DJI": {
                            "regularMarketPrice": 35000.0,
                            "regularMarketPreviousClose": 35500.0,
                        },
                        "^IXIC": {
                            "regularMarketPrice": 14000.0,
                            "regularMarketPreviousClose": 14300.0,
                        },
                        "DX-Y.NYB": {
                            "regularMarketPrice": 105.0,
                            "regularMarketPreviousClose": 104.5,
                        },
                    }
                    return data.get(ticker, {})

                client.get_quote.side_effect = quote_side_effect
                register_indices(mock_mcp)

                fn = mock_mcp._registered_tools["get_market_indices"]
                result = json.loads(await fn())

        assert result["data"]["vix_interpretation"] == "high"

    @pytest.mark.asyncio
    async def test_handles_empty_data(self, mock_mcp, tmp_cache):
        """Returns error on empty data."""
        with patch("zaza.tools.macro.indices.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.macro.indices.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_quote.return_value = {}
                register_indices(mock_mcp)

                fn = mock_mcp._registered_tools["get_market_indices"]
                result = json.loads(await fn())

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Commodities
# ---------------------------------------------------------------------------


class TestCommodityPrices:
    """Tests for get_commodity_prices tool."""

    @pytest.mark.asyncio
    async def test_returns_commodity_prices_and_changes(self, mock_mcp, tmp_cache):
        """get_commodity_prices returns prices and weekly/monthly % change."""
        with patch("zaza.tools.macro.commodities.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.macro.commodities.YFinanceClient") as MockYF:
                client = MockYF.return_value

                def quote_side_effect(ticker):
                    data = {
                        "CL=F": {
                            "regularMarketPrice": 75.0,
                            "regularMarketPreviousClose": 74.5,
                        },
                        "GC=F": {
                            "regularMarketPrice": 2050.0,
                            "regularMarketPreviousClose": 2040.0,
                        },
                        "SI=F": {
                            "regularMarketPrice": 24.5,
                            "regularMarketPreviousClose": 24.3,
                        },
                        "HG=F": {
                            "regularMarketPrice": 3.8,
                            "regularMarketPreviousClose": 3.75,
                        },
                        "NG=F": {
                            "regularMarketPrice": 2.5,
                            "regularMarketPreviousClose": 2.45,
                        },
                    }
                    return data.get(ticker, {})

                def history_side_effect(ticker, period="5d"):
                    return [
                        {"Close": 70.0, "Date": "2025-01-01"},
                        {"Close": 72.0, "Date": "2025-01-02"},
                        {"Close": 73.0, "Date": "2025-01-03"},
                        {"Close": 74.0, "Date": "2025-01-04"},
                        {"Close": 75.0, "Date": "2025-01-05"},
                    ]

                client.get_quote.side_effect = quote_side_effect
                client.get_history.side_effect = history_side_effect
                register_commodities(mock_mcp)

                fn = mock_mcp._registered_tools["get_commodity_prices"]
                result = json.loads(await fn())

        assert result["status"] == "ok"
        assert "crude_oil" in result["data"]
        assert result["data"]["crude_oil"]["price"] == 75.0

    @pytest.mark.asyncio
    async def test_handles_empty_data(self, mock_mcp, tmp_cache):
        """Returns error on empty data."""
        with patch("zaza.tools.macro.commodities.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.macro.commodities.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_quote.return_value = {}
                client.get_history.return_value = []
                register_commodities(mock_mcp)

                fn = mock_mcp._registered_tools["get_commodity_prices"]
                result = json.loads(await fn())

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Economic Calendar
# ---------------------------------------------------------------------------


class TestEconomicCalendar:
    """Tests for get_economic_calendar tool."""

    @pytest.mark.asyncio
    async def test_returns_events_with_fred(self, mock_mcp, tmp_cache):
        """get_economic_calendar returns events from FRED when key is available."""
        with patch("zaza.tools.macro.calendar.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.macro.calendar.has_fred_key", return_value=True):
                with patch("zaza.tools.macro.calendar.get_fred_api_key", return_value="test_key"):
                    with patch("zaza.tools.macro.calendar.FredClient") as MockFred:
                        fred = MockFred.return_value
                        fred.get_release_dates = AsyncMock(return_value=[
                            {"release_id": "10", "release_name": "CPI", "date": "2025-02-15"},
                            {"release_id": "50", "release_name": "GDP", "date": "2025-02-20"},
                        ])
                        register_calendar(mock_mcp)

                        fn = mock_mcp._registered_tools["get_economic_calendar"]
                        result = json.loads(await fn())

        assert result["status"] == "ok"
        assert len(result["data"]["events"]) == 2

    @pytest.mark.asyncio
    async def test_degrades_gracefully_without_fred_key(self, mock_mcp, tmp_cache):
        """Returns placeholder message when FRED key is absent."""
        with patch("zaza.tools.macro.calendar.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.macro.calendar.has_fred_key", return_value=False):
                register_calendar(mock_mcp)

                fn = mock_mcp._registered_tools["get_economic_calendar"]
                result = json.loads(await fn())

        assert result["status"] == "ok"
        source_check = "unavailable" in result["data"]["source"].lower()
        msg_check = "not configured" in result["data"]["message"].lower()
        assert source_check or msg_check

    @pytest.mark.asyncio
    async def test_handles_fred_error(self, mock_mcp, tmp_cache):
        """Returns error when FRED API fails."""
        with patch("zaza.tools.macro.calendar.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.macro.calendar.has_fred_key", return_value=True):
                with patch("zaza.tools.macro.calendar.get_fred_api_key", return_value="test_key"):
                    with patch("zaza.tools.macro.calendar.FredClient") as MockFred:
                        fred = MockFred.return_value
                        fred.get_release_dates = AsyncMock(side_effect=Exception("API error"))
                        register_calendar(mock_mcp)

                        fn = mock_mcp._registered_tools["get_economic_calendar"]
                        result = json.loads(await fn())

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Intermarket Correlations
# ---------------------------------------------------------------------------


class TestIntermarketCorrelations:
    """Tests for get_intermarket_correlations tool."""

    @pytest.mark.asyncio
    async def test_returns_correlations_for_ticker(self, mock_mcp, tmp_cache):
        """get_intermarket_correlations returns correlation matrix."""
        import numpy as np

        with patch("zaza.tools.macro.correlations.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.macro.correlations.YFinanceClient") as MockYF:
                client = MockYF.return_value
                # Generate correlated price data
                rng = np.random.default_rng(42)
                n = 100
                base = np.cumsum(rng.standard_normal(n)) + 100

                def history_side_effect(ticker, period="6mo"):
                    rng_local = np.random.default_rng(hash(ticker) % 2**31)
                    noise = rng_local.standard_normal(n) * 2
                    prices = base + noise
                    return [
                        {"Close": float(p), "Date": f"2025-01-{i+1:02d}"}
                        for i, p in enumerate(prices)
                    ]

                client.get_history.side_effect = history_side_effect
                register_correlations(mock_mcp)

                fn = mock_mcp._registered_tools["get_intermarket_correlations"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "ok"
        assert "correlations" in result["data"]
        corr = result["data"]["correlations"]
        # Should have correlations with benchmark tickers
        assert "SP500" in corr or "^GSPC" in corr

    @pytest.mark.asyncio
    async def test_handles_insufficient_data(self, mock_mcp, tmp_cache):
        """Returns error when insufficient data for correlations."""
        with patch("zaza.tools.macro.correlations.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.macro.correlations.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_history.return_value = []
                register_correlations(mock_mcp)

                fn = mock_mcp._registered_tools["get_intermarket_correlations"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "error"
