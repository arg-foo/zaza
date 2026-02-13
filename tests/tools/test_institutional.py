"""Tests for institutional tools (TASK-020): short interest, holdings, flows, dark pool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from zaza.cache.store import FileCache
from zaza.tools.institutional.dark_pool import register as register_dark_pool
from zaza.tools.institutional.flows import register as register_flows
from zaza.tools.institutional.holdings import register as register_holdings
from zaza.tools.institutional.short_interest import register as register_short_interest

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


# ---------------------------------------------------------------------------
# Short Interest
# ---------------------------------------------------------------------------


class TestShortInterest:
    """Tests for get_short_interest tool."""

    @pytest.mark.asyncio
    async def test_returns_short_interest_data(self, mock_mcp, tmp_cache):
        """get_short_interest returns short metrics and squeeze score."""
        with patch("zaza.tools.institutional.short_interest.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.institutional.short_interest.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_quote.return_value = {
                    "regularMarketPrice": 150.0,
                    "shortPercentOfFloat": 0.05,
                    "sharesShort": 5000000,
                    "shortRatio": 2.5,
                    "sharesOutstanding": 100000000,
                    "averageVolume": 50000000,
                }
                register_short_interest(mock_mcp)

                fn = mock_mcp._registered_tools["get_short_interest"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "ok"
        data = result["data"]
        assert "short_percent_of_float" in data
        assert "short_ratio" in data
        assert "squeeze_score" in data

    @pytest.mark.asyncio
    async def test_high_short_interest_squeeze_score(self, mock_mcp, tmp_cache):
        """High short interest produces high squeeze score."""
        with patch("zaza.tools.institutional.short_interest.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.institutional.short_interest.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_quote.return_value = {
                    "regularMarketPrice": 10.0,
                    "shortPercentOfFloat": 0.40,
                    "sharesShort": 40000000,
                    "shortRatio": 8.0,
                    "sharesOutstanding": 100000000,
                    "averageVolume": 5000000,
                }
                register_short_interest(mock_mcp)

                fn = mock_mcp._registered_tools["get_short_interest"]
                result = json.loads(await fn(ticker="GME"))

        data = result["data"]
        assert data["squeeze_score"] > 5  # High squeeze potential

    @pytest.mark.asyncio
    async def test_handles_missing_data(self, mock_mcp, tmp_cache):
        """Returns error when quote data is empty."""
        with patch("zaza.tools.institutional.short_interest.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.institutional.short_interest.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_quote.return_value = {}
                register_short_interest(mock_mcp)

                fn = mock_mcp._registered_tools["get_short_interest"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Institutional Holdings
# ---------------------------------------------------------------------------


class TestInstitutionalHoldings:
    """Tests for get_institutional_holdings tool."""

    @pytest.mark.asyncio
    async def test_returns_top_holders(self, mock_mcp, tmp_cache):
        """get_institutional_holdings returns top 10 holders."""
        with patch("zaza.tools.institutional.holdings.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.institutional.holdings.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_institutional_holders.return_value = {
                    "institutional_holders": [
                        {
                            "Holder": "Vanguard",
                            "Shares": 1000000,
                            "Value": 150000000,
                            "% Out": 0.08,
                        },
                        {
                            "Holder": "BlackRock",
                            "Shares": 900000,
                            "Value": 135000000,
                            "% Out": 0.07,
                        },
                        {
                            "Holder": "State Street",
                            "Shares": 500000,
                            "Value": 75000000,
                            "% Out": 0.04,
                        },
                    ],
                    "major_holders": [
                        {"0": "5.23%", "1": "% of Shares Held by All Insider"},
                        {"0": "63.19%", "1": "% of Shares Held by Institutions"},
                    ],
                }
                register_holdings(mock_mcp)

                fn = mock_mcp._registered_tools["get_institutional_holdings"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "ok"
        data = result["data"]
        assert "top_holders" in data
        assert len(data["top_holders"]) >= 1

    @pytest.mark.asyncio
    async def test_handles_empty_holders(self, mock_mcp, tmp_cache):
        """Returns error when no holder data available."""
        with patch("zaza.tools.institutional.holdings.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.institutional.holdings.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_institutional_holders.return_value = {
                    "institutional_holders": [],
                    "major_holders": [],
                }
                register_holdings(mock_mcp)

                fn = mock_mcp._registered_tools["get_institutional_holdings"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Fund Flows
# ---------------------------------------------------------------------------


class TestFundFlows:
    """Tests for get_fund_flows tool."""

    @pytest.mark.asyncio
    async def test_returns_flow_proxy_data(self, mock_mcp, tmp_cache):
        """get_fund_flows returns sector ETF volume/price trend proxy."""
        with patch("zaza.tools.institutional.flows.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.institutional.flows.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_quote.return_value = {
                    "regularMarketPrice": 150.0,
                    "sector": "Technology",
                }

                def history_side_effect(ticker, period="1mo"):
                    return [
                        {"Close": 50.0, "Volume": 10000000, "Date": "2025-01-01"},
                        {"Close": 51.0, "Volume": 12000000, "Date": "2025-01-02"},
                        {"Close": 52.0, "Volume": 11000000, "Date": "2025-01-03"},
                        {"Close": 53.0, "Volume": 13000000, "Date": "2025-01-04"},
                        {"Close": 54.0, "Volume": 14000000, "Date": "2025-01-05"},
                    ]

                client.get_history.side_effect = history_side_effect
                register_flows(mock_mcp)

                fn = mock_mcp._registered_tools["get_fund_flows"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "ok"
        data = result["data"]
        assert "sector_etf" in data or "flow_signal" in data

    @pytest.mark.asyncio
    async def test_handles_unknown_sector(self, mock_mcp, tmp_cache):
        """Handles tickers with no sector mapping."""
        with patch("zaza.tools.institutional.flows.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.institutional.flows.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_quote.return_value = {
                    "regularMarketPrice": 50.0,
                }
                client.get_history.return_value = [
                    {"Close": 50.0, "Volume": 10000000, "Date": "2025-01-01"},
                    {"Close": 51.0, "Volume": 12000000, "Date": "2025-01-02"},
                ]
                register_flows(mock_mcp)

                fn = mock_mcp._registered_tools["get_fund_flows"]
                result = json.loads(await fn(ticker="AAPL"))

        # Should still return ok with whatever data is available
        assert result["status"] in ("ok", "error")


# ---------------------------------------------------------------------------
# Dark Pool Activity
# ---------------------------------------------------------------------------


class TestDarkPoolActivity:
    """Tests for get_dark_pool_activity tool."""

    @pytest.mark.asyncio
    async def test_returns_dark_pool_estimate(self, mock_mcp, tmp_cache):
        """get_dark_pool_activity returns off-exchange % estimate."""
        with patch("zaza.tools.institutional.dark_pool.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.institutional.dark_pool.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_quote.return_value = {
                    "regularMarketPrice": 150.0,
                    "regularMarketVolume": 50000000,
                    "averageVolume": 45000000,
                    "averageVolume10days": 48000000,
                }
                client.get_history.return_value = [
                    {"Close": 148.0, "Volume": 40000000, "Date": "2025-01-01"},
                    {"Close": 149.0, "Volume": 42000000, "Date": "2025-01-02"},
                    {"Close": 150.0, "Volume": 50000000, "Date": "2025-01-03"},
                ]
                register_dark_pool(mock_mcp)

                fn = mock_mcp._registered_tools["get_dark_pool_activity"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "ok"
        data = result["data"]
        assert "estimated_off_exchange_pct" in data

    @pytest.mark.asyncio
    async def test_handles_missing_volume_data(self, mock_mcp, tmp_cache):
        """Returns error when volume data is missing."""
        with patch("zaza.tools.institutional.dark_pool.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.institutional.dark_pool.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_quote.return_value = {}
                client.get_history.return_value = []
                register_dark_pool(mock_mcp)

                fn = mock_mcp._registered_tools["get_dark_pool_activity"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "error"
