"""Tests for yfinance-powered stock screener tools.

Tests screen_stocks, get_screening_strategies, get_buy_sell_levels,
scoring functions, and query builders. All external APIs are mocked.
"""

from __future__ import annotations

import asyncio
import importlib
import json
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_file_cache() -> Any:
    """Prevent all tests from writing to the real ~/.zaza/cache/ directory.

    This autouse fixture patches FileCache so that register() never
    creates real cache files on disk during tests.
    """
    with patch("zaza.tools.screener.screener.FileCache") as MockCache:
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.make_key.return_value = "test_cache_key"
        MockCache.return_value = mock_cache
        yield MockCache


def _make_ohlcv_df(n: int = 100) -> pd.DataFrame:
    """Create a seeded random OHLCV DataFrame for deterministic tests."""
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    open_ = close + np.random.randn(n) * 0.2
    volume = np.random.randint(100_000, 10_000_000, size=n).astype(float)
    return pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })


def _make_screen_response(symbols: list[str]) -> dict[str, Any]:
    """Build a mock response matching yf.screen() output shape."""
    quotes = []
    for s in symbols:
        quotes.append({
            "symbol": s,
            "shortName": f"{s} Inc.",
            "regularMarketPrice": 150.0,
            "regularMarketChangePercent": 2.5,
            "averageDailyVolume3Month": 5_000_000,
            "fiftyTwoWeekChangePercent": 85.0,
            "marketCap": 1_000_000_000,
            "fiftyTwoWeekHigh": 160.0,
            "fiftyTwoWeekLow": 90.0,
            "short_percentage_of_shares_outstanding": {"value": 15.0},
        })
    return {"quotes": quotes, "total": len(quotes)}


def _make_history_records(n: int = 100) -> list[dict[str, Any]]:
    """Create mock yfinance history records (list of dicts with OHLCV keys)."""
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    records = []
    for i in range(n):
        records.append({
            "Open": float(close[i] + np.random.randn() * 0.2),
            "High": float(close[i] + abs(np.random.randn() * 0.3)),
            "Low": float(close[i] - abs(np.random.randn() * 0.3)),
            "Close": float(close[i]),
            "Volume": int(np.random.randint(100_000, 10_000_000)),
        })
    return records


# ---------------------------------------------------------------------------
# TestScreenStocks
# ---------------------------------------------------------------------------

