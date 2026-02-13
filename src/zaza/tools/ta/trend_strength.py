"""Trend strength MCP tool — ADX, +DI/-DI, trend classification."""

from __future__ import annotations

import json

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.indicators import compute_adx, ohlcv_to_dataframe

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register trend strength tool with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_trend_strength(
        ticker: str,
        period: str = "6mo",
    ) -> str:
        """Get trend strength analysis for a stock.

        Computes ADX, +DI/-DI, and classifies trend strength and direction.

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
            adx_data = compute_adx(df)

            # Build summary
            if adx_data.get("adx") is not None:
                adx_val = adx_data["adx"]
                direction = adx_data.get("trend_direction", "unknown")
                strength = adx_data.get("signal", "unknown")
                summary = f"{direction} trend, {strength} (ADX={adx_val})"
            else:
                summary = "insufficient data for trend analysis"

            return json.dumps({
                "status": "ok",
                "ticker": ticker.upper(),
                "period": period,
                "data": {
                    "adx": adx_data,
                    "current_price": float(df["Close"].iloc[-1]),
                    "summary": summary,
                },
            }, default=str)

        except Exception as e:
            logger.warning("get_trend_strength_error", ticker=ticker, error=str(e))
            return json.dumps({"error": str(e)}, default=str)
