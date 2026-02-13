"""Technical analysis tools — 9 MCP tools for price and volume analysis."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register_ta_tools(mcp: FastMCP) -> None:
    """Register all 9 technical analysis tools with the MCP server."""
    from zaza.tools.ta.momentum import register as register_momentum
    from zaza.tools.ta.money_flow import register as register_money_flow
    from zaza.tools.ta.moving_averages import register as register_moving_averages
    from zaza.tools.ta.patterns import register as register_patterns
    from zaza.tools.ta.relative import register as register_relative
    from zaza.tools.ta.support_resistance import register as register_support_resistance
    from zaza.tools.ta.trend_strength import register as register_trend_strength
    from zaza.tools.ta.volatility import register as register_volatility
    from zaza.tools.ta.volume import register as register_volume

    register_moving_averages(mcp)
    register_momentum(mcp)
    register_volatility(mcp)
    register_volume(mcp)
    register_support_resistance(mcp)
    register_trend_strength(mcp)
    register_patterns(mcp)
    register_money_flow(mcp)
    register_relative(mcp)
