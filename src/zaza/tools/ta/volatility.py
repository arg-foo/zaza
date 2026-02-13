"""Volatility indicators MCP tool — Bollinger Bands, ATR."""

from __future__ import annotations

import json

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.indicators import compute_atr, compute_bollinger, ohlcv_to_dataframe

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register volatility indicators tool with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_volatility_indicators(
        ticker: str,
        period: str = "6mo",
    ) -> str:
        """Get volatility indicator analysis for a stock.

        Computes Bollinger Bands(20, 2) and ATR(14).

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
            bollinger_data = compute_bollinger(df)
            atr_value = compute_atr(df)
            current_price = float(df["Close"].iloc[-1])

            # ATR as percentage of price
            atr_pct = round(atr_value / current_price * 100, 2) if atr_value else None

            # Volatility assessment
            if bollinger_data.get("width") is not None:
                width = bollinger_data["width"]
                if width > 0.1:
                    vol_signal = "high_volatility"
                elif width < 0.04:
                    vol_signal = "low_volatility"
                else:
                    vol_signal = "normal_volatility"
            else:
                vol_signal = "insufficient_data"

            return json.dumps({
                "status": "ok",
                "ticker": ticker.upper(),
                "period": period,
                "data": {
                    "bollinger": bollinger_data,
                    "atr": {
                        "atr_14": atr_value,
                        "atr_pct": atr_pct,
                    },
                    "current_price": current_price,
                    "volatility_signal": vol_signal,
                },
            }, default=str)

        except Exception as e:
            logger.warning("get_volatility_error", ticker=ticker, error=str(e))
            return json.dumps({"error": str(e)}, default=str)
