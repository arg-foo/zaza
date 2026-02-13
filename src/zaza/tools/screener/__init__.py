"""Stock screener tools -- PKScreener Docker integration."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register_screener_tools(mcp: FastMCP) -> None:
    """Register all screener tools with the MCP server."""
    from zaza.tools.screener.pkscreener import register

    register(mcp)
