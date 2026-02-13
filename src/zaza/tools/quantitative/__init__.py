"""Quantitative model tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from zaza.tools.quantitative.distribution import register as register_distribution
from zaza.tools.quantitative.forecast import register as register_forecast
from zaza.tools.quantitative.mean_reversion import register as register_mean_reversion
from zaza.tools.quantitative.monte_carlo import register as register_monte_carlo
from zaza.tools.quantitative.regime import register as register_regime
from zaza.tools.quantitative.volatility import register as register_volatility


def register_quantitative_tools(mcp: FastMCP) -> None:
    """Register all 6 quantitative tools with the MCP server."""
    register_forecast(mcp)
    register_volatility(mcp)
    register_monte_carlo(mcp)
    register_distribution(mcp)
    register_mean_reversion(mcp)
    register_regime(mcp)
