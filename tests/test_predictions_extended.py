"""Tests for extended PredictionLog dataclass fields.

Verifies that the new optional fields (catalyst_calendar, catalyst_cluster,
scenario_conditions, short_interest, buyback_support, weighting_mode) work
correctly for both new and legacy prediction data.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import orjson
import pytest

from zaza.utils.predictions import PredictionLog, _load_prediction_files, log_prediction

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_prediction_kwargs() -> dict:
    """Return minimal kwargs for a valid PredictionLog."""
    return {
        "ticker": "AAPL",
        "prediction_date": "2026-03-20",
        "horizon_days": 5,
        "target_date": "2026-03-25",
        "current_price": 185.50,
        "predicted_range": {"low": 180.0, "mid": 187.0, "high": 194.0},
        "confidence_interval": {"ci_5": 178.0, "ci_25": 183.0, "ci_75": 191.0, "ci_95": 196.0},
        "model_weights": {"momentum": 0.3, "mean_reversion": 0.2, "volatility": 0.5},
        "key_factors": ["RSI oversold bounce", "Earnings beat", "Sector rotation"],
    }


def _extended_fields() -> dict:
    """Return all extended fields with sample data."""
    return {
        "catalyst_calendar": [
            {"date": "2026-03-22", "event": "Earnings report"},
            {"date": "2026-03-25", "event": "Fed meeting"},
        ],
        "catalyst_cluster": {
            "density": 0.8,
            "window_days": 5,
            "events_count": 2,
        },
        "scenario_conditions": {
            "bull_requires": "Price breaks above $190 with volume",
            "bear_triggered_by": "Fails to hold $183 support",
            "base_assumes": "Consolidation between $183-$190",
        },
        "short_interest": {
            "short_ratio": 3.2,
            "short_pct_float": 0.045,
            "days_to_cover": 2.1,
        },
        "buyback_support": {
            "active": True,
            "remaining_authorization": 50_000_000_000,
            "avg_quarterly_spend": 20_000_000_000,
        },
        "weighting_mode": "catalyst_adjusted",
    }


# ---------------------------------------------------------------------------
# Test: PredictionLog with all extended fields populated
# ---------------------------------------------------------------------------


class TestPredictionLogExtendedFields:
    """Tests for PredictionLog dataclass extended fields."""

    def test_create_with_all_extended_fields(self) -> None:
        """PredictionLog accepts all extended fields and stores them."""
        kwargs = {**_base_prediction_kwargs(), **_extended_fields()}
        pred = PredictionLog(**kwargs)

        assert pred.catalyst_calendar is not None
        assert len(pred.catalyst_calendar) == 2
        assert pred.catalyst_cluster is not None
        assert pred.catalyst_cluster["density"] == 0.8
        assert pred.scenario_conditions is not None
        assert "bull_requires" in pred.scenario_conditions
        assert pred.short_interest is not None
        assert pred.short_interest["short_ratio"] == 3.2
        assert pred.buyback_support is not None
        assert pred.buyback_support["active"] is True
        assert pred.weighting_mode == "catalyst_adjusted"

    def test_create_without_extended_fields_defaults_to_none(self) -> None:
        """PredictionLog without extended fields has all None defaults (backward compat)."""
        pred = PredictionLog(**_base_prediction_kwargs())

        assert pred.catalyst_calendar is None
        assert pred.catalyst_cluster is None
        assert pred.scenario_conditions is None
        assert pred.short_interest is None
        assert pred.buyback_support is None
        assert pred.weighting_mode is None

    def test_asdict_includes_extended_fields(self) -> None:
        """asdict() serialization includes all extended fields."""
        kwargs = {**_base_prediction_kwargs(), **_extended_fields()}
        pred = PredictionLog(**kwargs)
        data = asdict(pred)

        assert data["catalyst_calendar"] == kwargs["catalyst_calendar"]
        assert data["catalyst_cluster"] == kwargs["catalyst_cluster"]
        assert data["scenario_conditions"] == kwargs["scenario_conditions"]
        assert data["short_interest"] == kwargs["short_interest"]
        assert data["buyback_support"] == kwargs["buyback_support"]
        assert data["weighting_mode"] == kwargs["weighting_mode"]

    def test_asdict_extended_fields_none_when_not_set(self) -> None:
        """asdict() includes extended fields as None when not provided."""
        pred = PredictionLog(**_base_prediction_kwargs())
        data = asdict(pred)

        assert data["catalyst_calendar"] is None
        assert data["catalyst_cluster"] is None
        assert data["scenario_conditions"] is None
        assert data["short_interest"] is None
        assert data["buyback_support"] is None
        assert data["weighting_mode"] is None


# ---------------------------------------------------------------------------
# Test: log_prediction serializes extended fields
# ---------------------------------------------------------------------------


class TestLogPredictionExtended:
    """Tests for log_prediction with extended fields."""

    def test_log_prediction_with_extended_fields(self, tmp_path: Path) -> None:
        """log_prediction writes extended fields to JSON on disk."""
        kwargs = {**_base_prediction_kwargs(), **_extended_fields()}
        pred = PredictionLog(**kwargs)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path)
            path = log_prediction(pred)

        data = orjson.loads(path.read_bytes())
        assert data["catalyst_calendar"] == kwargs["catalyst_calendar"]
        assert data["catalyst_cluster"] == kwargs["catalyst_cluster"]
        assert data["scenario_conditions"] == kwargs["scenario_conditions"]
        assert data["short_interest"] == kwargs["short_interest"]
        assert data["buyback_support"] == kwargs["buyback_support"]
        assert data["weighting_mode"] == kwargs["weighting_mode"]

    def test_log_prediction_with_base_fields_only(self, tmp_path: Path) -> None:
        """log_prediction works with only base fields (extended = None)."""
        pred = PredictionLog(**_base_prediction_kwargs())

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("zaza.utils.predictions.PREDICTIONS_DIR", tmp_path)
            path = log_prediction(pred)

        data = orjson.loads(path.read_bytes())
        assert data["ticker"] == "AAPL"
        assert data["catalyst_calendar"] is None
        assert data["weighting_mode"] is None


# ---------------------------------------------------------------------------
# Test: _load_prediction_files with extended fields
# ---------------------------------------------------------------------------


class TestLoadPredictionFilesExtended:
    """Tests for _load_prediction_files with extended field data."""

    def test_load_file_with_extended_fields(self, tmp_path: Path) -> None:
        """_load_prediction_files loads a file that has extended fields."""
        data = {
            **_base_prediction_kwargs(),
            **_extended_fields(),
            "scored": False,
            "actual_price": None,
        }
        file_path = tmp_path / "AAPL_2026-03-20_5d.json"
        file_path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))

        results = _load_prediction_files(tmp_path, ticker="AAPL")

        assert len(results) == 1
        _, loaded = results[0]
        assert loaded["catalyst_calendar"] is not None
        assert len(loaded["catalyst_calendar"]) == 2
        bull_req = loaded["scenario_conditions"]["bull_requires"]
        assert bull_req == "Price breaks above $190 with volume"
        assert loaded["weighting_mode"] == "catalyst_adjusted"

    def test_load_file_without_extended_fields(self, tmp_path: Path) -> None:
        """_load_prediction_files loads a legacy file without extended fields (backward compat)."""
        data = {**_base_prediction_kwargs(), "scored": False, "actual_price": None}
        # Explicitly ensure no extended fields are present
        for key in ("catalyst_calendar", "catalyst_cluster", "scenario_conditions",
                     "short_interest", "buyback_support", "weighting_mode"):
            data.pop(key, None)

        file_path = tmp_path / "AAPL_2026-03-20_5d.json"
        file_path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))

        results = _load_prediction_files(tmp_path, ticker="AAPL")

        assert len(results) == 1
        _, loaded = results[0]
        assert loaded["ticker"] == "AAPL"
        # Extended fields simply absent from the dict (not errors)
        assert loaded.get("catalyst_calendar") is None
        assert loaded.get("weighting_mode") is None
