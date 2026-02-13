"""Earnings and events tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from zaza.tools.earnings.buybacks import register as register_buybacks
from zaza.tools.earnings.calendar import register as register_calendar
from zaza.tools.earnings.events import register as register_events
from zaza.tools.earnings.history import register as register_history


def register_earnings_tools(mcp: FastMCP) -> None:
    """Register all 4 earnings tools with the MCP server."""
    register_history(mcp)
    register_calendar(mcp)
    register_events(mcp)
    register_buybacks(mcp)