class TestScreenStocks:
    """Tests for the screen_stocks MCP tool."""

    @pytest.mark.asyncio
    async def test_valid_scan_returns_results(self) -> None:
        """Valid scan type with mocked yf.screen + history returns results."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        screen_resp = _make_screen_response(["AAPL", "MSFT", "GOOG"])
        history_records = _make_history_records()

        with (
            patch("zaza.tools.screener.screener.yf") as mock_yf,
            patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
        ):
            mock_yf.screen.return_value = screen_resp
            mock_client = MagicMock()
            mock_client.get_history.return_value = history_records
            MockYFClient.return_value = mock_client

            mcp = FastMCP("test")
            register(mcp)

            tool = mcp._tool_manager.get_tool("screen_stocks")
            result_str = await tool.run(arguments={"scan_type": "breakout"})
            result = json.loads(result_str)

        assert "error" not in result
        assert "results" in result
        assert len(result["results"]) > 0

    @pytest.mark.asyncio
    async def test_invalid_scan_type_returns_error(self) -> None:
        """Unknown scan type returns error without calling yfinance."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        mcp = FastMCP("test")
        register(mcp)

        tool = mcp._tool_manager.get_tool("screen_stocks")
        result_str = await tool.run(arguments={"scan_type": "nonexistent_type"})
        result = json.loads(result_str)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_unsupported_market_returns_error(self) -> None:
        """Unsupported market returns error."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        mcp = FastMCP("test")
        register(mcp)

        tool = mcp._tool_manager.get_tool("screen_stocks")
        result_str = await tool.run(
            arguments={"scan_type": "breakout", "market": "UNKNOWN_MKT"}
        )
        result = json.loads(result_str)

        assert "error" in result
        assert "Unsupported market" in result["error"]

    @pytest.mark.asyncio
    async def test_empty_screen_results(self) -> None:
        """Empty yf.screen response returns empty results list."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        with (
            patch("zaza.tools.screener.screener.yf") as mock_yf,
            patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
            patch("zaza.tools.screener.screener.FileCache") as MockCache,
        ):
            mock_yf.screen.return_value = {"quotes": [], "total": 0}
            mock_client = MagicMock()
            MockYFClient.return_value = mock_client
            mock_cache = MagicMock()
            mock_cache.get.return_value = None
            mock_cache.make_key.return_value = "screen__NASDAQ__momentum"
            MockCache.return_value = mock_cache

            mcp = FastMCP("test")
            register(mcp)

            tool = mcp._tool_manager.get_tool("screen_stocks")
            result_str = await tool.run(arguments={"scan_type": "momentum"})
            result = json.loads(result_str)

        assert "error" not in result
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_yfinance_screen_error_handled(self) -> None:
        """Exception from yf.screen is caught and returns error JSON."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        with (
            patch("zaza.tools.screener.screener.yf") as mock_yf,
            patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
            patch("zaza.tools.screener.screener.FileCache") as MockCache,
        ):
            mock_yf.screen.side_effect = Exception("API rate limit exceeded")
            mock_client = MagicMock()
            MockYFClient.return_value = mock_client
            mock_cache = MagicMock()
            mock_cache.get.return_value = None
            mock_cache.make_key.return_value = "screen__NASDAQ__momentum"
            MockCache.return_value = mock_cache

            mcp = FastMCP("test")
            register(mcp)

            tool = mcp._tool_manager.get_tool("screen_stocks")
            result_str = await tool.run(arguments={"scan_type": "momentum"})
            result = json.loads(result_str)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_results_sorted_by_score_descending(self) -> None:
        """Results are sorted by score in descending order."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        mcp = FastMCP("test")
        register(mcp)

        screen_resp = _make_screen_response(["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"])
        history_records = _make_history_records()

        with (
            patch("zaza.tools.screener.screener.yf") as mock_yf,
            patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
        ):
            mock_yf.screen.return_value = screen_resp
            mock_client = MagicMock()
            mock_client.get_history.return_value = history_records
            MockYFClient.return_value = mock_client

            tool = mcp._tool_manager.get_tool("screen_stocks")
            result_str = await tool.run(arguments={"scan_type": "momentum"})
            result = json.loads(result_str)

        if result.get("results"):
            scores = [r["score"] for r in result["results"]]
            assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_all_nine_scan_types_accepted(self) -> None:
        """All nine scan types are accepted without error."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        mcp = FastMCP("test")
        register(mcp)

        scan_types = [
            "breakout", "momentum", "consolidation", "volume", "reversal",
            "ipo", "short_squeeze", "bullish", "bearish",
        ]

        screen_resp = _make_screen_response(["AAPL"])
        history_records = _make_history_records()

        for st in scan_types:
            with (
                patch("zaza.tools.screener.screener.yf") as mock_yf,
                patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
            ):
                mock_yf.screen.return_value = screen_resp
                mock_client = MagicMock()
                mock_client.get_history.return_value = history_records
                MockYFClient.return_value = mock_client

                tool = mcp._tool_manager.get_tool("screen_stocks")
                result_str = await tool.run(arguments={"scan_type": st})
                result = json.loads(result_str)

            assert "error" not in result, f"Scan type '{st}' returned error: {result}"

    @pytest.mark.asyncio
    async def test_pagination_fetches_all_pages(self) -> None:
        """screen_stocks paginates through all yf.screen() pages."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        mcp = FastMCP("test")
        register(mcp)

        # Simulate 3 pages: 250 + 250 + 100 = 600 total candidates
        page1 = [{"symbol": f"SYM{i}", "regularMarketPrice": 100.0,
                   "regularMarketChangePercent": 1.0,
                   "averageDailyVolume3Month": 1_000_000}
                  for i in range(250)]
        page2 = [{"symbol": f"SYM{i}", "regularMarketPrice": 100.0,
                   "regularMarketChangePercent": 1.0,
                   "averageDailyVolume3Month": 1_000_000}
                  for i in range(250, 500)]
        page3 = [{"symbol": f"SYM{i}", "regularMarketPrice": 100.0,
                   "regularMarketChangePercent": 1.0,
                   "averageDailyVolume3Month": 1_000_000}
                  for i in range(500, 600)]

        history_records = _make_history_records()

        with (
            patch("zaza.tools.screener.screener.yf") as mock_yf,
            patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
        ):
            mock_yf.screen.side_effect = [
                {"quotes": page1, "total": 600},
                {"quotes": page2, "total": 600},
                {"quotes": page3, "total": 600},
            ]
            mock_client = MagicMock()
            mock_client.get_history.return_value = history_records
            MockYFClient.return_value = mock_client

            tool = mcp._tool_manager.get_tool("screen_stocks")
            result_str = await tool.run(arguments={"scan_type": "momentum"})
            result = json.loads(result_str)

        assert "error" not in result
        assert result["total_candidates"] == 600
        assert mock_yf.screen.call_count == 3

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(self) -> None:
        """When cache has results, yf.screen is not called."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        cached_data = {
            "scan_type": "breakout",
            "market": "NASDAQ",
            "total_results": 1,
            "results": [{"symbol": "AAPL", "score": 85, "signals": ["test"]}],
        }

        with (
            patch("zaza.tools.screener.screener.yf") as mock_yf,
            patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
            patch("zaza.tools.screener.screener.FileCache") as MockCache,
        ):
            mock_cache = MagicMock()
            mock_cache.get.return_value = cached_data
            mock_cache.make_key.return_value = "screen__NASDAQ__breakout"
            MockCache.return_value = mock_cache

            mock_client = MagicMock()
            MockYFClient.return_value = mock_client

            mcp = FastMCP("test")
            register(mcp)

            tool = mcp._tool_manager.get_tool("screen_stocks")
            result_str = await tool.run(arguments={"scan_type": "breakout"})
            result = json.loads(result_str)

        # yf.screen should NOT have been called since cache returned data
        mock_yf.screen.assert_not_called()
        assert result["results"][0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_result_shape_has_required_fields(self) -> None:
        """Each result item has symbol, score, and signals fields."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        mcp = FastMCP("test")
        register(mcp)

        screen_resp = _make_screen_response(["AAPL", "MSFT"])
        history_records = _make_history_records()

        with (
            patch("zaza.tools.screener.screener.yf") as mock_yf,
            patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
        ):
            mock_yf.screen.return_value = screen_resp
            mock_client = MagicMock()
            mock_client.get_history.return_value = history_records
            MockYFClient.return_value = mock_client

            tool = mcp._tool_manager.get_tool("screen_stocks")
            result_str = await tool.run(arguments={"scan_type": "breakout"})
            result = json.loads(result_str)

        for item in result["results"]:
            assert "symbol" in item
            assert "score" in item
            assert "signals" in item
            assert isinstance(item["score"], (int, float))
            assert 0 <= item["score"] <= 100
            assert isinstance(item["signals"], list)


