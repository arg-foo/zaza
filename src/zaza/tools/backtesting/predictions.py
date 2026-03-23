"""Prediction retrieval tool -- reads full prediction data for a ticker.

Delegates to zaza.utils.predictions._load_prediction_files() for loading.
Returns full prediction JSON including catalyst/scenario data. Never cached.
"""

from __future__ import annotations

import json
import re

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.config import PREDICTIONS_DIR
from zaza.utils.predictions import _load_prediction_files

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register the prediction retrieval tool."""

    @mcp.tool()
    async def get_prediction(
        ticker: str,
        prediction_date: str | None = None,
    ) -> str:
        """Retrieve full prediction data for a ticker.

        Returns the complete prediction JSON including catalyst_calendar,
        scenario_conditions, key_factors, and predicted_range.

        Args:
            ticker: Stock symbol.
            prediction_date: Optional ISO date to get a specific prediction.
                           If None, returns the most recent prediction for this ticker.
        """
        if not re.match(r"^[A-Z]{1,10}$", ticker.upper()):
            return json.dumps(
                {"status": "error", "error": f"Invalid ticker format: {ticker}"},
                default=str,
            )
        ticker = ticker.upper()

        try:
            entries = _load_prediction_files(PREDICTIONS_DIR, ticker=ticker)
            if not entries:
                return json.dumps(
                    {"status": "error", "error": f"No predictions found for {ticker}"},
                    default=str,
                )

            if prediction_date:
                # Filter by specific date
                matched = [
                    (fp, data) for fp, data in entries
                    if data.get("prediction_date") == prediction_date
                ]
                if not matched:
                    return json.dumps(
                        {
                            "status": "error",
                            "error": f"No prediction found for {ticker} on {prediction_date}",
                        },
                        default=str,
                    )
                _, prediction_data = matched[0]
            else:
                # Sort by prediction_date descending, return most recent
                entries.sort(
                    key=lambda x: x[1].get("prediction_date", ""),
                    reverse=True,
                )
                _, prediction_data = entries[0]

            return json.dumps(
                {"status": "ok", "data": prediction_data},
                default=str,
            )
        except Exception as e:
            logger.warning("get_prediction_error", error=str(e))
            return json.dumps({"status": "error", "error": str(e)}, default=str)
