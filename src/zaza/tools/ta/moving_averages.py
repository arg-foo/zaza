"""Moving averages MCP tool — SMA, EMA, golden/death cross."""

from __future__ import annotations

import json

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.indicators import compute_ema, compute_sma, ohlcv_to_dataframe

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register moving averages tool with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_moving_averages(
        ticker: str,
        period: str = "6mo",
    ) -> str:
        """Get moving average analysis for a stock.

        Computes SMA(20, 50, 200), EMA(12, 26), and golden/death cross signals.

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
            sma_data = compute_sma(df, [20, 50, 200])
            ema_data = compute_ema(df, [12, 26])

            result = {
                "status": "ok",
                "ticker": ticker.upper(),
                "period": period,
                "data": {
                    "current_price": sma_data["current_price"],
                    "sma": sma_data["sma"],
                    "ema": ema_data,
                },
            }

            # Include cross signal if available
            if "cross" in sma_data:
                result["data"]["cross"] = sma_data["cross"]

            # Generate summary signal
            signals = []
            for key in ["sma_20", "sma_50", "sma_200"]:
                pos = sma_data["sma"].get(f"price_vs_{key}")
                if pos:
                    signals.append(f"Price {pos} {key.upper()}")

            result["data"]["summary"] = "; ".join(signals) if signals else "insufficient data"

            return json.dumps(result, default=str)

        except Exception as e:
            logger.warning("get_moving_averages_error", ticker=ticker, error=str(e))
            return json.dumps({"error": str(e)}, default=str)
