"""Trade plan management tools -- save, load, list, update, archive.

Registers all 5 MCP tools in the trades domain:
  save_trade_plan, get_trade_plan, list_trade_plans,
  update_trade_plan, close_trade_plan
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from zaza.tools.trades.plans import register as register_plans


def register_trades_tools(mcp: FastMCP) -> None:
    """Register all 5 trade plan MCP tools with the server."""
    register_plans(mcp)
