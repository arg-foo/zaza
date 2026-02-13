"""Options chain and expiration tools."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP, yf: YFinanceClient, cache: FileCache) -> None:
    """Register options chain tools on the MCP server."""

    @mcp.tool()
    async def get_options_expirations(ticker: str) -> str:
        """List available options expiration dates for a ticker.

        Returns a JSON object with ticker, expirations list, and count.
        """
        try:
            expirations = yf.get_options_expirations(ticker.upper())
            result: dict[str, Any] = {
                "ticker": ticker.upper(),
                "expirations": expirations,
                "count": len(expirations),
            }
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("get_options_expirations_error", ticker=ticker, error=str(e))
            return json.dumps({"error": f"Failed to get expirations for {ticker}: {e}"})

    @mcp.tool()
    async def get_options_chain(ticker: str, expiration_date: str) -> str:
        """Get full options chain (calls and puts) for a ticker and expiration date.

        Returns calls and puts with strike, last price, bid, ask, volume,
        open interest, and implied volatility.
        """
        try:
            chain = yf.get_options_chain(ticker.upper(), expiration_date)
            result: dict[str, Any] = {
                "ticker": ticker.upper(),
                "expiration_date": expiration_date,
                "calls": chain.get("calls", []),
                "puts": chain.get("puts", []),
                "call_count": len(chain.get("calls", [])),
                "put_count": len(chain.get("puts", [])),
            }
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("get_options_chain_error", ticker=ticker, error=str(e))
            return json.dumps({"error": f"Failed to get options chain for {ticker}: {e}"})
