"""Prediction scoring tool -- reads prediction log, scores past predictions.

Delegates to zaza.utils.predictions.score_predictions() for the actual
scoring logic. Computes directional accuracy, MAE, MAPE, bias, and
range_accuracy. Never cached (always fresh).
"""

from __future__ import annotations

import json

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.config import PREDICTIONS_DIR
from zaza.utils.predictions import score_predictions

logger = structlog.get_logger(__name__)


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
            result = score_predictions(
                ticker=ticker,
                predictions_dir=PREDICTIONS_DIR,
            )
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("prediction_score_error", error=str(e))
            return json.dumps({"error": str(e)}, default=str)
