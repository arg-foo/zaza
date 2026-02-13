"""Price and OHLCV history MCP tools.

Tools:
  - get_price_snapshot: Current price, volume, market cap, and daily change.
  - get_prices: Historical OHLCV records.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def _make_price_snapshot(yf: YFinanceClient, ticker: str) -> str:
    """Build price snapshot JSON from a YFinanceClient instance."""
    try:
        data = yf.get_quote(ticker)
        if not data:
            return json.dumps({"error": f"No data found for ticker {ticker}"})
        result: dict[str, Any] = {
            "ticker": ticker,
            "name": data.get("shortName"),
            "currency": data.get("currency"),
            "price": data.get("regularMarketPrice"),
            "change_pct": data.get("regularMarketChangePercent"),
            "volume": data.get("regularMarketVolume"),
            "market_cap": data.get("marketCap"),
            "fifty_two_week_high": data.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": data.get("fiftyTwoWeekLow"),
            "day_high": data.get("regularMarketDayHigh"),
            "day_low": data.get("regularMarketDayLow"),
            "open": data.get("regularMarketOpen"),
            "previous_close": data.get("regularMarketPreviousClose"),
        }
        return json.dumps(result, default=str)
    except Exception as e:
        logger.error("price_snapshot_error", ticker=ticker, error=str(e))
        return json.dumps({"error": f"Failed to get price snapshot for {ticker}: {e}"})


def _make_prices(
    yf: YFinanceClient,
    ticker: str,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str = "6mo",
) -> str:
    """Build OHLCV prices JSON from a YFinanceClient instance."""
    try:
        records = yf.get_history(
            ticker, period=period, start=start_date, end=end_date,
        )
        if not records:
            return json.dumps({"error": f"No price history found for {ticker}"})
        result: dict[str, Any] = {
            "ticker": ticker,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "record_count": len(records),
            "records": records,
        }
        return json.dumps(result, default=str)
    except Exception as e:
        logger.error("prices_error", ticker=ticker, error=str(e))
        return json.dumps({"error": f"Failed to get prices for {ticker}: {e}"})


def register(mcp: FastMCP) -> None:
    """Register price tools with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_price_snapshot(ticker: str) -> str:
        """Get current price, volume, market cap, and daily change for a stock.

        Returns price, change_pct, volume, market_cap, 52-week high/low, day high/low.
        """
        return _make_price_snapshot(yf, ticker)

    @mcp.tool()
    async def get_prices(
        ticker: str,
        start_date: str | None = None,
        end_date: str | None = None,
        period: str = "6mo",
    ) -> str:
        """Get historical OHLCV price data for a stock.

        Args:
            ticker: Stock ticker symbol.
            start_date: Start date (YYYY-MM-DD). Overrides period if both start and end provided.
            end_date: End date (YYYY-MM-DD). Overrides period if both start and end provided.
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max).
        """
        return _make_prices(yf, ticker, start_date=start_date, end_date=end_date, period=period)
