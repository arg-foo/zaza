"""Macro and cross-asset tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from zaza.tools.macro.calendar import register as register_calendar
from zaza.tools.macro.commodities import register as register_commodities
from zaza.tools.macro.correlations import register as register_correlations
from zaza.tools.macro.indices import register as register_indices
from zaza.tools.macro.rates import register as register_rates


def register_macro_tools(mcp: FastMCP) -> None:
    """Register all 5 macro tools with the MCP server."""
    register_rates(mcp)
    register_indices(mcp)
    register_commodities(mcp)
    register_calendar(mcp)
    register_correlations(mcp)
