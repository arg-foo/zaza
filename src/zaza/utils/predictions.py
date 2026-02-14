"""Prediction logging and self-scoring utilities.

Provides the PredictionLog dataclass for structured prediction storage,
log_prediction() for atomic file writes, score_predictions() for computing
accuracy metrics against actual outcomes, and rotate_logs() for archiving
old prediction files.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import orjson
import structlog

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.config import PREDICTIONS_DIR

logger = structlog.get_logger(__name__)


@dataclass
class PredictionLog:
    """Structured prediction record for logging and scoring.

    Attributes:
        ticker: Stock symbol.
        prediction_date: ISO 8601 date when prediction was made.
        horizon_days: Forecast horizon in calendar days.
        target_date: prediction_date + horizon_days (ISO 8601).
        current_price: Price at prediction time.
        predicted_range: Dict with low, mid, high price targets.
        confidence_interval: Dict with ci_5, ci_25, ci_75, ci_95 bounds.
        model_weights: Signal weights used in the prediction.
        key_factors: Top 3-5 driving factors.
        actual_price: Filled when scoring (None initially).
        scored: Whether this prediction has been scored.
    """

    ticker: str
    prediction_date: str
    horizon_days: int
    target_date: str
    current_price: float
    predicted_range: dict[str, float]
    confidence_interval: dict[str, float]
    model_weights: dict[str, float]
    key_factors: list[str]
    actual_price: float | None = None
    scored: bool = False


def log_prediction(prediction: PredictionLog) -> Path:
    """Write a prediction to disk as human-readable JSON.

    Uses atomic writes (write to temp file, then rename) to prevent
    corruption on failure.

    Args:
        prediction: The PredictionLog to persist.

    Returns:
        Path of the written file.

    Raises:
        OSError: If the write or rename fails.
    """
    predictions_dir = PREDICTIONS_DIR
    predictions_dir.mkdir(parents=True, exist_ok=True)

    filename = (
        f"{prediction.ticker}_{prediction.prediction_date}"
        f"_{prediction.horizon_days}d.json"
    )
    target_path = predictions_dir / filename

    data = asdict(prediction)
    json_bytes = orjson.dumps(data, option=orjson.OPT_INDENT_2)

    # Atomic write: write to temp file in same directory, then rename
    fd = tempfile.NamedTemporaryFile(
        dir=predictions_dir,
        suffix=".tmp",
        delete=False,
    )
    tmp_path = Path(fd.name)
    try:
        fd.write(json_bytes)
        fd.flush()
        os.fsync(fd.fileno())
        fd.close()
        tmp_path.rename(target_path)
        logger.info(
            "prediction_logged",
            ticker=prediction.ticker,
            date=prediction.prediction_date,
            horizon=prediction.horizon_days,
            path=str(target_path),
        )
    except Exception:
        fd.close()
        tmp_path.unlink(missing_ok=True)
        raise

    return target_path


def _load_prediction_files(
    predictions_dir: Path,
    ticker: str | None = None,
) -> list[tuple[Path, dict[str, Any]]]:
    """Load prediction JSON files from disk.

    Returns list of (filepath, data) tuples. Skips corrupt files.
    """
    results: list[tuple[Path, dict[str, Any]]] = []
    if not predictions_dir.exists():
        return results

    for f in sorted(predictions_dir.glob("*.json")):
        try:
            data = orjson.loads(f.read_bytes())
            if ticker and data.get("ticker", "").upper() != ticker.upper():
                continue
            results.append((f, data))
        except (orjson.JSONDecodeError, OSError) as e:
            logger.warning("prediction_load_error", file=str(f), error=str(e))
            continue

    return results


def score_predictions(
    ticker: str | None = None,
    predictions_dir: Path | None = None,
) -> dict[str, Any]:
    """Score predictions: fetch actual prices, compute accuracy metrics.

    For predictions past their target_date that have not been scored yet,
    fetches actual price via yfinance and updates the file on disk.

    Args:
        ticker: Optional ticker to filter predictions. If None, scores all.
        predictions_dir: Directory to read predictions from. Defaults to
                         PREDICTIONS_DIR from config.

    Returns:
        Dict with aggregate metrics and per-prediction details:
        - total_predictions: total count
        - directional_accuracy: % correct direction predictions
        - mae: Mean Absolute Error of mid vs actual
        - mape: Mean Absolute Percentage Error
        - bias: Average signed error (positive = bullish bias)
        - range_accuracy: % of actuals within predicted CI
        - predictions: list of per-prediction detail dicts
    """
    if predictions_dir is None:
        predictions_dir = PREDICTIONS_DIR
    entries = _load_prediction_files(predictions_dir, ticker=ticker)

    if not entries:
        return {
            "total_predictions": 0,
            "directional_accuracy": None,
            "mae": None,
            "mape": None,
            "bias": None,
            "range_accuracy": None,
            "predictions": [],
        }

    today = date.today()
    yf_client: YFinanceClient | None = None
    scored_entries: list[dict[str, Any]] = []

    for filepath, data in entries:
        target_date_str = data.get("target_date", "")
        is_scored = data.get("scored", False)
        actual_price = data.get("actual_price")

        # Try to score unscored predictions that are past target date
        if not is_scored and target_date_str:
            try:
                target_dt = date.fromisoformat(target_date_str)
            except ValueError:
                target_dt = today + timedelta(days=1)  # treat invalid as future

            if target_dt <= today:
                # Need to fetch actual price
                if yf_client is None:
                    yf_client = YFinanceClient(cache=FileCache())

                ticker_sym = data.get("ticker", "")
                quote = yf_client.get_quote(ticker_sym)
                price = quote.get("regularMarketPrice")

                if price is not None:
                    data["actual_price"] = float(price)
                    data["scored"] = True
                    actual_price = float(price)
                    is_scored = True

                    # Update file on disk
                    try:
                        filepath.write_bytes(
                            orjson.dumps(data, option=orjson.OPT_INDENT_2)
                        )
                        logger.info(
                            "prediction_scored",
                            ticker=ticker_sym,
                            actual_price=price,
                            path=str(filepath),
                        )
                    except OSError as e:
                        logger.warning(
                            "prediction_update_failed",
                            path=str(filepath),
                            error=str(e),
                        )

        scored_entries.append({
            "ticker": data.get("ticker"),
            "prediction_date": data.get("prediction_date"),
            "horizon_days": data.get("horizon_days"),
            "target_date": target_date_str,
            "current_price": data.get("current_price"),
            "predicted_range": data.get("predicted_range", {}),
            "confidence_interval": data.get("confidence_interval", {}),
            "actual_price": actual_price,
            "scored": is_scored,
        })

    metrics = _compute_aggregate_metrics(scored_entries)
    metrics["predictions"] = scored_entries
    return metrics


def _compute_aggregate_metrics(
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute aggregate accuracy metrics from scored prediction entries.

    Args:
        entries: List of prediction entry dicts, each with scored, actual_price,
                 current_price, predicted_range, and confidence_interval fields.

    Returns:
        Dict with total_predictions, directional_accuracy, mae, mape, bias,
        and range_accuracy.
    """
    empty_result: dict[str, Any] = {
        "total_predictions": len(entries),
        "directional_accuracy": None,
        "mae": None,
        "mape": None,
        "bias": None,
        "range_accuracy": None,
    }

    scored_only = [
        e for e in entries
        if e.get("scored") and e.get("actual_price") is not None
    ]

    if not scored_only:
        return empty_result

    # Directional accuracy: did we predict the right direction?
    correct_directions = 0
    for entry in scored_only:
        current = entry.get("current_price", 0)
        actual = entry["actual_price"]
        mid = entry.get("predicted_range", {}).get("mid", current)
        predicted_up = mid >= current
        actual_up = actual >= current
        if predicted_up == actual_up:
            correct_directions += 1

    # Error metrics
    abs_errors: list[float] = []
    pct_errors: list[float] = []
    signed_errors: list[float] = []
    within_ci = 0

    for entry in scored_only:
        actual = entry["actual_price"]
        mid = entry.get("predicted_range", {}).get("mid")
        ci = entry.get("confidence_interval", {})
        ci_5 = ci.get("ci_5")
        ci_95 = ci.get("ci_95")

        if mid is not None and actual is not None:
            error = abs(mid - actual)
            abs_errors.append(error)
            signed_errors.append(mid - actual)
            if actual != 0:
                pct_errors.append(error / abs(actual))

        if ci_5 is not None and ci_95 is not None and actual is not None:
            if ci_5 <= actual <= ci_95:
                within_ci += 1

    return {
        "total_predictions": len(entries),
        "directional_accuracy": round(correct_directions / len(scored_only), 4),
        "mae": round(sum(abs_errors) / len(abs_errors), 4) if abs_errors else None,
        "mape": round(sum(pct_errors) / len(pct_errors), 4) if pct_errors else None,
        "bias": round(sum(signed_errors) / len(signed_errors), 4) if signed_errors else None,
        "range_accuracy": round(within_ci / len(scored_only), 4),
    }


def rotate_logs(
    predictions_dir: Path,
    archive_dir: Path | None = None,
) -> int:
    """Move prediction files older than 1 year to archive directory.

    Args:
        predictions_dir: Directory containing prediction JSON files.
        archive_dir: Destination for archived files. Defaults to
                     predictions_dir / "archive".

    Returns:
        Number of files archived.
    """
    if not predictions_dir.exists():
        return 0

    if archive_dir is None:
        archive_dir = predictions_dir / "archive"

    cutoff = date.today() - timedelta(days=365)
    archived = 0

    for f in list(predictions_dir.glob("*.json")):
        try:
            data = orjson.loads(f.read_bytes())
            pred_date_str = data.get("prediction_date", "")
            pred_date = date.fromisoformat(pred_date_str)
        except (orjson.JSONDecodeError, ValueError, OSError):
            continue

        if pred_date < cutoff:
            archive_dir.mkdir(parents=True, exist_ok=True)
            dest = archive_dir / f.name
            shutil.move(str(f), str(dest))
            archived += 1
            logger.info("prediction_archived", file=f.name, dest=str(dest))

    return archived
