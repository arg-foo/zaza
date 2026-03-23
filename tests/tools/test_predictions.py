"""Tests for the get_prediction MCP tool.

Tests prediction retrieval by ticker and date, error cases,
and inclusion of extended fields in responses.
"""

from __future__ import annotations

import json
from pathlib import Path

import orjson
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prediction_data(
    ticker: str = "AAPL",
    prediction_date: str = "2026-03-20",
    horizon_days: int = 5,
    current_price: float = 185.50,
    *,
    include_extended: bool = False,
) -> dict:
    """Build a prediction data dict for writing to disk."""
    data = {
        "ticker": ticker,
        "prediction_date": prediction_date,
        "horizon_days": horizon_days,
        "target_date": "2026-03-25",
        "current_price": current_price,
        "predicted_range": {"low": 180.0, "mid": 187.0, "high": 194.0},
        "confidence_interval": {"ci_5": 178.0, "ci_25": 183.0, "ci_75": 191.0, "ci_95": 196.0},
        "model_weights": {"momentum": 0.3, "mean_reversion": 0.2, "volatility": 0.5},
        "key_factors": ["RSI oversold bounce", "Earnings beat"],
        "actual_price": None,
        "scored": False,
    }
    if include_extended:
        data.update({
            "catalyst_calendar": [
                {"date": "2026-03-22", "event": "Earnings report"},
            ],
            "scenario_conditions": {
                "bull_requires": "Breaks above $190",
                "bear_triggered_by": "Fails $183 support",
            },
            "short_interest": {"short_ratio": 3.2},
            "buyback_support": {"active": True},
            "weighting_mode": "catalyst_adjusted",
        })
    return data


def _write_prediction(tmp_path: Path, data: dict) -> Path:
    """Write a prediction JSON file to tmp_path and return the file path."""
    ticker = data["ticker"]
    pred_date = data["prediction_date"]
    horizon = data["horizon_days"]
    filename = f"{ticker}_{pred_date}_{horizon}d.json"
    file_path = tmp_path / filename
    file_path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
    return file_path


# ---------------------------------------------------------------------------
# Test: get_prediction tool
# ---------------------------------------------------------------------------


class TestGetPrediction:
    """Tests for the get_prediction MCP tool."""

    @pytest.fixture(autouse=True)
    def _patch_predictions_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Patch PREDICTIONS_DIR to use tmp_path for all tests."""
        monkeypatch.setattr(
            "zaza.tools.backtesting.predictions.PREDICTIONS_DIR", tmp_path
        )
        self._tmp_path = tmp_path

    async def test_returns_most_recent_when_no_date(self) -> None:
        """get_prediction returns the most recent prediction when no date specified."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.predictions import register

        mcp = FastMCP("test")
        register(mcp)

        # Write two predictions with different dates
        old_data = _make_prediction_data(prediction_date="2026-03-18")
        new_data = _make_prediction_data(prediction_date="2026-03-20")
        _write_prediction(self._tmp_path, old_data)
        _write_prediction(self._tmp_path, new_data)

        # Call the tool function directly
        tool_fn = mcp._tool_manager._tools["get_prediction"].fn
        result = await tool_fn(ticker="AAPL")
        parsed = json.loads(result)

        assert parsed["status"] == "ok"
        assert parsed["data"]["prediction_date"] == "2026-03-20"

    async def test_returns_specific_date_prediction(self) -> None:
        """get_prediction with prediction_date returns that specific prediction."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.predictions import register

        mcp = FastMCP("test")
        register(mcp)

        data_1 = _make_prediction_data(prediction_date="2026-03-18", current_price=182.0)
        data_2 = _make_prediction_data(prediction_date="2026-03-20", current_price=185.5)
        _write_prediction(self._tmp_path, data_1)
        _write_prediction(self._tmp_path, data_2)

        tool_fn = mcp._tool_manager._tools["get_prediction"].fn
        result = await tool_fn(ticker="AAPL", prediction_date="2026-03-18")
        parsed = json.loads(result)

        assert parsed["status"] == "ok"
        assert parsed["data"]["prediction_date"] == "2026-03-18"
        assert parsed["data"]["current_price"] == 182.0

    async def test_returns_error_when_no_predictions_exist(self) -> None:
        """get_prediction returns error when no predictions found for ticker."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.predictions import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["get_prediction"].fn
        result = await tool_fn(ticker="AAPL")
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "No predictions found" in parsed["error"]

    async def test_returns_error_when_date_not_found(self) -> None:
        """get_prediction returns error when specific date doesn't match."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.predictions import register

        mcp = FastMCP("test")
        register(mcp)

        data = _make_prediction_data(prediction_date="2026-03-20")
        _write_prediction(self._tmp_path, data)

        tool_fn = mcp._tool_manager._tools["get_prediction"].fn
        result = await tool_fn(ticker="AAPL", prediction_date="2026-03-15")
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "No prediction found" in parsed["error"]
        assert "2026-03-15" in parsed["error"]

    async def test_extended_fields_included_in_response(self) -> None:
        """get_prediction response includes extended fields when present."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.predictions import register

        mcp = FastMCP("test")
        register(mcp)

        data = _make_prediction_data(include_extended=True)
        _write_prediction(self._tmp_path, data)

        tool_fn = mcp._tool_manager._tools["get_prediction"].fn
        result = await tool_fn(ticker="AAPL")
        parsed = json.loads(result)

        assert parsed["status"] == "ok"
        pred = parsed["data"]
        assert pred["catalyst_calendar"] is not None
        assert len(pred["catalyst_calendar"]) == 1
        assert pred["scenario_conditions"]["bull_requires"] == "Breaks above $190"
        assert pred["short_interest"]["short_ratio"] == 3.2
        assert pred["buyback_support"]["active"] is True
        assert pred["weighting_mode"] == "catalyst_adjusted"

    @pytest.mark.parametrize("bad_ticker", [
        "AAPL123",       # digits not allowed
        "../etc/passwd", # path traversal
        "A" * 11,        # too long
        "aa bb",         # spaces
        "AAPL!",         # special chars
        "",              # empty string
    ])
    async def test_rejects_invalid_ticker_format(self, bad_ticker: str) -> None:
        """get_prediction returns error for invalid ticker formats."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.predictions import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["get_prediction"].fn
        result = await tool_fn(ticker=bad_ticker)
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "Invalid ticker format" in parsed["error"]

    async def test_accepts_valid_lowercase_ticker(self) -> None:
        """get_prediction normalizes lowercase tickers to uppercase."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.predictions import register

        mcp = FastMCP("test")
        register(mcp)

        data = _make_prediction_data(ticker="AAPL")
        _write_prediction(self._tmp_path, data)

        tool_fn = mcp._tool_manager._tools["get_prediction"].fn
        result = await tool_fn(ticker="aapl")
        parsed = json.loads(result)

        assert parsed["status"] == "ok"
        assert parsed["data"]["ticker"] == "AAPL"
