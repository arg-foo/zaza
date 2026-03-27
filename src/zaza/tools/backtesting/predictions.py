"""Prediction retrieval tools -- reads full prediction data for a ticker.

Delegates to zaza.utils.predictions._load_prediction_files() for loading.
Returns full prediction JSON including catalyst/scenario data. Never cached.

Provides:
  - get_prediction: retrieve latest (or specific) prediction, revision-aware
  - get_prediction_chain: retrieve original + all revisions in order
"""

from __future__ import annotations

import json
import re

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.config import PREDICTIONS_DIR
from zaza.utils.predictions import _load_prediction_files

logger = structlog.get_logger(__name__)


def _sort_key(entry: tuple) -> tuple:
    """Sort key: (prediction_date, revision_number) for descending sort."""
    _, data = entry
    return (
        data.get("prediction_date", ""),
        data.get("revision_number", 0),
    )


def register(mcp: FastMCP) -> None:
    """Register prediction retrieval tools."""

    @mcp.tool()
    async def get_prediction(
        ticker: str,
        prediction_date: str | None = None,
        original_only: bool = False,
    ) -> str:
        """Retrieve full prediction data for a ticker.

        Returns the complete prediction JSON including catalyst_calendar,
        scenario_conditions, key_factors, and predicted_range.

        By default returns the latest revision of the most recent prediction.
        Use original_only=True to skip revisions and get the original prediction.

        Args:
            ticker: Stock symbol.
            prediction_date: Optional ISO date to get a specific prediction.
                           If None, returns the most recent prediction for this ticker.
            original_only: If True, filter out revision entries (is_revision=True).
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

            # Filter out revisions when original_only is requested
            if original_only:
                entries = [
                    (fp, data) for fp, data in entries
                    if not data.get("is_revision", False)
                ]
                if not entries:
                    return json.dumps(
                        {"status": "error", "error": f"No original predictions found for {ticker}"},
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
                # Sort by (prediction_date, revision_number) descending
                matched.sort(key=_sort_key, reverse=True)
                _, prediction_data = matched[0]
            else:
                # Sort by (prediction_date, revision_number) descending
                entries.sort(key=_sort_key, reverse=True)
                _, prediction_data = entries[0]

            return json.dumps(
                {"status": "ok", "data": prediction_data},
                default=str,
            )
        except Exception as e:
            logger.warning("get_prediction_error", error=str(e))
            return json.dumps({"status": "error", "error": str(e)}, default=str)

    @mcp.tool()
    async def get_prediction_chain(
        ticker: str,
        prediction_date: str | None = None,
    ) -> str:
        """Retrieve the full prediction chain: original + all revisions in order.

        Returns the original prediction and all its revisions sorted by
        revision_number ascending. Useful for understanding thesis evolution.

        Args:
            ticker: Stock symbol.
            prediction_date: Optional ISO date to get a specific prediction's chain.
                           If None, returns the chain for the most recent original.
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

            # Find originals (not revisions)
            originals = [
                (fp, data) for fp, data in entries
                if not data.get("is_revision", False)
            ]

            if not originals:
                return json.dumps(
                    {"status": "error", "error": f"No original predictions found for {ticker}"},
                    default=str,
                )

            # Select the target original
            if prediction_date:
                target_originals = [
                    (fp, data) for fp, data in originals
                    if data.get("prediction_date") == prediction_date
                ]
                if not target_originals:
                    return json.dumps(
                        {
                            "status": "error",
                            "error": f"No original prediction found for {ticker} on {prediction_date}",
                        },
                        default=str,
                    )
                # Use the first match (should be unique per date)
                original_fp, original_data = target_originals[0]
            else:
                # Most recent original by prediction_date
                originals.sort(
                    key=lambda x: x[1].get("prediction_date", ""),
                    reverse=True,
                )
                original_fp, original_data = originals[0]

            original_filename = original_fp.name

            # Find all revisions pointing to this original
            revisions = [
                (fp, data) for fp, data in entries
                if data.get("is_revision", False)
                and data.get("parent_prediction") == original_filename
            ]

            # Build chain: original first, then revisions sorted by revision_number
            chain = [
                {
                    "file": original_filename,
                    "revision": 0,
                    "data": original_data,
                }
            ]
            revisions.sort(key=lambda x: x[1].get("revision_number", 0))
            for fp, data in revisions:
                chain.append(
                    {
                        "file": fp.name,
                        "revision": data.get("revision_number", 0),
                        "data": data,
                    }
                )

            return json.dumps(
                {"status": "ok", "ticker": ticker, "chain": chain},
                default=str,
            )
        except Exception as e:
            logger.warning("get_prediction_chain_error", error=str(e))
            return json.dumps({"status": "error", "error": str(e)}, default=str)
