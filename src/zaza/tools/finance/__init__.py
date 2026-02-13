"""Financial data tools -- prices, statements, ratios, filings, news.

Registers all 13 MCP tools in the finance domain:
  TASK-012: get_price_snapshot, get_prices, get_company_facts,
            get_company_news, get_insider_trades
  TASK-013: get_income_statements, get_balance_sheets, get_cash_flow_statements,
            get_all_financial_statements, get_key_ratios_snapshot, get_key_ratios,
            get_analyst_estimates, get_segmented_revenues
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from zaza.tools.finance.estimates import register as register_estimates
from zaza.tools.finance.facts import register as register_facts
from zaza.tools.finance.insider import register as register_insider
from zaza.tools.finance.news import register as register_news
from zaza.tools.finance.prices import register as register_prices
from zaza.tools.finance.ratios import register as register_ratios
from zaza.tools.finance.segments import register as register_segments
from zaza.tools.finance.statements import register as register_statements


def register_finance_tools(mcp: FastMCP) -> None:
    """Register all 13 finance MCP tools with the server."""
    register_prices(mcp)
    register_facts(mcp)
    register_news(mcp)
    register_insider(mcp)
    register_statements(mcp)
    register_ratios(mcp)
    register_estimates(mcp)
    register_segments(mcp)
