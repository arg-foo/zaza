"""Tests for prediction revision support in PredictionLog and scoring.

Step 1: Extends PredictionLog with revision fields, updates filename
generation for revisions, and ensures scoring skips revision entries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import orjson
import pytest

from zaza.utils.predictions import PredictionLog, log_prediction, score_predictions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prediction_log(
    ticker: str = "AAPL",
    prediction_date: str = "2026-03-20",
    horizon_days: int = 10,
    *,
    is_revision: bool = False,
    revision_number: int = 0,
    parent_prediction: str | None = None,
    revision_date: str | None = None,
    drift_assessment: str | None = None,
    drift_details: dict[str, Any] | None = None,
) -> PredictionLog:
    """Build a PredictionLog with optional revision fields."""
    return PredictionLog(
        ticker=ticker,
        prediction_date=prediction_date,
        horizon_days=horizon_days,
        target_date="2026-03-30",
        current_price=185.50,
        predicted_range={"low": 180.0, "mid": 187.0, "high": 194.0},
        confidence_interval={
            "ci_5": 178.0,
            "ci_25": 183.0,
            "ci_75": 191.0,
            "ci_95": 196.0,
        },
        model_weights={"momentum": 0.3, "mean_reversion": 0.2, "volatility": 0.5},
        key_factors=["RSI oversold bounce", "Earnings beat"],
        is_revision=is_revision,
        revision_number=revision_number,
        parent_prediction=parent_prediction,
        revision_date=revision_date,
        drift_assessment=drift_assessment,
        drift_details=drift_details,
    )


def _write_prediction_file(
    directory: Path,
    filename: str,
    data: dict[str, Any],
) -> Path:
    """Write a prediction JSON file to the given directory."""
    filepath = directory / filename
    filepath.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
    return filepath


def _make_prediction_data(
    ticker: str = "AAPL",
    prediction_date: str = "2026-03-20",
    horizon_days: int = 10,
    *,
    is_revision: bool = False,
    revision_number: int = 0,
    parent_prediction: str | None = None,
    scored: bool = True,
    actual_price: float | None = 190.0,
    current_price: float = 185.50,
) -> dict[str, Any]:
    """Build a prediction data dict for writing to disk."""
    data: dict[str, Any] = {
        "ticker": ticker,
        "prediction_date": prediction_date,
        "horizon_days": horizon_days,
        "target_date": "2026-03-01",
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
        "actual_price": actual_price,
        "scored": scored,
    }
    if is_revision:
        data["is_revision"] = True
        data["revision_number"] = revision_number
        data["parent_prediction"] = parent_prediction
    return data


# ---------------------------------------------------------------------------
# Tests: PredictionLog revision fields defaults
# ---------------------------------------------------------------------------


class TestPredictionLogRevisionFields:
    """Verify new revision fields have correct defaults."""

    def test_prediction_log_revision_fields_default(self) -> None:
        """New PredictionLog without revision fields has sensible defaults."""
        pred = _make_prediction_log()

        assert pred.is_revision is False
        assert pred.revision_number == 0
        assert pred.parent_prediction is None
        assert pred.revision_date is None
        assert pred.drift_assessment is None
        assert pred.drift_details is None

    def test_prediction_log_revision_fields_set(self) -> None:
        """PredictionLog with revision fields set retains them."""
        drift = {"price": 0.03, "volume": -0.01, "sentiment": 0.05}
        pred = _make_prediction_log(
            is_revision=True,
            revision_number=2,
            parent_prediction="AAPL_2026-03-20_10d.json",
            revision_date="2026-03-25",
            drift_assessment="MODIFY",
            drift_details=drift,
        )

        assert pred.is_revision is True
        assert pred.revision_number == 2
        assert pred.parent_prediction == "AAPL_2026-03-20_10d.json"
        assert pred.revision_date == "2026-03-25"
        assert pred.drift_assessment == "MODIFY"
        assert pred.drift_details == drift


# ---------------------------------------------------------------------------
# Tests: log_prediction filename generation
# ---------------------------------------------------------------------------


class TestLogPredictionFilename:
    """Verify filename generation for original vs revision predictions."""

    @pytest.fixture(autouse=True)
    def _patch_predictions_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Patch PREDICTIONS_DIR to use tmp_path."""
        monkeypatch.setattr("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path)
        self._tmp_path = tmp_path

    def test_log_prediction_original_filename_unchanged(self) -> None:
        """log_prediction with default fields produces standard filename."""
        pred = _make_prediction_log(
            ticker="AAPL",
            prediction_date="2026-03-20",
            horizon_days=10,
        )
        path = log_prediction(pred)

        assert path.name == "AAPL_2026-03-20_10d.json"

    def test_log_prediction_revision_filename(self) -> None:
        """log_prediction with is_revision=True, revision_number=2 produces _r2 filename."""
        pred = _make_prediction_log(
            ticker="AAPL",
            prediction_date="2026-03-20",
            horizon_days=10,
            is_revision=True,
            revision_number=2,
            parent_prediction="AAPL_2026-03-20_10d.json",
        )
        path = log_prediction(pred)

        assert path.name == "AAPL_2026-03-20_10d_r2.json"

    def test_log_prediction_revision_number_1(self) -> None:
        """First revision produces _r1 filename."""
        pred = _make_prediction_log(
            ticker="TSLA",
            prediction_date="2026-03-15",
            horizon_days=5,
            is_revision=True,
            revision_number=1,
            parent_prediction="TSLA_2026-03-15_5d.json",
        )
        path = log_prediction(pred)

        assert path.name == "TSLA_2026-03-15_5d_r1.json"

    def test_log_prediction_revision_zero_uses_standard_filename(self) -> None:
        """is_revision=True but revision_number=0 uses standard filename (edge case)."""
        pred = _make_prediction_log(
            ticker="AAPL",
            prediction_date="2026-03-20",
            horizon_days=10,
            is_revision=True,
            revision_number=0,
        )
        path = log_prediction(pred)

        # revision_number=0 means not actually a revision
        assert path.name == "AAPL_2026-03-20_10d.json"


# ---------------------------------------------------------------------------
# Tests: score_predictions skips revisions
# ---------------------------------------------------------------------------


class TestScorePredictionsSkipsRevisions:
    """Verify scoring only includes original predictions, not revisions."""

    def test_score_predictions_skips_revisions(self, tmp_path: Path) -> None:
        """Scoring loop skips entries where is_revision=True."""
        # Write an original prediction (scored, with actual_price)
        original_data = _make_prediction_data(
            ticker="AAPL",
            prediction_date="2026-03-10",
            horizon_days=10,
            scored=True,
            actual_price=190.0,
        )
        _write_prediction_file(
            tmp_path, "AAPL_2026-03-10_10d.json", original_data
        )

        # Write a revision prediction (also scored, with actual_price)
        revision_data = _make_prediction_data(
            ticker="AAPL",
            prediction_date="2026-03-10",
            horizon_days=10,
            is_revision=True,
            revision_number=1,
            parent_prediction="AAPL_2026-03-10_10d.json",
            scored=True,
            actual_price=190.0,
        )
        _write_prediction_file(
            tmp_path, "AAPL_2026-03-10_10d_r1.json", revision_data
        )

        result = score_predictions(ticker="AAPL", predictions_dir=tmp_path)

        # Should only include the original, not the revision
        assert result["total_predictions"] == 1
        assert len(result["predictions"]) == 1
        assert result["predictions"][0]["prediction_date"] == "2026-03-10"

    def test_legacy_predictions_treated_as_originals(self, tmp_path: Path) -> None:
        """Files without is_revision field are treated as originals (not skipped)."""
        legacy_data: dict[str, Any] = {
            "ticker": "MSFT",
            "prediction_date": "2026-03-05",
            "horizon_days": 5,
            "target_date": "2026-03-01",
            "current_price": 420.0,
            "predicted_range": {"low": 415.0, "mid": 425.0, "high": 435.0},
            "confidence_interval": {
                "ci_5": 410.0,
                "ci_25": 418.0,
                "ci_75": 432.0,
                "ci_95": 440.0,
            },
            "model_weights": {"momentum": 0.5, "mean_reversion": 0.5},
            "key_factors": ["Strong earnings"],
            "actual_price": 428.0,
            "scored": True,
            # No is_revision field at all
        }
        _write_prediction_file(tmp_path, "MSFT_2026-03-05_5d.json", legacy_data)

        result = score_predictions(ticker="MSFT", predictions_dir=tmp_path)

        # Legacy file should be included (not skipped)
        assert result["total_predictions"] == 1
        assert len(result["predictions"]) == 1
        assert result["predictions"][0]["ticker"] == "MSFT"

    def test_score_predictions_mixed_originals_and_revisions(
        self, tmp_path: Path
    ) -> None:
        """With multiple originals and revisions, only originals are scored."""
        # Two originals
        for i, ticker in enumerate(["AAPL", "GOOG"]):
            data = _make_prediction_data(
                ticker=ticker,
                prediction_date="2026-03-10",
                horizon_days=10,
                scored=True,
                actual_price=190.0 + i * 10,
            )
            _write_prediction_file(
                tmp_path, f"{ticker}_2026-03-10_10d.json", data
            )

        # Two revisions
        for i, ticker in enumerate(["AAPL", "GOOG"]):
            data = _make_prediction_data(
                ticker=ticker,
                prediction_date="2026-03-10",
                horizon_days=10,
                is_revision=True,
                revision_number=1,
                parent_prediction=f"{ticker}_2026-03-10_10d.json",
                scored=True,
                actual_price=190.0 + i * 10,
            )
            _write_prediction_file(
                tmp_path, f"{ticker}_2026-03-10_10d_r1.json", data
            )

        result = score_predictions(predictions_dir=tmp_path)

        # Only 2 originals, not the 2 revisions
        assert result["total_predictions"] == 2
        assert len(result["predictions"]) == 2


# ---------------------------------------------------------------------------
# Helpers for save_prediction_revision tool tests
# ---------------------------------------------------------------------------


def _make_revision_prediction_json(
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


def _create_parent_on_disk(
    tmp_path: Path,
    ticker: str = "GLNG",
    pred_date: str = "2026-03-23",
    horizon: int = 10,
) -> str:
    """Create a parent prediction file on disk and return its filename."""
    from datetime import date, timedelta

    filename = f"{ticker}_{pred_date}_{horizon}d.json"
    target_date = (
        date.fromisoformat(pred_date) + timedelta(days=horizon)
    ).isoformat()
    data = {
        "ticker": ticker,
        "current_price": 185.50,
        "predicted_range": {"low": 180.0, "mid": 187.0, "high": 194.0},
        "confidence_interval": {"ci_5": 178.0},
        "model_weights": {"momentum": 0.3},
        "key_factors": ["test factor"],
        "prediction_date": pred_date,
        "horizon_days": horizon,
        "target_date": target_date,
        "scored": False,
        "actual_price": None,
    }
    (tmp_path / filename).write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
    return filename


# ---------------------------------------------------------------------------
# Tests: save_prediction_revision MCP tool
# ---------------------------------------------------------------------------


class TestSavePredictionRevision:
    """Tests for the save_prediction_revision MCP tool."""

    @pytest.fixture(autouse=True)
    def _patch_predictions_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Patch PREDICTIONS_DIR to use tmp_path for all tests."""
        monkeypatch.setattr(
            "zaza.tools.backtesting.save_prediction_revision.PREDICTIONS_DIR",
            tmp_path,
        )
        self._tmp_path = tmp_path

    def _get_tool_fn(self):
        """Register save_prediction_revision and return the tool function."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.backtesting.save_prediction_revision import register

        mcp = FastMCP("test")
        register(mcp)
        return mcp._tool_manager._tools["save_prediction_revision"].fn

    async def test_save_revision_filename_format(self) -> None:
        """Revision saves with _r1.json suffix based on parent filename."""
        parent = _create_parent_on_disk(self._tmp_path)
        tool_fn = self._get_tool_fn()

        result = await tool_fn(
            ticker="GLNG",
            parent_prediction=parent,
            prediction_data=_make_revision_prediction_json(),
        )
        parsed = json.loads(result)

        assert parsed["status"] == "ok"
        assert parsed["file"] == "GLNG_2026-03-23_10d_r1.json"
        assert parsed["revision_number"] == 1
        assert (self._tmp_path / parsed["file"]).exists()

    async def test_revision_increments_number(self) -> None:
        """Saving two revisions produces _r1 then _r2."""
        parent = _create_parent_on_disk(self._tmp_path)
        tool_fn = self._get_tool_fn()

        r1_result = await tool_fn(
            ticker="GLNG",
            parent_prediction=parent,
            prediction_data=_make_revision_prediction_json(current_price=190.0),
        )
        r1 = json.loads(r1_result)
        assert r1["status"] == "ok"
        assert r1["file"] == "GLNG_2026-03-23_10d_r1.json"
        assert r1["revision_number"] == 1

        r2_result = await tool_fn(
            ticker="GLNG",
            parent_prediction=parent,
            prediction_data=_make_revision_prediction_json(current_price=195.0),
        )
        r2 = json.loads(r2_result)
        assert r2["status"] == "ok"
        assert r2["file"] == "GLNG_2026-03-23_10d_r2.json"
        assert r2["revision_number"] == 2

    async def test_revision_requires_parent(self) -> None:
        """Empty parent_prediction returns error."""
        tool_fn = self._get_tool_fn()

        result = await tool_fn(
            ticker="GLNG",
            parent_prediction="",
            prediction_data=_make_revision_prediction_json(),
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "parent" in parsed["error"].lower()

    async def test_revision_rejects_missing_parent_file(self) -> None:
        """Error if parent prediction file doesn't exist on disk."""
        tool_fn = self._get_tool_fn()

        result = await tool_fn(
            ticker="GLNG",
            parent_prediction="GLNG_2026-03-23_10d.json",
            prediction_data=_make_revision_prediction_json(),
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "not found" in parsed["error"].lower() or "does not exist" in parsed["error"].lower()

    async def test_revision_rejects_revision_as_parent(self) -> None:
        """Can't chain revisions -- parent must be an original prediction."""
        parent = _create_parent_on_disk(self._tmp_path)
        tool_fn = self._get_tool_fn()

        # Create r1 first
        await tool_fn(
            ticker="GLNG",
            parent_prediction=parent,
            prediction_data=_make_revision_prediction_json(),
        )

        # Try to use r1 as parent
        result = await tool_fn(
            ticker="GLNG",
            parent_prediction="GLNG_2026-03-23_10d_r1.json",
            prediction_data=_make_revision_prediction_json(),
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "revision" in parsed["error"].lower()

    async def test_revision_preserves_original_date(self) -> None:
        """prediction_date in saved JSON matches parent's date, NOT today."""
        parent = _create_parent_on_disk(
            self._tmp_path, pred_date="2026-03-20"
        )
        tool_fn = self._get_tool_fn()

        result = await tool_fn(
            ticker="GLNG",
            parent_prediction=parent,
            prediction_data=_make_revision_prediction_json(),
        )
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

        file_path = self._tmp_path / parsed["file"]
        written = orjson.loads(file_path.read_bytes())

        assert written["prediction_date"] == "2026-03-20"

    async def test_revision_sets_revision_date(self) -> None:
        """revision_date is today's date."""
        from datetime import date

        parent = _create_parent_on_disk(self._tmp_path)
        tool_fn = self._get_tool_fn()

        result = await tool_fn(
            ticker="GLNG",
            parent_prediction=parent,
            prediction_data=_make_revision_prediction_json(),
        )
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

        file_path = self._tmp_path / parsed["file"]
        written = orjson.loads(file_path.read_bytes())

        assert written["revision_date"] == date.today().isoformat()

    async def test_revision_has_is_revision_flag(self) -> None:
        """is_revision=True in saved JSON with all revision metadata."""
        parent = _create_parent_on_disk(self._tmp_path)
        tool_fn = self._get_tool_fn()

        result = await tool_fn(
            ticker="GLNG",
            parent_prediction=parent,
            prediction_data=_make_revision_prediction_json(),
        )
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

        file_path = self._tmp_path / parsed["file"]
        written = orjson.loads(file_path.read_bytes())

        assert written["is_revision"] is True
        assert written["revision_number"] == 1
        assert written["parent_prediction"] == "GLNG_2026-03-23_10d.json"
        assert written["scored"] is False
        assert written["actual_price"] is None

    async def test_revision_validates_required_keys(self) -> None:
        """Missing required keys (e.g. current_price) returns error."""
        parent = _create_parent_on_disk(self._tmp_path)
        tool_fn = self._get_tool_fn()

        incomplete_data = json.dumps(
            {
                "predicted_range": {"low": 180.0},
                "model_weights": {"momentum": 0.3},
            }
        )

        result = await tool_fn(
            ticker="GLNG",
            parent_prediction=parent,
            prediction_data=incomplete_data,
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "current_price" in parsed["error"]

    @pytest.mark.parametrize(
        "bad_ticker",
        [
            "INVALID123",
            "../etc/passwd",
            "A" * 11,
            "aa bb",
            "AAPL!",
            "",
        ],
    )
    async def test_revision_validates_ticker(self, bad_ticker: str) -> None:
        """Invalid ticker formats return error."""
        parent = _create_parent_on_disk(self._tmp_path)
        tool_fn = self._get_tool_fn()

        result = await tool_fn(
            ticker=bad_ticker,
            parent_prediction=parent,
            prediction_data=_make_revision_prediction_json(),
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "Invalid ticker format" in parsed["error"]

    @pytest.mark.parametrize(
        "bad_parent",
        [
            "../../../etc/passwd",
            "../other_dir/GLNG_2026-03-23_10d.json",
            "/abs/path/GLNG_2026-03-23_10d.json",
        ],
    )
    async def test_revision_rejects_path_traversal(
        self, bad_parent: str
    ) -> None:
        """Path traversal attempts in parent_prediction are rejected."""
        _create_parent_on_disk(self._tmp_path)
        tool_fn = self._get_tool_fn()

        result = await tool_fn(
            ticker="GLNG",
            parent_prediction=bad_parent,
            prediction_data=_make_revision_prediction_json(),
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"

    async def test_revision_rejects_ticker_mismatch(self) -> None:
        """Ticker mismatch between parameter and parent filename returns error."""
        _create_parent_on_disk(self._tmp_path, ticker="GLNG")
        tool_fn = self._get_tool_fn()

        result = await tool_fn(
            ticker="AAPL",
            parent_prediction="GLNG_2026-03-23_10d.json",
            prediction_data=_make_revision_prediction_json(),
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "Ticker mismatch" in parsed["error"]
        assert "AAPL" in parsed["error"]
        assert "GLNG" in parsed["error"]

    async def test_revision_rejects_parent_missing_required_fields(
        self,
    ) -> None:
        """Parent prediction missing target_date returns error."""
        # Write a parent file WITHOUT target_date
        filename = "GLNG_2026-03-23_10d.json"
        data = {
            "ticker": "GLNG",
            "current_price": 185.50,
            "predicted_range": {"low": 180.0, "mid": 187.0, "high": 194.0},
            "confidence_interval": {"ci_5": 178.0},
            "model_weights": {"momentum": 0.3},
            "key_factors": ["test factor"],
            "prediction_date": "2026-03-23",
            "horizon_days": 10,
            # Deliberately missing "target_date"
            "scored": False,
            "actual_price": None,
        }
        (self._tmp_path / filename).write_bytes(
            orjson.dumps(data, option=orjson.OPT_INDENT_2)
        )

        tool_fn = self._get_tool_fn()

        result = await tool_fn(
            ticker="GLNG",
            parent_prediction=filename,
            prediction_data=_make_revision_prediction_json(),
        )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "missing required fields" in parsed["error"].lower()

    async def test_revision_atomic_write(self) -> None:
        """File exists after save, no .tmp files left behind."""
        parent = _create_parent_on_disk(self._tmp_path)
        tool_fn = self._get_tool_fn()

        result = await tool_fn(
            ticker="GLNG",
            parent_prediction=parent,
            prediction_data=_make_revision_prediction_json(),
        )
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

        # Revision file exists
        assert (self._tmp_path / parsed["file"]).exists()

        # No .tmp files left
        tmp_files = list(self._tmp_path.glob("*.tmp"))
        assert tmp_files == []


# ---------------------------------------------------------------------------
# Helpers for get_prediction / get_prediction_chain tests
# ---------------------------------------------------------------------------


def _get_prediction_tool_fn(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Register predictions tools and return (get_prediction_fn, get_prediction_chain_fn)."""
    from mcp.server.fastmcp import FastMCP

    from zaza.tools.backtesting.predictions import register

    monkeypatch.setattr(
        "zaza.tools.backtesting.predictions.PREDICTIONS_DIR", tmp_path
    )
    mcp = FastMCP("test")
    register(mcp)
    get_pred = mcp._tool_manager._tools["get_prediction"].fn
    get_chain = mcp._tool_manager._tools["get_prediction_chain"].fn
    return get_pred, get_chain


def _write_prediction_for_retrieval(
    directory: Path,
    filename: str,
    ticker: str = "AAPL",
    prediction_date: str = "2026-03-20",
    horizon_days: int = 10,
    *,
    is_revision: bool = False,
    revision_number: int = 0,
    parent_prediction: str | None = None,
    current_price: float = 185.50,
) -> Path:
    """Write a prediction file with optional revision fields for retrieval tests."""
    data: dict[str, Any] = {
        "ticker": ticker,
        "prediction_date": prediction_date,
        "horizon_days": horizon_days,
        "target_date": "2026-03-30",
        "current_price": current_price,
        "predicted_range": {"low": 180.0, "mid": 187.0, "high": 194.0},
        "confidence_interval": {
            "ci_5": 178.0,
            "ci_25": 183.0,
            "ci_75": 191.0,
            "ci_95": 196.0,
        },
        "model_weights": {"momentum": 0.3, "mean_reversion": 0.2, "volatility": 0.5},
        "key_factors": ["RSI oversold bounce"],
        "actual_price": None,
        "scored": False,
    }
    if is_revision:
        data["is_revision"] = True
        data["revision_number"] = revision_number
        data["parent_prediction"] = parent_prediction
    filepath = directory / filename
    filepath.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
    return filepath


# ---------------------------------------------------------------------------
# Tests: get_prediction with revision awareness (Steps 3 & 4)
# ---------------------------------------------------------------------------


class TestGetPredictionRevisionAwareness:
    """Tests for get_prediction revision-aware sorting and filtering."""

    async def test_get_prediction_returns_latest_revision(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With original + r1 + r2, get_prediction returns r2 (latest revision)."""
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-20_10d.json",
            prediction_date="2026-03-20",
        )
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-20_10d_r1.json",
            prediction_date="2026-03-20",
            is_revision=True, revision_number=1,
            parent_prediction="AAPL_2026-03-20_10d.json",
            current_price=190.0,
        )
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-20_10d_r2.json",
            prediction_date="2026-03-20",
            is_revision=True, revision_number=2,
            parent_prediction="AAPL_2026-03-20_10d.json",
            current_price=195.0,
        )

        get_pred, _ = _get_prediction_tool_fn(monkeypatch, tmp_path)
        result = await get_pred(ticker="AAPL")
        parsed = json.loads(result)

        assert parsed["status"] == "ok"
        assert parsed["data"]["current_price"] == 195.0
        assert parsed["data"]["revision_number"] == 2

    async def test_get_prediction_original_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With original_only=True, revisions are filtered out."""
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-20_10d.json",
            prediction_date="2026-03-20",
            current_price=185.50,
        )
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-20_10d_r1.json",
            prediction_date="2026-03-20",
            is_revision=True, revision_number=1,
            parent_prediction="AAPL_2026-03-20_10d.json",
            current_price=190.0,
        )

        get_pred, _ = _get_prediction_tool_fn(monkeypatch, tmp_path)
        result = await get_pred(ticker="AAPL", original_only=True)
        parsed = json.loads(result)

        assert parsed["status"] == "ok"
        assert parsed["data"]["current_price"] == 185.50
        assert parsed["data"].get("is_revision") is not True

    async def test_get_prediction_by_date_returns_latest_revision(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When prediction_date is specified, still returns latest revision for that date."""
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-20_10d.json",
            prediction_date="2026-03-20",
            current_price=185.50,
        )
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-20_10d_r1.json",
            prediction_date="2026-03-20",
            is_revision=True, revision_number=1,
            parent_prediction="AAPL_2026-03-20_10d.json",
            current_price=192.0,
        )

        get_pred, _ = _get_prediction_tool_fn(monkeypatch, tmp_path)
        result = await get_pred(ticker="AAPL", prediction_date="2026-03-20")
        parsed = json.loads(result)

        assert parsed["status"] == "ok"
        assert parsed["data"]["current_price"] == 192.0
        assert parsed["data"]["revision_number"] == 1

    async def test_get_prediction_no_revisions_returns_original(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When only original exists, get_prediction returns it (backward compat)."""
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-20_10d.json",
            prediction_date="2026-03-20",
            current_price=185.50,
        )

        get_pred, _ = _get_prediction_tool_fn(monkeypatch, tmp_path)
        result = await get_pred(ticker="AAPL")
        parsed = json.loads(result)

        assert parsed["status"] == "ok"
        assert parsed["data"]["current_price"] == 185.50
        assert parsed["data"]["prediction_date"] == "2026-03-20"


# ---------------------------------------------------------------------------
# Tests: get_prediction_chain tool
# ---------------------------------------------------------------------------


class TestGetPredictionChain:
    """Tests for the get_prediction_chain MCP tool."""

    async def test_get_prediction_chain_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Chain returns [original, r1, r2] in revision_number ascending order."""
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-20_10d.json",
            prediction_date="2026-03-20",
            current_price=185.50,
        )
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-20_10d_r1.json",
            prediction_date="2026-03-20",
            is_revision=True, revision_number=1,
            parent_prediction="AAPL_2026-03-20_10d.json",
            current_price=190.0,
        )
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-20_10d_r2.json",
            prediction_date="2026-03-20",
            is_revision=True, revision_number=2,
            parent_prediction="AAPL_2026-03-20_10d.json",
            current_price=195.0,
        )

        _, get_chain = _get_prediction_tool_fn(monkeypatch, tmp_path)
        result = await get_chain(ticker="AAPL")
        parsed = json.loads(result)

        assert parsed["status"] == "ok"
        assert parsed["ticker"] == "AAPL"
        chain = parsed["chain"]
        assert len(chain) == 3
        assert chain[0]["revision"] == 0
        assert chain[0]["file"] == "AAPL_2026-03-20_10d.json"
        assert chain[1]["revision"] == 1
        assert chain[1]["file"] == "AAPL_2026-03-20_10d_r1.json"
        assert chain[2]["revision"] == 2
        assert chain[2]["file"] == "AAPL_2026-03-20_10d_r2.json"

    async def test_get_prediction_chain_no_revisions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Chain with only original returns [original]."""
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-20_10d.json",
            prediction_date="2026-03-20",
        )

        _, get_chain = _get_prediction_tool_fn(monkeypatch, tmp_path)
        result = await get_chain(ticker="AAPL")
        parsed = json.loads(result)

        assert parsed["status"] == "ok"
        chain = parsed["chain"]
        assert len(chain) == 1
        assert chain[0]["revision"] == 0
        assert chain[0]["file"] == "AAPL_2026-03-20_10d.json"

    async def test_get_prediction_chain_filters_by_date(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Chain filters to specified prediction_date only."""
        # Prediction date A with revision
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-15_10d.json",
            prediction_date="2026-03-15",
            current_price=180.0,
        )
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-15_10d_r1.json",
            prediction_date="2026-03-15",
            is_revision=True, revision_number=1,
            parent_prediction="AAPL_2026-03-15_10d.json",
            current_price=182.0,
        )
        # Prediction date B (different date)
        _write_prediction_for_retrieval(
            tmp_path, "AAPL_2026-03-20_10d.json",
            prediction_date="2026-03-20",
            current_price=185.50,
        )

        _, get_chain = _get_prediction_tool_fn(monkeypatch, tmp_path)
        result = await get_chain(ticker="AAPL", prediction_date="2026-03-15")
        parsed = json.loads(result)

        assert parsed["status"] == "ok"
        chain = parsed["chain"]
        assert len(chain) == 2
        assert chain[0]["data"]["prediction_date"] == "2026-03-15"
        assert chain[1]["data"]["prediction_date"] == "2026-03-15"

    async def test_get_prediction_chain_no_predictions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Chain returns error when no predictions exist."""
        _, get_chain = _get_prediction_tool_fn(monkeypatch, tmp_path)
        result = await get_chain(ticker="AAPL")
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "No predictions found" in parsed["error"]
