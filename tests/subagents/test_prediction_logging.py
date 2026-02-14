"""Tests for prediction logging and self-scoring infrastructure (TASK-036).

Tests cover:
- PredictionLog dataclass schema validation
- log_prediction() creates valid JSON with correct schema and atomic writes
- score_predictions() computes directional accuracy, MAE, MAPE, bias, range_accuracy
- Handles missing/corrupt files gracefully
- Log rotation works correctly
- Atomic write safety (file does not corrupt on failure)

All external dependencies (yfinance, filesystem) are mocked.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import orjson
import pytest

from zaza.utils.predictions import (
    PredictionLog,
    log_prediction,
    rotate_logs,
    score_predictions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prediction(
    ticker: str = "AAPL",
    prediction_date: str = "2025-01-15",
    horizon_days: int = 30,
    current_price: float = 190.0,
    predicted_mid: float = 200.0,
    actual_price: float | None = None,
    scored: bool = False,
) -> PredictionLog:
    """Create a PredictionLog for testing."""
    target = date.fromisoformat(prediction_date) + timedelta(days=horizon_days)
    return PredictionLog(
        ticker=ticker,
        prediction_date=prediction_date,
        horizon_days=horizon_days,
        target_date=target.isoformat(),
        current_price=current_price,
        predicted_range={
            "low": predicted_mid * 0.95,
            "mid": predicted_mid,
            "high": predicted_mid * 1.05,
        },
        confidence_interval={
            "ci_5": predicted_mid * 0.90,
            "ci_25": predicted_mid * 0.95,
            "ci_75": predicted_mid * 1.05,
            "ci_95": predicted_mid * 1.10,
        },
        model_weights={
            "quant": 0.3,
            "technical": 0.25,
            "sentiment": 0.15,
            "macro": 0.15,
            "options": 0.15,
        },
        key_factors=["Strong momentum", "Bullish MACD crossover", "Positive earnings revision"],
        actual_price=actual_price,
        scored=scored,
    )


def _write_prediction_file(
    predictions_dir: Path,
    prediction: PredictionLog,
) -> Path:
    """Write a prediction to disk, returning the file path."""
    filename = f"{prediction.ticker}_{prediction.prediction_date}_{prediction.horizon_days}d.json"
    filepath = predictions_dir / filename
    data = prediction.__dict__.copy()
    filepath.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
    return filepath


# ---------------------------------------------------------------------------
# PredictionLog dataclass tests
# ---------------------------------------------------------------------------


class TestPredictionLogSchema:
    """Verify PredictionLog dataclass has correct fields and defaults."""

    def test_required_fields_present(self) -> None:
        """PredictionLog has all required fields."""
        p = _make_prediction()
        assert p.ticker == "AAPL"
        assert p.prediction_date == "2025-01-15"
        assert p.horizon_days == 30
        assert p.target_date == "2025-02-14"
        assert p.current_price == 190.0
        assert isinstance(p.predicted_range, dict)
        assert isinstance(p.confidence_interval, dict)
        assert isinstance(p.model_weights, dict)
        assert isinstance(p.key_factors, list)

    def test_default_optional_fields(self) -> None:
        """actual_price defaults to None, scored defaults to False."""
        p = _make_prediction()
        assert p.actual_price is None
        assert p.scored is False

    def test_predicted_range_keys(self) -> None:
        """predicted_range has low, mid, high keys."""
        p = _make_prediction()
        assert "low" in p.predicted_range
        assert "mid" in p.predicted_range
        assert "high" in p.predicted_range

    def test_confidence_interval_keys(self) -> None:
        """confidence_interval has ci_5, ci_25, ci_75, ci_95."""
        p = _make_prediction()
        for key in ("ci_5", "ci_25", "ci_75", "ci_95"):
            assert key in p.confidence_interval


# ---------------------------------------------------------------------------
# log_prediction() tests
# ---------------------------------------------------------------------------


class TestLogPrediction:
    """Tests for the log_prediction function."""

    def test_creates_valid_json_file(self, tmp_path: Path) -> None:
        """log_prediction creates a valid JSON file with correct schema."""
        pred = _make_prediction()
        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result_path = log_prediction(pred)

        assert result_path.exists()
        data = orjson.loads(result_path.read_bytes())
        assert data["ticker"] == "AAPL"
        assert data["prediction_date"] == "2025-01-15"
        assert data["horizon_days"] == 30
        assert data["current_price"] == 190.0
        assert data["scored"] is False

    def test_filename_format(self, tmp_path: Path) -> None:
        """File is named {ticker}_{date}_{horizon}d.json."""
        pred = _make_prediction(ticker="MSFT", prediction_date="2025-03-01", horizon_days=14)
        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result_path = log_prediction(pred)

        assert result_path.name == "MSFT_2025-03-01_14d.json"

    def test_returns_path(self, tmp_path: Path) -> None:
        """log_prediction returns the Path of the written file."""
        pred = _make_prediction()
        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result_path = log_prediction(pred)

        assert isinstance(result_path, Path)
        assert result_path.parent == tmp_path

    def test_uses_orjson_indent(self, tmp_path: Path) -> None:
        """Output JSON is human-readable (indented)."""
        pred = _make_prediction()
        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result_path = log_prediction(pred)

        content = result_path.read_text()
        # orjson OPT_INDENT_2 uses 2-space indentation
        assert "\n" in content
        assert "  " in content

    def test_atomic_write_does_not_leave_partial_file(self, tmp_path: Path) -> None:
        """If write fails, the target file should not exist or be partial."""
        pred = _make_prediction()
        filename = f"{pred.ticker}_{pred.prediction_date}_{pred.horizon_days}d.json"
        target = tmp_path / filename

        # Simulate a failure during temp file write by patching tempfile
        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            with patch(
                "zaza.utils.predictions.tempfile.NamedTemporaryFile",
                side_effect=OSError("disk full"),
            ):
                with pytest.raises(OSError):
                    log_prediction(pred)

        # Target file should not exist since write failed
        assert not target.exists()

    def test_creates_predictions_dir_if_missing(self, tmp_path: Path) -> None:
        """log_prediction creates the predictions directory if it does not exist."""
        pred_dir = tmp_path / "predictions_new"
        pred = _make_prediction()
        with patch("zaza.utils.predictions.PREDICTIONS_DIR", pred_dir):
            result_path = log_prediction(pred)

        assert pred_dir.exists()
        assert result_path.exists()

    def test_overwrites_existing_prediction(self, tmp_path: Path) -> None:
        """Writing a prediction with the same key overwrites the old file."""
        pred1 = _make_prediction(predicted_mid=200.0)
        pred2 = _make_prediction(predicted_mid=210.0)
        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            log_prediction(pred1)
            result_path = log_prediction(pred2)

        data = orjson.loads(result_path.read_bytes())
        assert data["predicted_range"]["mid"] == 210.0


# ---------------------------------------------------------------------------
# score_predictions() tests
# ---------------------------------------------------------------------------


class TestScorePredictions:
    """Tests for the score_predictions function."""

    def _mock_yf_price(self, price: float) -> MagicMock:
        """Create a mock YFinanceClient that returns a fixed price."""
        mock = MagicMock()
        mock.get_quote.return_value = {"regularMarketPrice": price}
        return mock

    def test_no_predictions_returns_empty(self, tmp_path: Path) -> None:
        """Empty predictions directory returns empty result."""
        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result = score_predictions()

        assert result["total_predictions"] == 0
        assert result["directional_accuracy"] is None
        assert result["mae"] is None
        assert result["predictions"] == []

    def test_scores_past_target_date(self, tmp_path: Path) -> None:
        """Predictions past target_date get scored with actual price."""
        past_date = (date.today() - timedelta(days=60)).isoformat()
        pred = _make_prediction(
            prediction_date=past_date,
            horizon_days=30,
            current_price=190.0,
            predicted_mid=200.0,
        )
        _write_prediction_file(tmp_path, pred)

        mock_yf = self._mock_yf_price(198.0)
        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            with patch("zaza.utils.predictions.YFinanceClient", return_value=mock_yf):
                with patch("zaza.utils.predictions.FileCache"):
                    result = score_predictions()

        assert result["total_predictions"] == 1
        assert result["predictions"][0]["actual_price"] == 198.0
        assert result["predictions"][0]["scored"] is True

    def test_directional_accuracy_all_correct(self, tmp_path: Path) -> None:
        """100% directional accuracy when all predictions are correct direction."""
        past_date = (date.today() - timedelta(days=60)).isoformat()

        # Both predict up (mid > current_price) and actual is up (actual > current)
        for i, (ticker, current, mid, actual) in enumerate([
            ("AAPL", 190.0, 200.0, 195.0),  # predicted up, actual up
            ("MSFT", 400.0, 420.0, 410.0),   # predicted up, actual up
        ]):
            pred = _make_prediction(
                ticker=ticker,
                prediction_date=past_date,
                horizon_days=30,
                current_price=current,
                predicted_mid=mid,
                actual_price=actual,
                scored=True,
            )
            _write_prediction_file(tmp_path, pred)

        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result = score_predictions()

        assert result["directional_accuracy"] == 1.0

    def test_directional_accuracy_mixed(self, tmp_path: Path) -> None:
        """50% directional accuracy with one correct and one wrong."""
        past_date = (date.today() - timedelta(days=60)).isoformat()

        # Predict up, actual up
        pred1 = _make_prediction(
            ticker="AAPL",
            prediction_date=past_date,
            horizon_days=30,
            current_price=190.0,
            predicted_mid=200.0,
            actual_price=195.0,  # up, correct
            scored=True,
        )
        _write_prediction_file(tmp_path, pred1)

        # Predict up, actual down
        pred2 = _make_prediction(
            ticker="MSFT",
            prediction_date=past_date,
            horizon_days=30,
            current_price=400.0,
            predicted_mid=420.0,
            actual_price=390.0,  # down, wrong
            scored=True,
        )
        _write_prediction_file(tmp_path, pred2)

        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result = score_predictions()

        assert result["directional_accuracy"] == 0.5

    def test_mae_computation(self, tmp_path: Path) -> None:
        """MAE is computed as average absolute error of mid vs actual."""
        past_date = (date.today() - timedelta(days=60)).isoformat()

        # Error: |200 - 198| = 2
        pred1 = _make_prediction(
            ticker="AAPL",
            prediction_date=past_date,
            horizon_days=30,
            current_price=190.0,
            predicted_mid=200.0,
            actual_price=198.0,
            scored=True,
        )
        _write_prediction_file(tmp_path, pred1)

        # Error: |420 - 410| = 10
        pred2 = _make_prediction(
            ticker="MSFT",
            prediction_date=past_date,
            horizon_days=30,
            current_price=400.0,
            predicted_mid=420.0,
            actual_price=410.0,
            scored=True,
        )
        _write_prediction_file(tmp_path, pred2)

        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result = score_predictions()

        # MAE = (2 + 10) / 2 = 6.0
        assert result["mae"] == 6.0

    def test_mape_computation(self, tmp_path: Path) -> None:
        """MAPE is mean absolute percentage error relative to actual price."""
        past_date = (date.today() - timedelta(days=60)).isoformat()

        # MAPE: |200 - 198| / 198 = 2/198 ~ 0.0101
        pred1 = _make_prediction(
            ticker="AAPL",
            prediction_date=past_date,
            horizon_days=30,
            current_price=190.0,
            predicted_mid=200.0,
            actual_price=198.0,
            scored=True,
        )
        _write_prediction_file(tmp_path, pred1)

        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result = score_predictions()

        expected_mape = abs(200.0 - 198.0) / 198.0
        assert abs(result["mape"] - expected_mape) < 0.001

    def test_bias_computation(self, tmp_path: Path) -> None:
        """Bias is average signed error (positive = bullish)."""
        past_date = (date.today() - timedelta(days=60)).isoformat()

        # Bias: 200 - 198 = +2 (predicted higher)
        pred1 = _make_prediction(
            ticker="AAPL",
            prediction_date=past_date,
            horizon_days=30,
            current_price=190.0,
            predicted_mid=200.0,
            actual_price=198.0,
            scored=True,
        )
        _write_prediction_file(tmp_path, pred1)

        # Bias: 420 - 430 = -10 (predicted lower)
        pred2 = _make_prediction(
            ticker="MSFT",
            prediction_date=past_date,
            horizon_days=30,
            current_price=400.0,
            predicted_mid=420.0,
            actual_price=430.0,
            scored=True,
        )
        _write_prediction_file(tmp_path, pred2)

        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result = score_predictions()

        # Bias = (2 + (-10)) / 2 = -4.0
        assert result["bias"] == -4.0

    def test_range_accuracy(self, tmp_path: Path) -> None:
        """range_accuracy is % of actuals within predicted CI (ci_5 to ci_95)."""
        past_date = (date.today() - timedelta(days=60)).isoformat()

        # CI: [180, 190, 210, 220], actual=195 -> within
        pred1 = _make_prediction(
            ticker="AAPL",
            prediction_date=past_date,
            horizon_days=30,
            current_price=190.0,
            predicted_mid=200.0,
            actual_price=195.0,
            scored=True,
        )
        _write_prediction_file(tmp_path, pred1)

        # CI: [378, 399, 441, 462], actual=500 -> outside
        pred2 = _make_prediction(
            ticker="MSFT",
            prediction_date=past_date,
            horizon_days=30,
            current_price=400.0,
            predicted_mid=420.0,
            actual_price=500.0,
            scored=True,
        )
        _write_prediction_file(tmp_path, pred2)

        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result = score_predictions()

        # 1 out of 2 within range
        assert result["range_accuracy"] == 0.5

    def test_filters_by_ticker(self, tmp_path: Path) -> None:
        """score_predictions filters by ticker when provided."""
        past_date = (date.today() - timedelta(days=60)).isoformat()

        for ticker in ("AAPL", "MSFT"):
            pred = _make_prediction(
                ticker=ticker,
                prediction_date=past_date,
                horizon_days=30,
                actual_price=195.0,
                scored=True,
            )
            _write_prediction_file(tmp_path, pred)

        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result = score_predictions(ticker="AAPL")

        assert result["total_predictions"] == 1
        assert result["predictions"][0]["ticker"] == "AAPL"

    def test_skips_future_target_date(self, tmp_path: Path) -> None:
        """Predictions with future target_date are not scored but included."""
        future_date = date.today().isoformat()
        pred = _make_prediction(
            prediction_date=future_date,
            horizon_days=30,  # target is 30 days from today
            current_price=190.0,
        )
        _write_prediction_file(tmp_path, pred)

        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result = score_predictions()

        assert result["total_predictions"] == 1
        # Should not be scored yet since target date is in the future
        assert result["predictions"][0]["scored"] is False
        assert result["predictions"][0]["actual_price"] is None

    def test_already_scored_not_re_fetched(self, tmp_path: Path) -> None:
        """Already scored predictions use their existing actual_price."""
        past_date = (date.today() - timedelta(days=60)).isoformat()
        pred = _make_prediction(
            prediction_date=past_date,
            horizon_days=30,
            actual_price=195.0,
            scored=True,
        )
        _write_prediction_file(tmp_path, pred)

        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            # No YFinanceClient mock needed - should not be called
            result = score_predictions()

        assert result["total_predictions"] == 1
        assert result["predictions"][0]["actual_price"] == 195.0

    def test_handles_corrupt_json_gracefully(self, tmp_path: Path) -> None:
        """Corrupt JSON files are skipped without crashing."""
        corrupt_file = tmp_path / "BAD_2025-01-01_30d.json"
        corrupt_file.write_text("{{not valid json")

        # Also add a valid prediction
        past_date = (date.today() - timedelta(days=60)).isoformat()
        pred = _make_prediction(
            prediction_date=past_date,
            horizon_days=30,
            actual_price=195.0,
            scored=True,
        )
        _write_prediction_file(tmp_path, pred)

        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result = score_predictions()

        # Should still return the valid prediction
        assert result["total_predictions"] == 1

    def test_handles_missing_predictions_dir(self, tmp_path: Path) -> None:
        """Non-existent predictions directory returns empty result."""
        missing_dir = tmp_path / "nonexistent"
        with patch("zaza.utils.predictions.PREDICTIONS_DIR", missing_dir):
            result = score_predictions()

        assert result["total_predictions"] == 0
        assert result["predictions"] == []

    def test_handles_empty_directory(self, tmp_path: Path) -> None:
        """Empty predictions directory returns empty result."""
        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            result = score_predictions()

        assert result["total_predictions"] == 0

    def test_scoring_updates_file_on_disk(self, tmp_path: Path) -> None:
        """When a prediction is scored, the file on disk is updated."""
        past_date = (date.today() - timedelta(days=60)).isoformat()
        pred = _make_prediction(
            prediction_date=past_date,
            horizon_days=30,
            current_price=190.0,
            predicted_mid=200.0,
        )
        filepath = _write_prediction_file(tmp_path, pred)

        mock_yf = MagicMock()
        mock_yf.get_quote.return_value = {"regularMarketPrice": 198.0}

        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            with patch("zaza.utils.predictions.YFinanceClient", return_value=mock_yf):
                with patch("zaza.utils.predictions.FileCache"):
                    score_predictions()

        # Re-read the file
        updated = orjson.loads(filepath.read_bytes())
        assert updated["actual_price"] == 198.0
        assert updated["scored"] is True

    def test_yfinance_failure_skips_scoring(self, tmp_path: Path) -> None:
        """If yfinance fails to return a price, prediction is left unscored."""
        past_date = (date.today() - timedelta(days=60)).isoformat()
        pred = _make_prediction(
            prediction_date=past_date,
            horizon_days=30,
        )
        _write_prediction_file(tmp_path, pred)

        mock_yf = MagicMock()
        mock_yf.get_quote.return_value = {}  # No price data

        with patch("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path):
            with patch("zaza.utils.predictions.YFinanceClient", return_value=mock_yf):
                with patch("zaza.utils.predictions.FileCache"):
                    result = score_predictions()

        assert result["total_predictions"] == 1
        assert result["predictions"][0]["scored"] is False


# ---------------------------------------------------------------------------
# rotate_logs() tests
# ---------------------------------------------------------------------------


class TestRotateLogs:
    """Tests for the rotate_logs function."""

    def test_rotates_old_files(self, tmp_path: Path) -> None:
        """Files older than 1 year are moved to archive/."""
        # Create an old prediction (> 1 year ago)
        old_date = (date.today() - timedelta(days=400)).isoformat()
        pred = _make_prediction(
            prediction_date=old_date,
            horizon_days=30,
            actual_price=195.0,
            scored=True,
        )
        filepath = _write_prediction_file(tmp_path, pred)

        count = rotate_logs(tmp_path)

        assert count == 1
        assert not filepath.exists()
        archive_dir = tmp_path / "archive"
        assert archive_dir.exists()
        archived_files = list(archive_dir.glob("*.json"))
        assert len(archived_files) == 1

    def test_does_not_rotate_recent_files(self, tmp_path: Path) -> None:
        """Files less than 1 year old are not rotated."""
        recent_date = (date.today() - timedelta(days=30)).isoformat()
        pred = _make_prediction(
            prediction_date=recent_date,
            horizon_days=30,
            actual_price=195.0,
            scored=True,
        )
        filepath = _write_prediction_file(tmp_path, pred)

        count = rotate_logs(tmp_path)

        assert count == 0
        assert filepath.exists()

    def test_uses_custom_archive_dir(self, tmp_path: Path) -> None:
        """Archive directory can be customized."""
        old_date = (date.today() - timedelta(days=400)).isoformat()
        pred = _make_prediction(
            prediction_date=old_date,
            horizon_days=30,
            scored=True,
        )
        _write_prediction_file(tmp_path, pred)

        custom_archive = tmp_path / "custom_archive"
        count = rotate_logs(tmp_path, archive_dir=custom_archive)

        assert count == 1
        assert custom_archive.exists()
        assert len(list(custom_archive.glob("*.json"))) == 1

    def test_empty_directory_returns_zero(self, tmp_path: Path) -> None:
        """Empty predictions directory returns 0 archived files."""
        count = rotate_logs(tmp_path)
        assert count == 0

    def test_handles_missing_directory(self, tmp_path: Path) -> None:
        """Non-existent directory returns 0 without error."""
        missing = tmp_path / "nonexistent"
        count = rotate_logs(missing)
        assert count == 0

    def test_mixed_old_and_recent(self, tmp_path: Path) -> None:
        """Only old files are rotated, recent ones stay."""
        old_date = (date.today() - timedelta(days=400)).isoformat()
        recent_date = (date.today() - timedelta(days=30)).isoformat()

        old_pred = _make_prediction(
            ticker="OLD",
            prediction_date=old_date,
            horizon_days=30,
            scored=True,
        )
        recent_pred = _make_prediction(
            ticker="RECENT",
            prediction_date=recent_date,
            horizon_days=30,
            scored=True,
        )

        _write_prediction_file(tmp_path, old_pred)
        recent_path = _write_prediction_file(tmp_path, recent_pred)

        count = rotate_logs(tmp_path)

        assert count == 1
        assert recent_path.exists()
        assert len(list((tmp_path / "archive").glob("*.json"))) == 1


# ---------------------------------------------------------------------------
# Integration: get_prediction_score tool uses score_predictions()
# ---------------------------------------------------------------------------


class TestScoringToolIntegration:
    """Verify get_prediction_score tool uses the new score_predictions."""

    @pytest.mark.asyncio
    async def test_tool_returns_new_metrics(self, tmp_path: Path) -> None:
        """get_prediction_score tool returns the new metrics from score_predictions."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.scoring import register

        past_date = (date.today() - timedelta(days=60)).isoformat()
        pred = _make_prediction(
            prediction_date=past_date,
            horizon_days=30,
            current_price=190.0,
            predicted_mid=200.0,
            actual_price=198.0,
            scored=True,
        )
        _write_prediction_file(tmp_path, pred)

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.scoring.PREDICTIONS_DIR", tmp_path):
            register(mcp)

            tool = mcp._tool_manager.get_tool("get_prediction_score")
            result_str = await tool.run(arguments={})
            result = json.loads(result_str)

        assert "total_predictions" in result
        assert "directional_accuracy" in result
        assert "mae" in result
        assert "mape" in result
        assert "bias" in result
        assert "range_accuracy" in result

    @pytest.mark.asyncio
    async def test_tool_filters_by_ticker(self, tmp_path: Path) -> None:
        """get_prediction_score tool filters by ticker."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.scoring import register

        past_date = (date.today() - timedelta(days=60)).isoformat()

        for ticker in ("AAPL", "MSFT"):
            pred = _make_prediction(
                ticker=ticker,
                prediction_date=past_date,
                horizon_days=30,
                actual_price=195.0,
                scored=True,
            )
            _write_prediction_file(tmp_path, pred)

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.scoring.PREDICTIONS_DIR", tmp_path):
            register(mcp)

            tool = mcp._tool_manager.get_tool("get_prediction_score")
            result_str = await tool.run(arguments={"ticker": "AAPL"})
            result = json.loads(result_str)

        assert result["total_predictions"] == 1

    @pytest.mark.asyncio
    async def test_tool_handles_error(self, tmp_path: Path) -> None:
        """get_prediction_score returns error JSON on unexpected failure."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.scoring import register

        mcp = FastMCP("test")

        with patch("zaza.tools.backtesting.scoring.PREDICTIONS_DIR", tmp_path):
            with patch(
                "zaza.tools.backtesting.scoring.score_predictions",
                side_effect=RuntimeError("test error"),
            ):
                register(mcp)

                tool = mcp._tool_manager.get_tool("get_prediction_score")
                result_str = await tool.run(arguments={})
                result = json.loads(result_str)

        assert "error" in result
