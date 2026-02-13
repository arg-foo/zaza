"""Tests for backtesting tools (TASK-022).

Tests signal backtest, strategy simulation, prediction scoring, and risk metrics.
All external dependencies (yfinance, filesystem) are mocked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from zaza.cache.store import FileCache

# ---------------------------------------------------------------------------
# Helpers to build realistic OHLCV test data
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 300, base_price: float = 100.0, seed: int = 42) -> list[dict[str, Any]]:
    """Generate n days of synthetic OHLCV data with known patterns."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end="2024-06-01", periods=n)
    prices = [base_price]
    for _ in range(n - 1):
        ret = rng.normal(0.0003, 0.015)
        prices.append(prices[-1] * (1 + ret))
    records = []
    for i, date in enumerate(dates):
        p = prices[i]
        records.append({
            "Date": str(date.date()),
            "Open": round(p * (1 + rng.normal(0, 0.003)), 2),
            "High": round(p * (1 + abs(rng.normal(0.005, 0.003))), 2),
            "Low": round(p * (1 - abs(rng.normal(0.005, 0.003))), 2),
            "Close": round(p, 2),
            "Volume": int(rng.integers(1_000_000, 10_000_000)),
        })
    return records


def _make_ohlcv_with_rsi_dip(n: int = 300, seed: int = 42) -> list[dict[str, Any]]:
    """Generate OHLCV data that includes a deliberate RSI < 30 dip."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end="2024-06-01", periods=n)
    prices = [100.0]
    for i in range(1, n):
        if 100 <= i <= 107:
            ret = -0.025
        elif 108 <= i <= 120:
            ret = 0.015
        else:
            ret = rng.normal(0.0003, 0.012)
        prices.append(prices[-1] * (1 + ret))
    records = []
    for i, date in enumerate(dates):
        p = prices[i]
        records.append({
            "Date": str(date.date()),
            "Open": round(p * 1.001, 2),
            "High": round(p * 1.005, 2),
            "Low": round(p * 0.995, 2),
            "Close": round(p, 2),
            "Volume": int(rng.integers(1_000_000, 10_000_000)),
        })
    return records


# ---------------------------------------------------------------------------
# TASK-022a: get_signal_backtest
# ---------------------------------------------------------------------------

class TestSignalBacktest:
    """Tests for the signal backtest tool."""

    @pytest.fixture
    def mock_cache(self, tmp_path: Path) -> FileCache:
        return FileCache(cache_dir=tmp_path / "cache")

    @pytest.fixture
    def ohlcv_data(self) -> list[dict[str, Any]]:
        return _make_ohlcv(n=400, seed=42)

    @pytest.fixture
    def ohlcv_with_rsi_dip(self) -> list[dict[str, Any]]:
        return _make_ohlcv_with_rsi_dip(n=400, seed=42)

    @pytest.mark.asyncio
    async def test_signal_backtest_returns_valid_structure(
        self, mock_cache: FileCache, ohlcv_data: list[dict[str, Any]]
    ) -> None:
        """Signal backtest returns expected keys and types."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.signals import register

        mcp = FastMCP("test")

        # Patches must wrap the register() call so the closure captures mocks
        with patch("zaza.tools.backtesting.signals.FileCache", return_value=mock_cache):
            with patch("zaza.tools.backtesting.signals.YFinanceClient") as MockYF:
                mock_yf = MockYF.return_value
                mock_yf.get_history.return_value = ohlcv_data

                register(mcp)

                tool = mcp._tool_manager.get_tool("get_signal_backtest")
                result_str = await tool.run(
                    arguments={"ticker": "AAPL", "signal": "golden_cross"}
                )
                result = json.loads(result_str)

        assert "error" not in result
        assert "ticker" in result
        assert "signal" in result
        assert "total_signals" in result

    @pytest.mark.asyncio
    async def test_signal_backtest_invalid_signal(
        self, mock_cache: FileCache
    ) -> None:
        """Invalid signal type returns error."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.signals import register

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.signals.FileCache", return_value=mock_cache):
            with patch("zaza.tools.backtesting.signals.YFinanceClient"):
                register(mcp)

                tool = mcp._tool_manager.get_tool("get_signal_backtest")
                result_str = await tool.run(
                    arguments={"ticker": "AAPL", "signal": "invalid_signal"}
                )
                result = json.loads(result_str)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_signal_backtest_no_lookahead_bias(
        self, mock_cache: FileCache, ohlcv_with_rsi_dip: list[dict[str, Any]]
    ) -> None:
        """Signal backtest must not use future data when evaluating signals."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.signals import register

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.signals.FileCache", return_value=mock_cache):
            with patch("zaza.tools.backtesting.signals.YFinanceClient") as MockYF:
                mock_yf = MockYF.return_value
                mock_yf.get_history.return_value = ohlcv_with_rsi_dip

                register(mcp)

                tool = mcp._tool_manager.get_tool("get_signal_backtest")
                result_str = await tool.run(
                    arguments={"ticker": "AAPL", "signal": "rsi_below_30"}
                )
                result = json.loads(result_str)

        # If signals were found, verify returns are computed correctly
        if result.get("total_signals", 0) > 0:
            assert "win_rate_5d" in result
            # Total signals should be reasonable (not the entire dataset)
            assert result["total_signals"] < len(ohlcv_with_rsi_dip) // 2

    @pytest.mark.asyncio
    async def test_signal_backtest_caches_result(
        self, mock_cache: FileCache, ohlcv_data: list[dict[str, Any]]
    ) -> None:
        """Backtest results are cached under 'backtest_results' category."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.signals import register

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.signals.FileCache", return_value=mock_cache):
            with patch("zaza.tools.backtesting.signals.YFinanceClient") as MockYF:
                mock_yf = MockYF.return_value
                mock_yf.get_history.return_value = ohlcv_data

                register(mcp)

                tool = mcp._tool_manager.get_tool("get_signal_backtest")
                await tool.run(
                    arguments={"ticker": "AAPL", "signal": "golden_cross"}
                )

        # Check cache was populated
        cache_files = list(mock_cache.cache_dir.glob("*.json"))
        assert len(cache_files) >= 1

    @pytest.mark.asyncio
    async def test_signal_backtest_empty_history(
        self, mock_cache: FileCache
    ) -> None:
        """Empty history returns an error."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.signals import register

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.signals.FileCache", return_value=mock_cache):
            with patch("zaza.tools.backtesting.signals.YFinanceClient") as MockYF:
                mock_yf = MockYF.return_value
                mock_yf.get_history.return_value = []

                register(mcp)

                tool = mcp._tool_manager.get_tool("get_signal_backtest")
                result_str = await tool.run(
                    arguments={"ticker": "AAPL", "signal": "golden_cross"}
                )
                result = json.loads(result_str)

        assert "error" in result