# ---------------------------------------------------------------------------
# TestScreeningStrategies
# ---------------------------------------------------------------------------

class TestScreeningStrategies:
    """Tests for the get_screening_strategies tool."""

    @pytest.mark.asyncio
    async def test_returns_nine_strategies(self) -> None:
        """Returns exactly nine strategies."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        mcp = FastMCP("test")
        register(mcp)

        tool = mcp._tool_manager.get_tool("get_screening_strategies")
        result_str = await tool.run(arguments={})
        result = json.loads(result_str)

        assert "strategies" in result
        assert len(result["strategies"]) == 9

    @pytest.mark.asyncio
    async def test_strategy_shape_has_name_and_description(self) -> None:
        """Each strategy has name and description fields."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        mcp = FastMCP("test")
        register(mcp)

        tool = mcp._tool_manager.get_tool("get_screening_strategies")
        result_str = await tool.run(arguments={})
        result = json.loads(result_str)

        for s in result["strategies"]:
            assert "name" in s
            assert "description" in s
            assert isinstance(s["name"], str)
            assert isinstance(s["description"], str)
            assert len(s["name"]) > 0
            assert len(s["description"]) > 0

    @pytest.mark.asyncio
    async def test_known_strategies_present(self) -> None:
        """All nine expected strategy names are present."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        mcp = FastMCP("test")
        register(mcp)

        tool = mcp._tool_manager.get_tool("get_screening_strategies")
        result_str = await tool.run(arguments={})
        result = json.loads(result_str)

        names = {s["name"] for s in result["strategies"]}
        expected = {
            "breakout", "momentum", "consolidation", "volume", "reversal",
            "ipo", "short_squeeze", "bullish", "bearish",
        }
        assert names == expected


# ---------------------------------------------------------------------------
# TestBuySellLevels
# ---------------------------------------------------------------------------

class TestBuySellLevels:
    """Tests for the get_buy_sell_levels tool."""

    @pytest.mark.asyncio
    async def test_valid_ticker_returns_levels(self) -> None:
        """Valid ticker returns buy/sell levels."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        history_records = _make_history_records()

        with patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient:
            mock_client = MagicMock()
            mock_client.get_history.return_value = history_records
            MockYFClient.return_value = mock_client

            mcp = FastMCP("test")
            register(mcp)

            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            result_str = await tool.run(arguments={"ticker": "AAPL"})
            result = json.loads(result_str)

        assert "error" not in result
        assert "ticker" in result
        assert result["ticker"] == "AAPL"
        assert "pivot_points" in result
        assert "fibonacci_levels" in result
        assert "buy_zone" in result
        assert "sell_zone" in result

    @pytest.mark.asyncio
    async def test_invalid_ticker_format_returns_error(self) -> None:
        """Invalid ticker format returns error."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        mcp = FastMCP("test")
        register(mcp)

        tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
        result_str = await tool.run(arguments={"ticker": "INVALID!!!"})
        result = json.loads(result_str)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_unsupported_market_returns_error(self) -> None:
        """Unsupported market returns error."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        mcp = FastMCP("test")
        register(mcp)

        tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
        result_str = await tool.run(
            arguments={"ticker": "AAPL", "market": "UNKNOWN_MKT"}
        )
        result = json.loads(result_str)

        assert "error" in result
        assert "Unsupported market" in result["error"]

    @pytest.mark.asyncio
    async def test_no_history_returns_error(self) -> None:
        """Empty history data returns error."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        with patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient:
            mock_client = MagicMock()
            mock_client.get_history.return_value = []
            MockYFClient.return_value = mock_client

            mcp = FastMCP("test")
            register(mcp)

            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            result_str = await tool.run(arguments={"ticker": "AAPL"})
            result = json.loads(result_str)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_buy_below_sell(self) -> None:
        """Buy zone max is below sell zone min."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        history_records = _make_history_records()

        with (
            patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
            patch("zaza.tools.screener.screener.FileCache") as MockCache,
        ):
            mock_client = MagicMock()
            mock_client.get_history.return_value = history_records
            MockYFClient.return_value = mock_client
            mock_cache = MagicMock()
            MockCache.return_value = mock_cache

            mcp = FastMCP("test")
            register(mcp)

            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            result_str = await tool.run(arguments={"ticker": "AAPL"})
            result = json.loads(result_str)

        # Assert no error explicitly -- do not conditionally skip
        assert "error" not in result, f"Unexpected error: {result.get('error')}"

        buy_max = result["buy_zone"]["upper"]
        sell_min = result["sell_zone"]["lower"]
        assert buy_max <= sell_min, (
            f"Buy zone upper ({buy_max}) should be <= sell zone lower ({sell_min})"
        )


