"""Tests for the save_prediction MCP tool.

Tests prediction saving with atomic writes, input validation,
auto-populated derived fields, and edge cases.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import orjson
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prediction_json(
    current_price: float = 185.50,
    *,
    extra: dict | None = None,
) -> str:
    """Build a prediction_data JSON string with all required keys."""
    data: dict = {
        "current_price": current_price,
        "predicted_range": {"low": 180.0, "mid": 187.0, "high": 194.0},
        "confidence_interval": {
            "ci_5": 178.0,
            "ci_25": 183.0,
            "ci_75": 191.0,
            "ci_95": 196.0,
        },
        "model_weights": {"momentum": 0.3, "mean_reversion": 0.2, "volatility": 0.5},
        "key_factors": ["RSI oversold bounce", "Earnings beat"],
    }
    if extra:
        data.update(extra)
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Test: save_prediction tool
# ---------------------------------------------------------------------------


class TestSavePrediction:
    """Tests for the save_prediction MCP tool."""

    @pytest.fixture(autouse=True)
    def _patch_predictions_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Patch PREDICTIONS_DIR to use tmp_path for all tests."""
        monkeypatch.setattr(
            "zaza.tools.backtesting.save_prediction.PREDICTIONS_DIR", tmp_path
        )
        self._tmp_path = tmp_path

    def _get_tool_fn(self):
        """Register save_prediction and return the tool function."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.save_prediction import register

        mcp = FastMCP("test")
        register(mcp)
        return mcp._tool_manager._tools["save_prediction"].fn

    async def test_saves_prediction_file(self) -> None:
        """Happy path: valid inputs produce a JSON file with status ok."""
        tool_fn = self._get_tool_fn()
        today = date.today().isoformat()
        horizon = 5

        result = await tool_fn(
            ticker="AAPL",
            horizon_days=horizon,
            prediction_data=_make_prediction_json(),
        )
        parsed = json.loads(result)

        assert parsed["status"] == "ok"

        expected_filename = f"AAPL_{today}_{horizon}d.json"
        assert parsed["file"] == expected_filename

        # Verify file exists and content is valid JSON
        file_path = self._tmp_path / expected_filename
        assert file_path.exists()

        written = orjson.loads(file_path.read_bytes())
        assert written["ticker"] == "AAPL"
        assert written["current_price"] == 185.50
        assert written["predicted_range"]["mid"] == 187.0

    async def test_auto_populates_derived_fields(self) -> None:
        """Derived fields are set: ticker uppercased, dates computed, scored=False."""
        tool_fn = self._get_tool_fn()
        today = date.today()
        horizon = 7

        result = await tool_fn(
            ticker="msft",
            horizon_days=horizon,
            prediction_data=_make_prediction_json(),
        )
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

        file_path = Path(parsed["path"])
        written = orjson.loads(file_path.read_bytes())

        assert written["ticker"] == "MSFT"
        assert written["prediction_date"] == today.isoformat()
        assert written["target_date"] == (today + timedelta(days=horizon)).isoformat()
        assert written["horizon_days"] == horizon
        assert written["scored"] is False
        assert written["actual_price"] is None

    async def test_preserves_extra_fields(self) -> None:
        """Extra fields in prediction_data appear in the written file."""
        tool_fn = self._get_tool_fn()
        extra = {
            "trade_setup": "long breakout",
            "conviction": "high",
            "notes": "Earnings catalyst next week",
        }

        result = await tool_fn(
            ticker="GOOG",
            horizon_days=10,
            prediction_data=_make_prediction_json(extra=extra),
        )
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

        file_path = Path(parsed["path"])
        written = orjson.loads(file_path.read_bytes())

        assert written["trade_setup"] == "long breakout"
        assert written["conviction"] == "high"
        assert written["notes"] == "Earnings catalyst next week"

    @pytest.mark.parametrize(
        "bad_ticker",
        [
            "AAPL123",
            "../etc/passwd",
            "A" * 11,
            "aa bb",
            "AAPL!",
            "",
        ],
    )
    async def test_rejects_invalid_ticker(self, bad_ticker: str) -> None:
        """Invalid ticker formats return status=error and no file is written."""
        tool_fn = self._get_tool_fn()
        result = await tool_fn(
            ticker=bad_ticker,
            horizon_days=5,
            prediction_data=_make_prediction_json(),
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "Invalid ticker format" in parsed["error"]
        assert list(self._tmp_path.iterdir()) == []

    async def test_rejects_missing_required_keys(self) -> None:
        """prediction_data missing required keys returns error listing them."""
        tool_fn = self._get_tool_fn()
        # Missing current_price and key_factors
        incomplete_data = json.dumps(
            {
                "predicted_range": {"low": 180.0, "mid": 187.0, "high": 194.0},
                "confidence_interval": {"ci_5": 178.0},
                "model_weights": {"momentum": 0.3},
            }
        )

        result = await tool_fn(
            ticker="AAPL",
            horizon_days=5,
            prediction_data=incomplete_data,
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "current_price" in parsed["error"]
        assert "key_factors" in parsed["error"]

    async def test_rejects_invalid_json(self) -> None:
        """Non-JSON prediction_data returns error with specific message."""
        tool_fn = self._get_tool_fn()
        result = await tool_fn(
            ticker="AAPL",
            horizon_days=5,
            prediction_data="not valid json {{{",
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "Invalid JSON" in parsed["error"]

    async def test_rejects_non_dict_json(self) -> None:
        """prediction_data that parses to non-dict (e.g. array) returns error."""
        tool_fn = self._get_tool_fn()
        result = await tool_fn(
            ticker="AAPL",
            horizon_days=5,
            prediction_data="[1,2,3]",
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "JSON object" in parsed["error"]

    async def test_rejects_zero_horizon_days(self) -> None:
        """horizon_days=0 returns error."""
        tool_fn = self._get_tool_fn()
        result = await tool_fn(
            ticker="AAPL",
            horizon_days=0,
            prediction_data=_make_prediction_json(),
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "horizon_days must be between 1 and 365" in parsed["error"]

    async def test_rejects_negative_horizon_days(self) -> None:
        """horizon_days=-5 returns error."""
        tool_fn = self._get_tool_fn()
        result = await tool_fn(
            ticker="AAPL",
            horizon_days=-5,
            prediction_data=_make_prediction_json(),
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "horizon_days must be between 1 and 365" in parsed["error"]

    async def test_rejects_excessive_horizon_days(self) -> None:
        """horizon_days=500 returns error."""
        tool_fn = self._get_tool_fn()
        result = await tool_fn(
            ticker="AAPL",
            horizon_days=500,
            prediction_data=_make_prediction_json(),
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "horizon_days must be between 1 and 365" in parsed["error"]

    async def test_derived_fields_override_caller_values(self) -> None:
        """Derived fields (ticker, scored, actual_price) override caller-supplied values."""
        tool_fn = self._get_tool_fn()
        extra = {
            "ticker": "WRONG",
            "scored": True,
            "actual_price": 999.0,
        }

        result = await tool_fn(
            ticker="AAPL",
            horizon_days=5,
            prediction_data=_make_prediction_json(extra=extra),
        )
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

        file_path = Path(parsed["path"])
        written = orjson.loads(file_path.read_bytes())

        assert written["ticker"] == "AAPL"
        assert written["scored"] is False
        assert written["actual_price"] is None

    async def test_overwrites_existing_prediction(self) -> None:
        """Second save with same ticker/date/horizon overwrites the first."""
        tool_fn = self._get_tool_fn()

        # First save
        await tool_fn(
            ticker="AAPL",
            horizon_days=5,
            prediction_data=_make_prediction_json(current_price=180.0),
        )
        # Second save (different price)
        result = await tool_fn(
            ticker="AAPL",
            horizon_days=5,
            prediction_data=_make_prediction_json(current_price=195.0),
        )
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

        file_path = Path(parsed["path"])
        written = orjson.loads(file_path.read_bytes())
        assert written["current_price"] == 195.0

    async def test_creates_predictions_dir_if_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auto-creates the predictions directory if it doesn't exist."""
        nested_dir = self._tmp_path / "deep" / "nested" / "predictions"
        monkeypatch.setattr(
            "zaza.tools.backtesting.save_prediction.PREDICTIONS_DIR", nested_dir
        )

        tool_fn = self._get_tool_fn()
        result = await tool_fn(
            ticker="TSLA",
            horizon_days=3,
            prediction_data=_make_prediction_json(),
        )
        parsed = json.loads(result)

        assert parsed["status"] == "ok"
        assert nested_dir.exists()
        assert (nested_dir / parsed["file"]).exists()
