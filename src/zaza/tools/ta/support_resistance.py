"""Support/resistance MCP tool — pivot points, Fibonacci, 52-week high/low."""

from __future__ import annotations

import json

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.indicators import (
    compute_fibonacci_levels,
    compute_pivot_points,
    ohlcv_to_dataframe,
)

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register support/resistance tool with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_support_resistance(
        ticker: str,
        period: str = "1y",
    ) -> str:
        """Get support and resistance levels for a stock.

        Computes pivot points, Fibonacci retracement levels, and 52-week high/low.

        Args:
            ticker: Stock ticker symbol.
            period: Historical period (default '1y').
        """
        try:
            history = yf.get_history(ticker, period=period)
            if not history:
                return json.dumps(
                    {"error": f"No price history available for {ticker}"},
                    default=str,
                )

            df = ohlcv_to_dataframe(history)
            current_price = float(df["Close"].iloc[-1])

            # Pivot points
            pivot_data = compute_pivot_points(df)

            # Fibonacci levels based on period high/low
            high_52w = float(df["High"].max())
            low_52w = float(df["Low"].min())
            fib_data = compute_fibonacci_levels(high_52w, low_52w)

            # Determine position relative to support/resistance
            if current_price > pivot_data["r1"]:
                position = "above_r1"
            elif current_price > pivot_data["pivot"]:
                position = "above_pivot"
            elif current_price > pivot_data["s1"]:
                position = "below_pivot"
            else:
                position = "below_s1"

            return json.dumps({
                "status": "ok",
                "ticker": ticker.upper(),
                "period": period,
                "data": {
                    "current_price": current_price,
                    "pivot_points": pivot_data,
                    "fibonacci": fib_data,
                    "high_low_52w": {
                        "high": high_52w,
                        "low": low_52w,
                        "pct_from_high": round(
                            (current_price - high_52w) / high_52w * 100, 2
                        ),
                        "pct_from_low": round(
                            (current_price - low_52w) / low_52w * 100, 2
                        ),
                    },
                    "position": position,
                },
            }, default=str)

        except Exception as e:
            logger.warning("get_support_resistance_error", ticker=ticker, error=str(e))
            return json.dumps({"error": str(e)}, default=str)