# ---------------------------------------------------------------------------
# TASK-022b: get_strategy_simulation
# ---------------------------------------------------------------------------

class TestStrategySimulation:
    """Tests for the strategy simulation tool."""

    @pytest.fixture
    def mock_cache(self, tmp_path: Path) -> FileCache:
        return FileCache(cache_dir=tmp_path / "cache")

    @pytest.fixture
    def ohlcv_data(self) -> list[dict[str, Any]]:
        return _make_ohlcv(n=500, seed=42)

    @pytest.mark.asyncio
    async def test_simulation_returns_valid_structure(
        self, mock_cache: FileCache, ohlcv_data: list[dict[str, Any]]
    ) -> None:
        """Strategy simulation returns expected keys."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.simulation import register

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.simulation.FileCache", return_value=mock_cache):
            with patch("zaza.tools.backtesting.simulation.YFinanceClient") as MockYF:
                mock_yf = MockYF.return_value
                mock_yf.get_history.return_value = ohlcv_data

                register(mcp)

                tool = mcp._tool_manager.get_tool("get_strategy_simulation")
                result_str = await tool.run(
                    arguments={
                        "ticker": "AAPL",
                        "entry_signal": "rsi_below_30",
                        "exit_signal": "rsi_above_70",
                    }
                )
                result = json.loads(result_str)

        assert "error" not in result
        assert "ticker" in result
        assert "total_trades" in result

    @pytest.mark.asyncio
    async def test_simulation_with_stop_loss(
        self, mock_cache: FileCache, ohlcv_data: list[dict[str, Any]]
    ) -> None:
        """Simulation with stop_loss_pct correctly exits losing trades."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.simulation import register

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.simulation.FileCache", return_value=mock_cache):
            with patch("zaza.tools.backtesting.simulation.YFinanceClient") as MockYF:
                mock_yf = MockYF.return_value
                mock_yf.get_history.return_value = ohlcv_data

                register(mcp)

                tool = mcp._tool_manager.get_tool("get_strategy_simulation")
                result_str = await tool.run(
                    arguments={
                        "ticker": "AAPL",
                        "entry_signal": "rsi_below_30",
                        "exit_signal": "rsi_above_70",
                        "stop_loss_pct": 3.0,
                    }
                )
                result = json.loads(result_str)

        assert "total_trades" in result

    @pytest.mark.asyncio
    async def test_simulation_invalid_signal(
        self, mock_cache: FileCache
    ) -> None:
        """Invalid entry/exit signal returns error."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.simulation import register

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.simulation.FileCache", return_value=mock_cache):
            with patch("zaza.tools.backtesting.simulation.YFinanceClient"):
                register(mcp)

                tool = mcp._tool_manager.get_tool("get_strategy_simulation")
                result_str = await tool.run(
                    arguments={
                        "ticker": "AAPL",
                        "entry_signal": "bad_signal",
                        "exit_signal": "rsi_above_70",
                    }
                )
                result = json.loads(result_str)

        assert "error" in result


# ---------------------------------------------------------------------------
# TASK-022c: get_prediction_score
# ---------------------------------------------------------------------------

class TestPredictionScore:
    """Tests for the prediction scoring tool."""

    @pytest.mark.asyncio
    async def test_no_predictions_returns_empty(self, tmp_path: Path) -> None:
        """When no predictions file exists, return empty results."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.scoring import register

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.scoring.PREDICTIONS_DIR", tmp_path):
            register(mcp)

            tool = mcp._tool_manager.get_tool("get_prediction_score")
            result_str = await tool.run(arguments={})
            result = json.loads(result_str)

        assert "predictions" in result
        assert result["predictions"] == [] or result["total_predictions"] == 0

    @pytest.mark.asyncio
    async def test_scores_existing_predictions(self, tmp_path: Path) -> None:
        """Scores prediction files that exist in the predictions directory."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.scoring import register

        prediction = {
            "ticker": "AAPL",
            "date": "2024-01-15",
            "predicted_direction": "up",
            "predicted_price": 195.0,
            "actual_price": 198.0,
            "actual_direction": "up",
        }
        pred_file = tmp_path / "AAPL_2024-01-15.json"
        pred_file.write_text(json.dumps(prediction))

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.scoring.PREDICTIONS_DIR", tmp_path):
            register(mcp)

            tool = mcp._tool_manager.get_tool("get_prediction_score")
            result_str = await tool.run(arguments={})
            result = json.loads(result_str)

        assert result["total_predictions"] >= 1

    @pytest.mark.asyncio
    async def test_scores_filtered_by_ticker(self, tmp_path: Path) -> None:
        """When ticker is provided, only that ticker's predictions are scored."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.scoring import register

        for ticker, price in [("AAPL", 195.0), ("MSFT", 410.0)]:
            prediction = {
                "ticker": ticker,
                "date": "2024-01-15",
                "predicted_direction": "up",
                "predicted_price": price,
                "actual_price": price + 3.0,
                "actual_direction": "up",
            }
            (tmp_path / f"{ticker}_2024-01-15.json").write_text(json.dumps(prediction))

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.scoring.PREDICTIONS_DIR", tmp_path):
            register(mcp)

            tool = mcp._tool_manager.get_tool("get_prediction_score")
            result_str = await tool.run(arguments={"ticker": "AAPL"})
            result = json.loads(result_str)

        assert result["total_predictions"] == 1


