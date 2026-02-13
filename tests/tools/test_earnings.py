"""Tests for earnings tools (TASK-021): history, calendar, events, buybacks."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from zaza.cache.store import FileCache
from zaza.tools.earnings.buybacks import register as register_buybacks
from zaza.tools.earnings.calendar import register as register_calendar
from zaza.tools.earnings.events import register as register_events
from zaza.tools.earnings.history import register as register_history

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
# Earnings History
# ---------------------------------------------------------------------------


class TestEarningsHistory:
    """Tests for get_earnings_history tool."""

    @pytest.mark.asyncio
    async def test_returns_quarterly_earnings(self, mock_mcp, tmp_cache):
        """get_earnings_history returns per-quarter EPS beat/miss."""
        with patch("zaza.tools.earnings.history.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.earnings.history.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_earnings.return_value = {
                    "earnings_history": [
                        {
                            "Quarter End": "2024-12-31",
                            "EPS Estimate": 2.10,
                            "Reported EPS": 2.18,
                            "Surprise(%)": 3.8,
                        },
                        {
                            "Quarter End": "2024-09-30",
                            "EPS Estimate": 1.95,
                            "Reported EPS": 1.46,
                            "Surprise(%)": -25.1,
                        },
                        {
                            "Quarter End": "2024-06-30",
                            "EPS Estimate": 1.85,
                            "Reported EPS": 1.90,
                            "Surprise(%)": 2.7,
                        },
                        {
                            "Quarter End": "2024-03-31",
                            "EPS Estimate": 1.70,
                            "Reported EPS": 1.72,
                            "Surprise(%)": 1.2,
                        },
                    ],
                    "calendar": {},
                }
                register_history(mock_mcp)

                fn = mock_mcp._registered_tools["get_earnings_history"]
                result = json.loads(await fn(ticker="AAPL", limit=4))

        assert result["status"] == "ok"
        data = result["data"]
        assert "quarters" in data
        assert len(data["quarters"]) == 4
        # Check beat/miss classification
        assert data["quarters"][0]["beat_miss"] == "beat"
        assert data["quarters"][1]["beat_miss"] == "miss"

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self, mock_mcp, tmp_cache):
        """Limits the number of quarters returned."""
        with patch("zaza.tools.earnings.history.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.earnings.history.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_earnings.return_value = {
                    "earnings_history": [
                        {
                            "Quarter End": f"2024-{(12 - i * 3):02d}-30",
                            "EPS Estimate": 2.0,
                            "Reported EPS": 2.1,
                            "Surprise(%)": 5.0,
                        }
                        for i in range(8)
                    ],
                    "calendar": {},
                }
                register_history(mock_mcp)

                fn = mock_mcp._registered_tools["get_earnings_history"]
                result = json.loads(await fn(ticker="AAPL", limit=3))

        assert result["status"] == "ok"
        assert len(result["data"]["quarters"]) == 3

    @pytest.mark.asyncio
    async def test_handles_empty_earnings(self, mock_mcp, tmp_cache):
        """Returns error when no earnings data available."""
        with patch("zaza.tools.earnings.history.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.earnings.history.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_earnings.return_value = {
                    "earnings_history": [],
                    "calendar": {},
                }
                register_history(mock_mcp)

                fn = mock_mcp._registered_tools["get_earnings_history"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Earnings Calendar
# ---------------------------------------------------------------------------


class TestEarningsCalendar:
    """Tests for get_earnings_calendar tool."""

    @pytest.mark.asyncio
    async def test_returns_next_earnings_date(self, mock_mcp, tmp_cache):
        """get_earnings_calendar returns next earnings date and estimates."""
        with patch("zaza.tools.earnings.calendar.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.earnings.calendar.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_earnings.return_value = {
                    "earnings_history": [],
                    "calendar": {
                        "Earnings Date": "2025-04-25",
                        "EPS Estimate": 2.25,
                        "Revenue Estimate": 95000000000,
                    },
                }
                register_calendar(mock_mcp)

                fn = mock_mcp._registered_tools["get_earnings_calendar"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "ok"
        data = result["data"]
        assert "earnings_date" in data
        assert "eps_estimate" in data

    @pytest.mark.asyncio
    async def test_handles_no_calendar_data(self, mock_mcp, tmp_cache):
        """Returns error when no calendar data available."""
        with patch("zaza.tools.earnings.calendar.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.earnings.calendar.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_earnings.return_value = {
                    "earnings_history": [],
                    "calendar": {},
                }
                register_calendar(mock_mcp)

                fn = mock_mcp._registered_tools["get_earnings_calendar"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Event Calendar
# ---------------------------------------------------------------------------


class TestEventCalendar:
    """Tests for get_event_calendar tool."""

    @pytest.mark.asyncio
    async def test_returns_upcoming_events(self, mock_mcp, tmp_cache):
        """get_event_calendar returns dividends, splits, earnings dates."""
        with patch("zaza.tools.earnings.events.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.earnings.events.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_quote.return_value = {
                    "regularMarketPrice": 150.0,
                    "exDividendDate": 1708041600,
                    "dividendDate": 1708646400,
                    "dividendRate": 0.96,
                    "dividendYield": 0.0064,
                    "lastSplitFactor": "4:1",
                    "lastSplitDate": 1598832000,
                }
                client.get_earnings.return_value = {
                    "earnings_history": [],
                    "calendar": {
                        "Earnings Date": "2025-04-25",
                    },
                }
                register_events(mock_mcp)

                fn = mock_mcp._registered_tools["get_event_calendar"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "ok"
        data = result["data"]
        assert "events" in data
        # Should include dividend and/or earnings events
        event_types = [e["type"] for e in data["events"]]
        assert len(event_types) > 0

    @pytest.mark.asyncio
    async def test_handles_no_events(self, mock_mcp, tmp_cache):
        """Returns ok with empty events list when no events available."""
        with patch("zaza.tools.earnings.events.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.earnings.events.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_quote.return_value = {"regularMarketPrice": 50.0}
                client.get_earnings.return_value = {
                    "earnings_history": [],
                    "calendar": {},
                }
                register_events(mock_mcp)

                fn = mock_mcp._registered_tools["get_event_calendar"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "ok"
        assert result["data"]["events"] == []


# ---------------------------------------------------------------------------
# Buyback Data
# ---------------------------------------------------------------------------


class TestBuybackData:
    """Tests for get_buyback_data tool."""

    @pytest.mark.asyncio
    async def test_returns_buyback_info(self, mock_mcp, tmp_cache):
        """get_buyback_data returns buyback metrics from quote."""
        with patch("zaza.tools.earnings.buybacks.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.earnings.buybacks.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_quote.return_value = {
                    "regularMarketPrice": 150.0,
                    "sharesOutstanding": 15000000000,
                    "floatShares": 14500000000,
                    "marketCap": 2250000000000,
                }
                client.get_financials.return_value = {
                    "cash_flow": [
                        {
                            "Repurchase Of Capital Stock": -20000000000,
                            "Issuance Of Capital Stock": 1000000000,
                        },
                        {
                            "Repurchase Of Capital Stock": -18000000000,
                            "Issuance Of Capital Stock": 900000000,
                        },
                    ],
                    "income_statement": [],
                    "balance_sheet": [],
                }
                register_buybacks(mock_mcp)

                fn = mock_mcp._registered_tools["get_buyback_data"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "ok"
        data = result["data"]
        assert "shares_outstanding" in data or "buyback_yield" in data or "net_buyback" in data

    @pytest.mark.asyncio
    async def test_handles_no_buyback_data(self, mock_mcp, tmp_cache):
        """Returns error when no buyback data available."""
        with patch("zaza.tools.earnings.buybacks.FileCache", return_value=tmp_cache):
            with patch("zaza.tools.earnings.buybacks.YFinanceClient") as MockYF:
                client = MockYF.return_value
                client.get_quote.return_value = {}
                client.get_financials.return_value = {
                    "cash_flow": [],
                    "income_statement": [],
                    "balance_sheet": [],
                }
                register_buybacks(mock_mcp)

                fn = mock_mcp._registered_tools["get_buyback_data"]
                result = json.loads(await fn(ticker="AAPL"))

        assert result["status"] == "error"
