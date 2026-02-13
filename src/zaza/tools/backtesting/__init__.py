"""Backtesting and validation tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register_backtesting_tools(mcp: FastMCP) -> None:
    """Register all backtesting tools with the MCP server."""
    from zaza.tools.backtesting.risk import register as register_risk
    from zaza.tools.backtesting.scoring import register as register_scoring
    from zaza.tools.backtesting.signals import register as register_signals
    from zaza.tools.backtesting.simulation import register as register_simulation

    register_signals(mcp)
    register_simulation(mcp)
    register_scoring(mcp)
    register_risk(mcp)
