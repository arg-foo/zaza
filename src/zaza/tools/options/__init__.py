"""Options and derivatives tools.

Provides 7 MCP tools for options analysis:
- get_options_expirations: list expiry dates
- get_options_chain: full chain data
- get_implied_volatility: ATM IV, IV rank, skew
- get_options_flow: unusual activity detection
- get_put_call_ratio: P/C by volume and OI
- get_max_pain: max pain calculation
- get_gamma_exposure: net GEX by strike
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.tools.options.chain import register as register_chain
from zaza.tools.options.flow import register as register_flow
from zaza.tools.options.levels import register as register_levels
from zaza.tools.options.volatility import register as register_volatility


def register_options_tools(mcp: FastMCP) -> None:
    """Register all 7 options tools on the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    register_chain(mcp, yf, cache)
    register_volatility(mcp, yf, cache)
    register_flow(mcp, yf, cache)
    register_levels(mcp, yf, cache)
