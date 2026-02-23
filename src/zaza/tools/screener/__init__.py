"""Stock screener tools -- yfinance-powered screening with TA scoring."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register_screener_tools(mcp: FastMCP) -> None:
    """Register all screener tools with the MCP server."""
    from zaza.tools.screener.screener import register

    register(mcp)
