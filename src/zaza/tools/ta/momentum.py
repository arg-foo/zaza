"""Momentum indicators MCP tool — RSI, MACD, Stochastic."""

from __future__ import annotations

import json

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.indicators import (
    compute_macd,
    compute_rsi,
    compute_stochastic,
    ohlcv_to_dataframe,
)

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register momentum indicators tool with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_momentum_indicators(
        ticker: str,
        period: str = "6mo",
    ) -> str:
        """Get momentum indicator analysis for a stock.

        Computes RSI(14), MACD(12,26,9), and Stochastic %K/%D.

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
            rsi_data = compute_rsi(df)
            macd_data = compute_macd(df)
            stoch_data = compute_stochastic(df)

            # Build overall momentum assessment
            bullish_count = 0
            bearish_count = 0
            for indicator_data in [rsi_data, macd_data, stoch_data]:
                sig = indicator_data.get("signal", "")
                if "bullish" in sig or sig == "oversold":
                    bullish_count += 1
                elif "bearish" in sig or sig == "overbought":
                    bearish_count += 1

            if bullish_count > bearish_count:
                overall = "bullish"
            elif bearish_count > bullish_count:
                overall = "bearish"
            else:
                overall = "neutral"

            return json.dumps({
                "status": "ok",
                "ticker": ticker.upper(),
                "period": period,
                "data": {
                    "rsi": rsi_data,
                    "macd": macd_data,
                    "stochastic": stoch_data,
                    "overall_momentum": overall,
                },
            }, default=str)

        except Exception as e:
            logger.warning("get_momentum_error", ticker=ticker, error=str(e))
            return json.dumps({"error": str(e)}, default=str)