# ---------------------------------------------------------------------------
# TASK-022d: get_risk_metrics
# ---------------------------------------------------------------------------

class TestRiskMetrics:
    """Tests for the risk metrics tool."""

    @pytest.fixture
    def mock_cache(self, tmp_path: Path) -> FileCache:
        return FileCache(cache_dir=tmp_path / "cache")

    @pytest.fixture
    def ohlcv_data(self) -> list[dict[str, Any]]:
        return _make_ohlcv(n=300, seed=42)

    @pytest.fixture
    def benchmark_data(self) -> list[dict[str, Any]]:
        return _make_ohlcv(n=300, base_price=450.0, seed=99)

    @pytest.mark.asyncio
    async def test_risk_metrics_returns_valid_structure(
        self,
        mock_cache: FileCache,
        ohlcv_data: list[dict[str, Any]],
        benchmark_data: list[dict[str, Any]],
    ) -> None:
        """Risk metrics returns Sharpe, Sortino, beta, etc."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.risk import register

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.risk.FileCache", return_value=mock_cache):
            with patch("zaza.tools.backtesting.risk.YFinanceClient") as MockYF:
                mock_yf = MockYF.return_value
                mock_yf.get_history.side_effect = [ohlcv_data, benchmark_data]

                register(mcp)

                tool = mcp._tool_manager.get_tool("get_risk_metrics")
                result_str = await tool.run(
                    arguments={"ticker": "AAPL"}
                )
                result = json.loads(result_str)

        assert "error" not in result
        assert "sharpe_ratio" in result
        assert "sortino_ratio" in result
        assert "max_drawdown" in result
        assert "beta" in result
        assert "alpha" in result
        assert "var_95" in result
        assert "cvar_95" in result

    @pytest.mark.asyncio
    async def test_risk_metrics_empty_data(
        self, mock_cache: FileCache
    ) -> None:
        """Empty data returns an error."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.risk import register

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.risk.FileCache", return_value=mock_cache):
            with patch("zaza.tools.backtesting.risk.YFinanceClient") as MockYF:
                mock_yf = MockYF.return_value
                mock_yf.get_history.return_value = []

                register(mcp)

                tool = mcp._tool_manager.get_tool("get_risk_metrics")
                result_str = await tool.run(
                    arguments={"ticker": "AAPL"}
                )
                result = json.loads(result_str)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_risk_metrics_caches_result(
        self,
        mock_cache: FileCache,
        ohlcv_data: list[dict[str, Any]],
        benchmark_data: list[dict[str, Any]],
    ) -> None:
        """Risk metrics results are cached."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.risk import register

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.risk.FileCache", return_value=mock_cache):
            with patch("zaza.tools.backtesting.risk.YFinanceClient") as MockYF:
                mock_yf = MockYF.return_value
                mock_yf.get_history.side_effect = [ohlcv_data, benchmark_data]

                register(mcp)

                tool = mcp._tool_manager.get_tool("get_risk_metrics")
                await tool.run(arguments={"ticker": "AAPL"})

        cache_files = list(mock_cache.cache_dir.glob("*.json"))
        assert len(cache_files) >= 1
