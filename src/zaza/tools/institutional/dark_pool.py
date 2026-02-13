"""Dark pool activity estimation tool."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)

# Typical off-exchange trading percentage for US equities (30-40%)
TYPICAL_OFF_EXCHANGE_PCT = 0.35


def register(mcp: FastMCP) -> None:
    """Register dark pool activity tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_dark_pool_activity(ticker: str) -> str:
        """Estimate dark pool / off-exchange trading activity for a ticker.

        Uses volume anomaly detection as a heuristic proxy since actual dark pool
        data requires paid FINRA ADF feeds. Compares recent volume patterns to
        historical averages to estimate off-exchange activity.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
        """
        cache_key = cache.make_key("dark_pool", ticker=ticker)
        cached = cache.get(cache_key, "dark_pool")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            quote = yf.get_quote(ticker)
            if not quote or "regularMarketPrice" not in quote:
                return json.dumps(
                    {"status": "error", "error": f"No data available for {ticker}"}
                )

            current_volume = float(quote.get("regularMarketVolume", 0) or 0)
            avg_volume = float(quote.get("averageVolume", 0) or 0)
            avg_volume_10d = float(quote.get("averageVolume10days", 0) or 0)

            if avg_volume == 0 and current_volume == 0:
                return json.dumps(
                    {"status": "error", "error": f"No volume data for {ticker}"}
                )

            # Get recent history for volume analysis
            history = yf.get_history(ticker, period="1mo")
            volumes = [
                r.get("Volume", 0) for r in history if r.get("Volume") is not None
            ]

            # Volume-based heuristics for off-exchange estimation
            volume_ratio = (
                current_volume / avg_volume if avg_volume > 0 else 1.0
            )

            # Estimate off-exchange percentage
            # Base is market average (~35%), adjusted for volume anomalies
            # Higher volume anomalies suggest more institutional/dark pool activity
            base_off_exchange = TYPICAL_OFF_EXCHANGE_PCT

            if volume_ratio > 2.0:
                # Very high volume may indicate more dark pool activity
                off_exchange_adj = base_off_exchange + 0.10
            elif volume_ratio > 1.5:
                off_exchange_adj = base_off_exchange + 0.05
            elif volume_ratio < 0.5:
                # Low volume may indicate less institutional interest
                off_exchange_adj = base_off_exchange - 0.05
            else:
                off_exchange_adj = base_off_exchange

            estimated_off_exchange = min(max(off_exchange_adj, 0.15), 0.60)

            # Volume statistics
            vol_stats: dict[str, Any] = {}
            if volumes:
                vol_array = np.array(volumes, dtype=float)
                vol_stats = {
                    "avg_volume_1mo": int(np.mean(vol_array)),
                    "max_volume_1mo": int(np.max(vol_array)),
                    "min_volume_1mo": int(np.min(vol_array)),
                    "volume_std": int(np.std(vol_array)),
                }

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "estimated_off_exchange_pct": round(estimated_off_exchange, 4),
                    "current_volume": int(current_volume),
                    "average_volume": int(avg_volume),
                    "average_volume_10d": int(avg_volume_10d),
                    "volume_ratio": round(volume_ratio, 4),
                    "volume_stats": vol_stats,
                    "note": (
                        "Estimated using volume heuristics."
                        " Actual dark pool data requires FINRA ADF feed."
                    ),
                },
            }
            cache.set(cache_key, "dark_pool", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("dark_pool_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