# ---------------------------------------------------------------------------
# TestScoringFunctions
# ---------------------------------------------------------------------------

class TestScoringFunctions:
    """Tests for TA scoring functions in scan_types module."""

    def test_momentum_scoring_returns_valid_score(self) -> None:
        """Momentum scoring returns score 0-100 and signals list."""
        from zaza.tools.screener.scan_types import SCAN_TYPES

        df = _make_ohlcv_df()
        quote = {
            "regularMarketChangePercent": 3.0,
            "averageDailyVolume3Month": 5_000_000,
        }

        config = SCAN_TYPES["momentum"]
        result = config.score_candidate(df, quote)

        assert "score" in result
        assert "signals" in result
        assert 0 <= result["score"] <= 100
        assert isinstance(result["signals"], list)

    def test_breakout_scoring_returns_valid_score(self) -> None:
        """Breakout scoring returns score 0-100 and signals list."""
        from zaza.tools.screener.scan_types import SCAN_TYPES

        df = _make_ohlcv_df()
        quote = {
            "fiftyTwoWeekHigh": 110.0,
            "fiftyTwoWeekLow": 90.0,
            "fiftyTwoWeekChangePercent": 85.0,
            "averageDailyVolume3Month": 5_000_000,
        }

        config = SCAN_TYPES["breakout"]
        result = config.score_candidate(df, quote)

        assert "score" in result
        assert "signals" in result
        assert 0 <= result["score"] <= 100
        assert isinstance(result["signals"], list)

    def test_score_capped_at_100(self) -> None:
        """Score never exceeds 100 even with extreme inputs."""
        from zaza.tools.screener.scan_types import SCAN_TYPES

        # Create a DataFrame that would produce very high raw scores
        np.random.seed(42)
        n = 100
        # Strong uptrend with high volume
        close = np.linspace(80, 150, n)
        high = close + 2.0
        low = close - 0.5
        open_ = close - 0.3
        volume = np.full(n, 50_000_000.0)
        df = pd.DataFrame({
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        })

        quote = {
            "fiftyTwoWeekHigh": 151.0,
            "fiftyTwoWeekLow": 70.0,
            "fiftyTwoWeekChangePercent": 100.0,
            "averageDailyVolume3Month": 50_000_000,
            "regularMarketChangePercent": 10.0,
            "short_percentage_of_shares_outstanding": {"value": 40.0},
        }

        for name, config in SCAN_TYPES.items():
            result = config.score_candidate(df, quote)
            assert result["score"] <= 100, (
                f"Score for {name} was {result['score']}, expected <= 100"
            )
            assert result["score"] >= 0, (
                f"Score for {name} was {result['score']}, expected >= 0"
            )


# ---------------------------------------------------------------------------
# TestQueryBuilders
# ---------------------------------------------------------------------------

class TestQueryBuilders:
    """Tests for EquityQuery builders in scan_types module."""

    def test_all_nine_types_produce_equity_query(self) -> None:
        """All nine scan types produce a valid EquityQuery."""
        from yfinance import EquityQuery

        from zaza.tools.screener.scan_types import SCAN_TYPES

        for name, config in SCAN_TYPES.items():
            query = config.build_query("NMS")
            assert isinstance(query, EquityQuery), (
                f"Scan type '{name}' did not produce an EquityQuery"
            )
            # Verify it can be serialized
            d = query.to_dict()
            assert "operator" in d
            assert "operands" in d


