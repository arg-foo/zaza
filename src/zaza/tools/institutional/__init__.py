"""Institutional flow tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from zaza.tools.institutional.dark_pool import register as register_dark_pool
from zaza.tools.institutional.flows import register as register_flows
from zaza.tools.institutional.holdings import register as register_holdings
from zaza.tools.institutional.short_interest import register as register_short_interest


def register_institutional_tools(mcp: FastMCP) -> None:
    """Register all 4 institutional tools with the MCP server."""
    register_short_interest(mcp)
    register_holdings(mcp)
    register_flows(mcp)
    register_dark_pool(mcp)
