"""Buyback data tool."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register buyback data tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_buyback_data(ticker: str) -> str:
        """Get share buyback data including repurchase amounts and buyback yield.

        Combines quote data (shares outstanding, market cap) with cash flow
        statement data (stock repurchases, issuances) to compute net buyback metrics.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
        """
        cache_key = cache.make_key("buyback_data", ticker=ticker)
        cached = cache.get(cache_key, "buyback_data")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            quote = yf.get_quote(ticker)
            if not quote or "regularMarketPrice" not in quote:
                return json.dumps(
                    {"status": "error", "error": f"No quote data for {ticker}"}
                )

            market_cap = quote.get("marketCap", 0)
            shares_outstanding = quote.get("sharesOutstanding", 0)
            float_shares = quote.get("floatShares", 0)

            # Get cash flow data for buyback information
            financials = yf.get_financials(ticker, period="annual")
            cash_flow = financials.get("cash_flow", [])

            if not cash_flow and not shares_outstanding:
                return json.dumps(
                    {"status": "error", "error": f"No buyback data available for {ticker}"}
                )

            # Extract repurchase data from cash flow statements
            buyback_periods: list[dict[str, Any]] = []
            total_repurchase = 0.0
            total_issuance = 0.0

            for period_data in cash_flow:
                repurchase = period_data.get("Repurchase Of Capital Stock", 0) or 0
                issuance = period_data.get("Issuance Of Capital Stock", 0) or 0

                # Repurchase is typically negative (cash outflow)
                repurchase_abs = abs(float(repurchase))
                issuance_val = float(issuance)

                net_buyback = repurchase_abs - issuance_val
                total_repurchase += repurchase_abs
                total_issuance += issuance_val

                buyback_periods.append({
                    "repurchase": round(repurchase_abs, 0),
                    "issuance": round(issuance_val, 0),
                    "net_buyback": round(net_buyback, 0),
                })

            # Compute buyback yield (annual repurchase / market cap)
            avg_annual_repurchase = (
                total_repurchase / len(cash_flow) if cash_flow else 0
            )
            buyback_yield = (
                round(avg_annual_repurchase / market_cap * 100, 2)
                if market_cap and market_cap > 0
                else None
            )

            net_buyback = total_repurchase - total_issuance

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "shares_outstanding": shares_outstanding,
                    "float_shares": float_shares,
                    "market_cap": market_cap,
                    "total_repurchase": round(total_repurchase, 0),
                    "total_issuance": round(total_issuance, 0),
                    "net_buyback": round(net_buyback, 0),
                    "buyback_yield": buyback_yield,
                    "periods": buyback_periods,
                },
            }
            cache.set(cache_key, "buyback_data", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("buyback_data_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