# ---------------------------------------------------------------------------
# CR-1: SCREENER_TA_CONCURRENCY must be at least 1
# ---------------------------------------------------------------------------

class TestScreenerTAConcurrency:
    """Tests for SCREENER_TA_CONCURRENCY minimum value guard."""

    def test_concurrency_zero_env_var_is_clamped_to_one(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SCREENER_TA_CONCURRENCY=0 via env must not produce 0 (deadlock)."""
        monkeypatch.setenv("SCREENER_TA_CONCURRENCY", "0")
        import zaza.config as config_module
        importlib.reload(config_module)
        assert config_module.SCREENER_TA_CONCURRENCY >= 1, (
            "SCREENER_TA_CONCURRENCY=0 would cause asyncio.Semaphore(0) deadlock"
        )
        # Clean up
        monkeypatch.delenv("SCREENER_TA_CONCURRENCY", raising=False)
        importlib.reload(config_module)

    def test_concurrency_negative_env_var_is_clamped_to_one(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Negative SCREENER_TA_CONCURRENCY must be clamped to at least 1."""
        monkeypatch.setenv("SCREENER_TA_CONCURRENCY", "-5")
        import zaza.config as config_module
        importlib.reload(config_module)
        assert config_module.SCREENER_TA_CONCURRENCY >= 1
        monkeypatch.delenv("SCREENER_TA_CONCURRENCY", raising=False)
        importlib.reload(config_module)

    def test_concurrency_valid_value_preserved(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Valid positive SCREENER_TA_CONCURRENCY is preserved as-is."""
        monkeypatch.setenv("SCREENER_TA_CONCURRENCY", "5")
        import zaza.config as config_module
        importlib.reload(config_module)
        assert config_module.SCREENER_TA_CONCURRENCY == 5
        monkeypatch.delenv("SCREENER_TA_CONCURRENCY", raising=False)
        importlib.reload(config_module)


# ---------------------------------------------------------------------------
# CR-2: _score_symbol and get_buy_sell_levels must use period="1y"
# ---------------------------------------------------------------------------

class TestPeriodIsOneYear:
    """Verify that _score_symbol and get_buy_sell_levels fetch 1 year of data."""

    @pytest.mark.asyncio
    async def test_score_symbol_uses_one_year_period(self) -> None:
        """_score_symbol must call get_history with period='1y' for golden cross."""
        from zaza.tools.screener.screener import _score_symbol

        mock_client = MagicMock()
        mock_client.get_history.return_value = _make_history_records(250)
        semaphore = asyncio.Semaphore(1)

        def dummy_score(df: Any, quote: Any) -> dict[str, Any]:
            return {"score": 50, "signals": []}

        await _score_symbol(
            mock_client, "AAPL", {"regularMarketPrice": 150.0}, dummy_score, semaphore
        )

        mock_client.get_history.assert_called_once_with("AAPL", period="1y")

    @pytest.mark.asyncio
    async def test_buy_sell_levels_uses_one_year_period(self) -> None:
        """get_buy_sell_levels must call get_history with period='1y'."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        history_records = _make_history_records(250)

        with (
            patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
            patch("zaza.tools.screener.screener.FileCache") as MockCache,
        ):
            mock_client = MagicMock()
            mock_client.get_history.return_value = history_records
            MockYFClient.return_value = mock_client
            mock_cache = MagicMock()
            MockCache.return_value = mock_cache

            mcp = FastMCP("test")
            register(mcp)

            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            await tool.run(arguments={"ticker": "AAPL"})

        mock_client.get_history.assert_called_once_with("AAPL", period="1y")


# ---------------------------------------------------------------------------
# HR-1: Additional coverage for edge cases
# ---------------------------------------------------------------------------

class TestScoreSymbolEdgeCases:
    """Tests for _score_symbol edge cases (short history, exceptions)."""

    @pytest.mark.asyncio
    async def test_score_symbol_short_history_returns_none(self) -> None:
        """_score_symbol returns None when history has fewer than 20 records."""
        from zaza.tools.screener.screener import _score_symbol

        mock_client = MagicMock()
        # Return only 10 records (< 20 threshold)
        mock_client.get_history.return_value = _make_history_records(10)
        semaphore = asyncio.Semaphore(1)

        def dummy_score(df: Any, quote: Any) -> dict[str, Any]:
            return {"score": 50, "signals": []}

        result = await _score_symbol(
            mock_client, "TINY", {"regularMarketPrice": 50.0}, dummy_score, semaphore
        )
        assert result is None, "Short history (<20) should return None"

    @pytest.mark.asyncio
    async def test_score_symbol_empty_history_returns_none(self) -> None:
        """_score_symbol returns None when get_history returns empty list."""
        from zaza.tools.screener.screener import _score_symbol

        mock_client = MagicMock()
        mock_client.get_history.return_value = []
        semaphore = asyncio.Semaphore(1)

        def dummy_score(df: Any, quote: Any) -> dict[str, Any]:
            return {"score": 50, "signals": []}

        result = await _score_symbol(
            mock_client, "EMPTY", {}, dummy_score, semaphore
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_score_symbol_exception_returns_none(self) -> None:
        """_score_symbol returns None when an indicator computation raises."""
        from zaza.tools.screener.screener import _score_symbol

        mock_client = MagicMock()
        mock_client.get_history.return_value = _make_history_records(100)
        semaphore = asyncio.Semaphore(1)

        def raising_score(df: Any, quote: Any) -> dict[str, Any]:
            raise ValueError("indicator computation failed")

        result = await _score_symbol(
            mock_client, "ERR", {"regularMarketPrice": 100.0}, raising_score, semaphore
        )
        assert result is None, "Exception in score_fn should be caught, returning None"

    @pytest.mark.asyncio
    async def test_score_symbol_valid_returns_result(self) -> None:
        """_score_symbol returns scored dict for valid data."""
        from zaza.tools.screener.screener import _score_symbol

        mock_client = MagicMock()
        mock_client.get_history.return_value = _make_history_records(100)
        semaphore = asyncio.Semaphore(1)

        def dummy_score(df: Any, quote: Any) -> dict[str, Any]:
            return {"score": 75, "signals": ["test_signal"]}

        quote = {
            "regularMarketPrice": 150.0,
            "regularMarketChangePercent": 2.0,
            "averageDailyVolume3Month": 1_000_000,
        }
        result = await _score_symbol(
            mock_client, "GOOD", quote, dummy_score, semaphore,
        )
        assert result is not None
        assert result["symbol"] == "GOOD"
        assert result["score"] == 75
        assert result["signals"] == ["test_signal"]


class TestBuySellLevelsEdgeCases:
    """Tests for get_buy_sell_levels edge cases."""

    @pytest.mark.asyncio
    async def test_insufficient_history_returns_error(self) -> None:
        """get_buy_sell_levels returns error when df has fewer than 5 rows."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        # Only 3 records -- below the len(df) < 5 threshold
        short_records = _make_history_records(3)

        with (
            patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
            patch("zaza.tools.screener.screener.FileCache") as MockCache,
        ):
            mock_client = MagicMock()
            mock_client.get_history.return_value = short_records
            MockYFClient.return_value = mock_client
            mock_cache = MagicMock()
            MockCache.return_value = mock_cache

            mcp = FastMCP("test")
            register(mcp)

            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            result_str = await tool.run(arguments={"ticker": "SHORT"})
            result = json.loads(result_str)

        assert "error" in result
        assert "Insufficient" in result["error"]


# ---------------------------------------------------------------------------
# HR-3: Fix conditional assert in test_buy_below_sell
# ---------------------------------------------------------------------------

class TestBuySellLevelsFixed:
    """Fixed version of buy/sell zone tests without conditional asserts."""

    @pytest.mark.asyncio
    async def test_buy_zone_below_sell_zone_no_conditional(self) -> None:
        """Buy zone upper must be <= sell zone lower, without conditional assert."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        history_records = _make_history_records(100)

        with (
            patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
            patch("zaza.tools.screener.screener.FileCache") as MockCache,
        ):
            mock_client = MagicMock()
            mock_client.get_history.return_value = history_records
            MockYFClient.return_value = mock_client
            mock_cache = MagicMock()
            MockCache.return_value = mock_cache

            mcp = FastMCP("test")
            register(mcp)

            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            result_str = await tool.run(arguments={"ticker": "AAPL"})
            result = json.loads(result_str)

        # Assert no error -- do not conditionally skip
        assert "error" not in result, f"Unexpected error: {result.get('error')}"

        buy_max = result["buy_zone"]["upper"]
        sell_min = result["sell_zone"]["lower"]
        assert buy_max <= sell_min, (
            f"Buy zone upper ({buy_max}) should be <= sell zone lower ({sell_min})"
        )


# ---------------------------------------------------------------------------
# MR-4: Buy/sell zone midpoint adjustment must not invert zones
# ---------------------------------------------------------------------------

class TestBuySellZoneInversionProtection:
    """Tests that buy/sell zone boundaries remain valid after midpoint adjustment."""

    @pytest.mark.asyncio
    async def test_buy_zone_lower_not_above_upper(self) -> None:
        """Buy zone lower must be <= buy zone upper after all adjustments."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        history_records = _make_history_records(100)

        with (
            patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
            patch("zaza.tools.screener.screener.FileCache") as MockCache,
        ):
            mock_client = MagicMock()
            mock_client.get_history.return_value = history_records
            MockYFClient.return_value = mock_client
            mock_cache = MagicMock()
            MockCache.return_value = mock_cache

            mcp = FastMCP("test")
            register(mcp)

            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            result_str = await tool.run(arguments={"ticker": "AAPL"})
            result = json.loads(result_str)

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        buy = result["buy_zone"]
        assert buy["lower"] <= buy["upper"], (
            f"Buy zone inverted: lower={buy['lower']} > upper={buy['upper']}"
        )

    @pytest.mark.asyncio
    async def test_sell_zone_lower_not_above_upper(self) -> None:
        """Sell zone lower must be <= sell zone upper after all adjustments."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.screener import register

        history_records = _make_history_records(100)

        with (
            patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
            patch("zaza.tools.screener.screener.FileCache") as MockCache,
        ):
            mock_client = MagicMock()
            mock_client.get_history.return_value = history_records
            MockYFClient.return_value = mock_client
            mock_cache = MagicMock()
            MockCache.return_value = mock_cache

            mcp = FastMCP("test")
            register(mcp)

            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            result_str = await tool.run(arguments={"ticker": "AAPL"})
            result = json.loads(result_str)

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        sell = result["sell_zone"]
        assert sell["lower"] <= sell["upper"], (
            f"Sell zone inverted: lower={sell['lower']} > upper={sell['upper']}"
        )


# ---------------------------------------------------------------------------
# LR-3: OBV logic in _score_volume and _score_bullish
# ---------------------------------------------------------------------------

class TestOBVScoringLogic:
    """Tests verifying OBV trend scoring awards points for correct direction."""

    def test_volume_scan_awards_points_for_rising_obv(self) -> None:
        """_score_volume must award OBV points when obv_trend is 'rising', not 'falling'."""
        from zaza.tools.screener.scan_types import SCAN_TYPES

        # Build a strongly rising price/volume DataFrame so OBV trend = rising
        n = 100
        close = np.linspace(80, 150, n)
        high = close + 1.0
        low = close - 0.5
        open_ = close - 0.3
        volume = np.full(n, 5_000_000.0)
        df = pd.DataFrame({
            "Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume,
        })
        quote: dict[str, Any] = {"averageDailyVolume3Month": 5_000_000}

        config = SCAN_TYPES["volume"]
        result = config.score_candidate(df, quote)

        # With a strongly rising OBV and uniform volume (vol_ratio ~1),
        # the OBV component should contribute its full 30 points
        assert "obv_rising" in result["signals"], (
            f"Volume scan should signal 'obv_rising' for uptrending data. "
            f"Got signals: {result['signals']}"
        )

    def test_volume_scan_does_not_award_full_obv_for_falling(self) -> None:
        """_score_volume should NOT give full OBV points for falling OBV trend."""
        from zaza.tools.screener.scan_types import SCAN_TYPES

        # Build a falling price DataFrame so OBV trend = falling
        n = 100
        close = np.linspace(150, 80, n)
        high = close + 1.0
        low = close - 0.5
        open_ = close + 0.3
        volume = np.full(n, 5_000_000.0)
        df = pd.DataFrame({
            "Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume,
        })
        quote: dict[str, Any] = {"averageDailyVolume3Month": 5_000_000}

        config = SCAN_TYPES["volume"]
        result = config.score_candidate(df, quote)

        # Should NOT have obv_rising signal for falling data
        assert "obv_rising" not in result["signals"], (
            f"Volume scan should NOT signal 'obv_rising' for downtrending data. "
            f"Got signals: {result['signals']}"
        )

    def test_bullish_scan_awards_points_for_rising_obv(self) -> None:
        """_score_bullish must award OBV points when obv_trend is 'rising'."""
        from zaza.tools.screener.scan_types import SCAN_TYPES

        n = 100
        close = np.linspace(80, 150, n)
        high = close + 1.0
        low = close - 0.5
        open_ = close - 0.3
        volume = np.full(n, 5_000_000.0)
        df = pd.DataFrame({
            "Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume,
        })
        quote: dict[str, Any] = {"averageDailyVolume3Month": 5_000_000}

        config = SCAN_TYPES["bullish"]
        result = config.score_candidate(df, quote)

        assert "obv_rising" in result["signals"], (
            f"Bullish scan should signal 'obv_rising' for uptrending data. "
            f"Got signals: {result['signals']}"
        )

    def test_bullish_scan_does_not_award_full_obv_for_falling(self) -> None:
        """_score_bullish should NOT give full OBV points for falling OBV."""
        from zaza.tools.screener.scan_types import SCAN_TYPES

        n = 100
        close = np.linspace(150, 80, n)
        high = close + 1.0
        low = close - 0.5
        open_ = close + 0.3
        volume = np.full(n, 5_000_000.0)
        df = pd.DataFrame({
            "Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume,
        })
        quote: dict[str, Any] = {"averageDailyVolume3Month": 5_000_000}

        config = SCAN_TYPES["bullish"]
        result = config.score_candidate(df, quote)

        assert "obv_rising" not in result["signals"], (
            f"Bullish scan should NOT signal 'obv_rising' for downtrending data. "
            f"Got signals: {result['signals']}"
        )


# ---------------------------------------------------------------------------
# HR-2: Tests must not write to real ~/.zaza/cache/
# ---------------------------------------------------------------------------

class TestFileCacheMocking:
    """Verify that tests using register() do not write to real disk cache."""

    @pytest.mark.asyncio
    async def test_register_with_mocked_cache_does_not_touch_disk(self) -> None:
        """register() must use the mocked FileCache, not create real cache files."""
        from mcp.server.fastmcp import FastMCP

        with (
            patch("zaza.tools.screener.screener.FileCache") as MockCache,
            patch("zaza.tools.screener.screener.YFinanceClient") as MockYFClient,
        ):
            mock_cache = MagicMock()
            MockCache.return_value = mock_cache
            mock_client = MagicMock()
            MockYFClient.return_value = mock_client

            mcp = FastMCP("test")
            from zaza.tools.screener.screener import register
            register(mcp)

        # FileCache was called exactly once (in register)
        MockCache.assert_called_once()


# ---------------------------------------------------------------------------
# Additional scoring branch coverage (HR-1)
# ---------------------------------------------------------------------------

class TestScoringBranchCoverage:
    """Additional tests for scoring function branch coverage."""

    def test_consolidation_scoring(self) -> None:
        """Consolidation scoring returns valid score."""
        from zaza.tools.screener.scan_types import SCAN_TYPES

        df = _make_ohlcv_df()
        quote: dict[str, Any] = {"regularMarketChangePercent": 0.1}
        config = SCAN_TYPES["consolidation"]
        result = config.score_candidate(df, quote)
        assert 0 <= result["score"] <= 100
        assert isinstance(result["signals"], list)

    def test_reversal_scoring(self) -> None:
        """Reversal scoring returns valid score."""
        from zaza.tools.screener.scan_types import SCAN_TYPES

        df = _make_ohlcv_df()
        quote: dict[str, Any] = {"regularMarketChangePercent": -5.0}
        config = SCAN_TYPES["reversal"]
        result = config.score_candidate(df, quote)
        assert 0 <= result["score"] <= 100
        assert isinstance(result["signals"], list)

    def test_ipo_scoring(self) -> None:
        """IPO scoring returns valid score."""
        from zaza.tools.screener.scan_types import SCAN_TYPES

        df = _make_ohlcv_df(25)  # Short history for IPO
        quote: dict[str, Any] = {"regularMarketChangePercent": 3.0}
        config = SCAN_TYPES["ipo"]
        result = config.score_candidate(df, quote)
        assert 0 <= result["score"] <= 100
        assert isinstance(result["signals"], list)
        # Short IPO history should produce the "very_recent_ipo" signal
        assert "very_recent_ipo" in result["signals"]

    def test_short_squeeze_scoring(self) -> None:
        """Short squeeze scoring returns valid score with high short %."""
        from zaza.tools.screener.scan_types import SCAN_TYPES

        df = _make_ohlcv_df()
        quote: dict[str, Any] = {
            "short_percentage_of_shares_outstanding": {"value": 35.0},
        }
        config = SCAN_TYPES["short_squeeze"]
        result = config.score_candidate(df, quote)
        assert 0 <= result["score"] <= 100
        assert isinstance(result["signals"], list)

    def test_bearish_scoring(self) -> None:
        """Bearish scoring returns valid score."""
        from zaza.tools.screener.scan_types import SCAN_TYPES

        df = _make_ohlcv_df()
        quote: dict[str, Any] = {"regularMarketChangePercent": -3.0}
        config = SCAN_TYPES["bearish"]
        result = config.score_candidate(df, quote)
        assert 0 <= result["score"] <= 100
        assert isinstance(result["signals"], list)

    def test_volume_scoring(self) -> None:
        """Volume scoring returns valid score."""
        from zaza.tools.screener.scan_types import SCAN_TYPES

        df = _make_ohlcv_df()
        quote: dict[str, Any] = {"averageDailyVolume3Month": 5_000_000}
        config = SCAN_TYPES["volume"]
        result = config.score_candidate(df, quote)
        assert 0 <= result["score"] <= 100
        assert isinstance(result["signals"], list)

    def test_bullish_scoring(self) -> None:
        """Bullish scoring returns valid score."""
        from zaza.tools.screener.scan_types import SCAN_TYPES

        df = _make_ohlcv_df()
        quote: dict[str, Any] = {"regularMarketChangePercent": 3.0}
        config = SCAN_TYPES["bullish"]
        result = config.score_candidate(df, quote)
        assert 0 <= result["score"] <= 100
        assert isinstance(result["signals"], list)
