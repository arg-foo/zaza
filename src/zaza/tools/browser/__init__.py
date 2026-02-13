"""Browser automation tools -- Playwright integration."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register_browser_tools(mcp: FastMCP) -> None:
    """Register all browser tools with the MCP server."""
    from zaza.tools.browser.actions import register

    register(mcp)
