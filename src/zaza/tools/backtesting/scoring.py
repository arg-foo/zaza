"""Prediction scoring tool -- reads prediction log, scores past predictions.

Reads JSON prediction files from PREDICTIONS_DIR, computes directional accuracy,
MAE, and bias. Never cached (always fresh).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.config import PREDICTIONS_DIR

logger = structlog.get_logger(__name__)


def _load_predictions(
    predictions_dir: Path, ticker: str | None = None
) -> list[dict[str, Any]]:
    """Load prediction JSON files from the predictions directory."""
    predictions: list[dict[str, Any]] = []
    if not predictions_dir.exists():
        return predictions

    for f in predictions_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if ticker and data.get("ticker", "").upper() != ticker.upper():
                continue
            predictions.append(data)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("prediction_load_error", file=str(f), error=str(e))
            continue

    return predictions


def _score_predictions(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    """Score a list of predictions computing accuracy, MAE, and bias."""
    if not predictions:
        return {
            "total_predictions": 0,
            "directional_accuracy": None,
            "mae": None,
            "bias": None,
            "predictions": [],
        }

    scored: list[dict[str, Any]] = []
    correct_directions = 0
    errors: list[float] = []
    biases: list[float] = []

    for p in predictions:
        predicted_price = p.get("predicted_price")
        actual_price = p.get("actual_price")
        predicted_direction = p.get("predicted_direction")
        actual_direction = p.get("actual_direction")

        entry: dict[str, Any] = {
            "ticker": p.get("ticker"),
            "date": p.get("date"),
        }

        if predicted_direction and actual_direction:
            is_correct = predicted_direction.lower() == actual_direction.lower()
            correct_directions += int(is_correct)
            entry["direction_correct"] = is_correct

        if predicted_price is not None and actual_price is not None:
            try:
                pred = float(predicted_price)
                actual = float(actual_price)
                error = abs(pred - actual)
                bias = pred - actual
                errors.append(error)
                biases.append(bias)
                entry["error"] = round(error, 4)
                entry["bias"] = round(bias, 4)
            except (TypeError, ValueError):
                pass

        scored.append(entry)

    dir_accuracy = (
        round(correct_directions / len(predictions), 4) if predictions else None
    )
    mae = round(float(np.mean(errors)), 4) if errors else None
    avg_bias = round(float(np.mean(biases)), 4) if biases else None

    return {
        "total_predictions": len(predictions),
        "directional_accuracy": dir_accuracy,
        "mae": mae,
        "bias": avg_bias,
        "predictions": scored,
    }


def register(mcp: FastMCP) -> None:
    """Register the prediction scoring tool."""

    @mcp.tool()
    async def get_prediction_score(
        ticker: str | None = None,
    ) -> str:
        """Score past predictions from the prediction log.

        Reads prediction files from the predictions directory and computes
        directional accuracy, MAE, and bias.

        Args:
            ticker: Optional ticker to filter predictions. If None, scores all.

        Returns:
            JSON with directional accuracy, MAE, bias, and per-prediction details.
        """
        try:
            predictions = _load_predictions(PREDICTIONS_DIR, ticker=ticker)
            result = _score_predictions(predictions)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("prediction_score_error", error=str(e))
            return json.dumps({"error": str(e)}, default=str)
