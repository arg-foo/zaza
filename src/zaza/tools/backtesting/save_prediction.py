"""Save prediction tool -- persists prediction data to disk as JSON.

Accepts a ticker, horizon, and prediction data JSON string. Validates
inputs, auto-populates derived fields, and writes atomically to
PREDICTIONS_DIR.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

import orjson
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.config import PREDICTIONS_DIR
from zaza.utils.predictions import _atomic_write

logger = structlog.get_logger(__name__)

_REQUIRED_KEYS = frozenset(
    {
        "current_price",
        "predicted_range",
        "confidence_interval",
        "model_weights",
        "key_factors",
    }
)


def register(mcp: FastMCP) -> None:
    """Register the save_prediction tool."""

    @mcp.tool()
    async def save_prediction(
        ticker: str,
        horizon_days: int,
        prediction_data: str,
    ) -> str:
        """Save a prediction to disk as a JSON file.

        Validates inputs, auto-populates derived fields (dates, scored
        status), and writes atomically using temp-file-then-rename.

        Args:
            ticker: Stock symbol (1-10 letters, auto-uppercased).
            horizon_days: Forecast horizon in calendar days.
            prediction_data: JSON string with required keys: current_price,
                predicted_range, confidence_interval, model_weights,
                key_factors. Extra keys are preserved.
        """
        try:
            # --- Validate ticker ---
            normalized_ticker = ticker.upper()
            if not re.match(r"^[A-Z]{1,10}$", normalized_ticker, re.ASCII):
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Invalid ticker format: {ticker}",
                    },
                    default=str,
                )

            # --- Validate horizon_days ---
            if not (1 <= horizon_days <= 365):
                return json.dumps(
                    {
                        "status": "error",
                        "error": (
                            f"horizon_days must be between 1 and 365, "
                            f"got {horizon_days}"
                        ),
                    },
                    default=str,
                )

            # --- Parse prediction_data JSON ---
            try:
                data = json.loads(prediction_data)
            except (json.JSONDecodeError, TypeError) as e:
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Invalid JSON in prediction_data: {e}",
                    },
                    default=str,
                )

            # --- Validate prediction_data is a dict ---
            if not isinstance(data, dict):
                return json.dumps(
                    {
                        "status": "error",
                        "error": "prediction_data must be a JSON object",
                    },
                    default=str,
                )

            # --- Validate required keys ---
            missing = _REQUIRED_KEYS - set(data.keys())
            if missing:
                return json.dumps(
                    {
                        "status": "error",
                        "error": (
                            f"Missing required keys in prediction_data: "
                            f"{sorted(missing)}"
                        ),
                    },
                    default=str,
                )

            # --- Auto-populate derived fields ---
            today = date.today()
            target_date = today + timedelta(days=horizon_days)

            data.update(
                {
                    "ticker": normalized_ticker,
                    "prediction_date": today.isoformat(),
                    "horizon_days": horizon_days,
                    "target_date": target_date.isoformat(),
                    "scored": False,
                    "actual_price": None,
                }
            )

            # --- Atomic write ---
            predictions_dir = PREDICTIONS_DIR
            predictions_dir.mkdir(parents=True, exist_ok=True)

            filename = (
                f"{normalized_ticker}_{today.isoformat()}_{horizon_days}d.json"
            )
            target_path = predictions_dir / filename

            json_bytes = orjson.dumps(data, option=orjson.OPT_INDENT_2)

            _atomic_write(target_path, json_bytes)

            logger.info(
                "prediction_saved",
                ticker=normalized_ticker,
                date=today.isoformat(),
                horizon=horizon_days,
                path=str(target_path),
            )

            return json.dumps(
                {
                    "status": "ok",
                    "file": filename,
                    "path": str(target_path),
                },
                default=str,
            )

        except Exception as e:
            logger.warning("save_prediction_error", error=str(e))
            return json.dumps(
                {"status": "error", "error": str(e)},
                default=str,
            )
