"""Volume analysis MCP tool — OBV, VWAP, volume trend."""

from __future__ import annotations

import json

import numpy as np
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.indicators import compute_obv, compute_vwap, ohlcv_to_dataframe

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register volume analysis tool with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_volume_analysis(
        ticker: str,
        period: str = "6mo",
    ) -> str:
        """Get volume analysis for a stock.

        Computes OBV, VWAP, and volume trend (20-day average vs current).

        Args:
            ticker: Stock ticker symbol.
            period: Historical period (default '6mo').
        """
        try:
            history = yf.get_history(ticker, period=period)
            if not history:
                return json.dumps(
                    {"error": f"No price history available for {ticker}"},
                    default=str,
                )

            df = ohlcv_to_dataframe(history)
            obv_data = compute_obv(df)
            vwap_value = compute_vwap(df)

            # Volume trend analysis
            volumes = df["Volume"].values
            current_vol = float(volumes[-1])
            if len(volumes) >= 20:
                avg_vol_20 = float(np.mean(volumes[-20:]))
            else:
                avg_vol_20 = float(np.mean(volumes))
            avg_vol_50 = float(np.mean(volumes[-50:])) if len(volumes) >= 50 else None

            vol_ratio = current_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0

            if vol_ratio > 1.5:
                direction = "increasing"
            elif vol_ratio < 0.5:
                direction = "decreasing"
            else:
                direction = "stable"

            return json.dumps({
                "status": "ok",
                "ticker": ticker.upper(),
                "period": period,
                "data": {
                    "obv": obv_data,
                    "vwap": vwap_value,
                    "volume_trend": {
                        "current_volume": current_vol,
                        "avg_volume_20d": round(avg_vol_20, 0),
                        "avg_volume_50d": round(avg_vol_50, 0) if avg_vol_50 else None,
                        "volume_ratio": round(vol_ratio, 2),
                        "direction": direction,
                    },
                    "current_price": float(df["Close"].iloc[-1]),
                },
            }, default=str)

        except Exception as e:
            logger.warning("get_volume_error", ticker=ticker, error=str(e))
            return json.dumps({"error": str(e)}, default=str)
