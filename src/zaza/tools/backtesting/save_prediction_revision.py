"""Save prediction revision tool -- persists a revised prediction to disk.

Accepts a ticker, parent prediction filename, and prediction data JSON string.
Validates inputs, inherits dates from the parent prediction, auto-increments
the revision number, and writes atomically to PREDICTIONS_DIR.
"""

from __future__ import annotations

import json
import re
from datetime import date
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

# Matches original prediction filenames: TICKER_DATE_Nd.json
# Must NOT match revision filenames (which have _rN suffix).
_PARENT_FILENAME_RE = re.compile(
    r"^([A-Z]{1,10})_(\d{4}-\d{2}-\d{2})_(\d+)d\.json$"
)

# Matches revision filenames: TICKER_DATE_Nd_rN.json
_REVISION_FILENAME_RE = re.compile(
    r"^([A-Z]{1,10})_(\d{4}-\d{2}-\d{2})_(\d+)d_r(\d+)\.json$"
)


def register(mcp: FastMCP) -> None:
    """Register the save_prediction_revision tool."""

    @mcp.tool()
    async def save_prediction_revision(
        ticker: str,
        parent_prediction: str,
        prediction_data: str,
    ) -> str:
        """Save a prediction revision to disk as a JSON file.

        Creates a new revision that references an original prediction,
        inheriting its prediction_date, target_date, and horizon_days.
        Revision numbers auto-increment. Revisions cannot chain --
        the parent must always be an original prediction.

        Args:
            ticker: Stock symbol (1-10 letters, auto-uppercased).
            parent_prediction: Filename of the original prediction
                (e.g. "GLNG_2026-03-23_10d.json"). Must exist on disk
                and must not itself be a revision.
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

            # --- Validate parent_prediction format ---
            if not parent_prediction:
                return json.dumps(
                    {
                        "status": "error",
                        "error": "parent_prediction is required",
                    },
                    default=str,
                )

            # Reject revision filenames as parent (no chaining)
            if _REVISION_FILENAME_RE.match(parent_prediction):
                return json.dumps(
                    {
                        "status": "error",
                        "error": (
                            "Cannot use a revision as parent_prediction. "
                            "Revisions must always reference the original prediction."
                        ),
                    },
                    default=str,
                )

            parent_match = _PARENT_FILENAME_RE.match(parent_prediction)
            if not parent_match:
                return json.dumps(
                    {
                        "status": "error",
                        "error": (
                            f"Invalid parent_prediction format: {parent_prediction}. "
                            f"Expected TICKER_DATE_Nd.json"
                        ),
                    },
                    default=str,
                )

            # --- Validate ticker vs parent filename match (1.2) ---
            parent_ticker = parent_match.group(1)
            if parent_ticker != normalized_ticker:
                return json.dumps(
                    {
                        "status": "error",
                        "error": (
                            f"Ticker mismatch: {normalized_ticker} vs "
                            f"parent {parent_ticker}"
                        ),
                    },
                    default=str,
                )

            # --- Validate parent exists on disk ---
            predictions_dir = PREDICTIONS_DIR
            predictions_dir.mkdir(parents=True, exist_ok=True)

            parent_path = predictions_dir / parent_prediction

            # Defence-in-depth: ensure resolved path stays inside predictions_dir
            if not parent_path.resolve().is_relative_to(
                predictions_dir.resolve()
            ):
                return json.dumps(
                    {
                        "status": "error",
                        "error": "Invalid parent_prediction path",
                    },
                    default=str,
                )

            if not parent_path.exists():
                return json.dumps(
                    {
                        "status": "error",
                        "error": (
                            f"Parent prediction file not found: {parent_prediction}"
                        ),
                    },
                    default=str,
                )

            # --- Load parent to inherit fields ---
            parent_data = orjson.loads(parent_path.read_bytes())
            orig_date = parent_match.group(2)
            horizon = int(parent_match.group(3))

            inherited_prediction_date = parent_data.get(
                "prediction_date", orig_date
            )
            inherited_target_date = parent_data.get("target_date")
            inherited_horizon = parent_data.get("horizon_days", horizon)

            # Guard against missing required inherited fields
            if not all(
                [inherited_prediction_date, inherited_target_date, inherited_horizon]
            ):
                return json.dumps(
                    {
                        "status": "error",
                        "error": "Parent prediction missing required fields",
                    },
                    default=str,
                )

            # --- Determine next revision number ---
            prefix = f"{normalized_ticker}_{orig_date}_{horizon}d_r"
            existing_revisions: list[int] = []
            for f in predictions_dir.iterdir():
                if f.name.startswith(prefix) and f.name.endswith(".json"):
                    rev_match = _REVISION_FILENAME_RE.match(f.name)
                    if rev_match:
                        existing_revisions.append(int(rev_match.group(4)))

            next_revision = max(existing_revisions, default=0) + 1

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

            data.update(
                {
                    "ticker": normalized_ticker,
                    "prediction_date": inherited_prediction_date,
                    "horizon_days": inherited_horizon,
                    "target_date": inherited_target_date,
                    "is_revision": True,
                    "revision_number": next_revision,
                    "parent_prediction": parent_prediction,
                    "revision_date": today.isoformat(),
                    "scored": False,
                    "actual_price": None,
                }
            )

            # --- Atomic write ---
            filename = (
                f"{normalized_ticker}_{orig_date}_{horizon}d_r{next_revision}.json"
            )
            target_path = predictions_dir / filename

            json_bytes = orjson.dumps(data, option=orjson.OPT_INDENT_2)

            _atomic_write(target_path, json_bytes)

            logger.info(
                "prediction_revision_saved",
                ticker=normalized_ticker,
                parent=parent_prediction,
                revision=next_revision,
                path=str(target_path),
            )

            return json.dumps(
                {
                    "status": "ok",
                    "file": filename,
                    "revision_number": next_revision,
                    "path": str(target_path),
                },
                default=str,
            )

        except Exception as e:
            logger.warning("save_prediction_revision_error", error=str(e))
            return json.dumps(
                {"status": "error", "error": str(e)},
                default=str,
            )
