"""Financial ratios MCP tools.

Tools:
  - get_key_ratios_snapshot: Current P/E, EV/EBITDA, ROE, margins, dividend yield.
  - get_key_ratios: Historical ratios computed from financial statements.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def _safe_divide(numerator: Any, denominator: Any) -> float | None:
    """Safely divide two numbers, returning None on error or zero denominator."""
    try:
        if numerator is None or denominator is None:
            return None
        if denominator == 0:
            return None
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _make_key_ratios_snapshot(yf: YFinanceClient, ticker: str) -> str:
    """Build key ratios snapshot JSON from current quote data."""
    try:
        data = yf.get_quote(ticker)
        if not data:
            return json.dumps({"error": f"No data found for ticker {ticker}"})

        result: dict[str, Any] = {
            "ticker": ticker,
            "valuation": {
                "trailing_pe": data.get("trailingPE"),
                "forward_pe": data.get("forwardPE"),
                "price_to_book": data.get("priceToBook"),
                "price_to_sales": data.get("priceToSalesTrailing12Months"),
                "ev_to_ebitda": data.get("enterpriseToEbitda"),
                "ev_to_revenue": data.get("enterpriseToRevenue"),
            },
            "profitability": {
                "return_on_equity": data.get("returnOnEquity"),
                "return_on_assets": data.get("returnOnAssets"),
                "gross_margin": data.get("grossMargins"),
                "operating_margin": data.get("operatingMargins"),
                "profit_margin": data.get("profitMargins"),
            },
            "growth": {
                "earnings_growth": data.get("earningsGrowth"),
                "revenue_growth": data.get("revenueGrowth"),
            },
            "dividends": {
                "dividend_yield": data.get("dividendYield"),
                "payout_ratio": data.get("payoutRatio"),
            },
            "leverage": {
                "debt_to_equity": data.get("debtToEquity"),
                "current_ratio": data.get("currentRatio"),
                "quick_ratio": data.get("quickRatio"),
            },
        }
        return json.dumps(result, default=str)
    except Exception as e:
        logger.error("key_ratios_snapshot_error", ticker=ticker, error=str(e))
        return json.dumps({"error": f"Failed to get ratios for {ticker}: {e}"})


def _make_key_ratios(
    yf: YFinanceClient, ticker: str, period: str, limit: int,
) -> str:
    """Build historical computed ratios JSON from financial statements."""
    try:
        data = yf.get_financials(ticker, period=period)
        income_records = data.get("income_statement", [])
        balance_records = data.get("balance_sheet", [])
        cashflow_records = data.get("cash_flow", [])

        if not income_records:
            return json.dumps({"error": f"No financial data available for {ticker}"})

        ratios_list: list[dict[str, Any]] = []
        for i, income in enumerate(income_records[:limit]):
            revenue = income.get("Total Revenue") or income.get("TotalRevenue")
            gross_profit = income.get("Gross Profit") or income.get("GrossProfit")
            operating_income = (
                income.get("Operating Income")
                or income.get("OperatingIncome")
                or income.get("EBIT")
            )
            net_income = income.get("Net Income") or income.get("NetIncome")

            ratio_entry: dict[str, Any] = {
                "date": income.get("index") or income.get("Date"),
                "gross_margin": _safe_divide(gross_profit, revenue),
                "operating_margin": _safe_divide(operating_income, revenue),
                "net_margin": _safe_divide(net_income, revenue),
            }

            # Add balance sheet ratios if available for same period
            if i < len(balance_records):
                bs = balance_records[i]
                equity = (
                    bs.get("Stockholders Equity")
                    or bs.get("StockholdersEquity")
                )
                total_assets = bs.get("Total Assets") or bs.get("TotalAssets")
                total_debt = bs.get("Total Debt") or bs.get("TotalDebt")
                current_assets = (
                    bs.get("Current Assets") or bs.get("CurrentAssets")
                )
                current_liabilities = (
                    bs.get("Current Liabilities") or bs.get("CurrentLiabilities")
                )

                ratio_entry["return_on_equity"] = _safe_divide(net_income, equity)
                ratio_entry["return_on_assets"] = _safe_divide(net_income, total_assets)
                ratio_entry["debt_to_equity"] = _safe_divide(total_debt, equity)
                ratio_entry["current_ratio"] = _safe_divide(
                    current_assets, current_liabilities,
                )
            else:
                ratio_entry["return_on_equity"] = None
                ratio_entry["return_on_assets"] = None
                ratio_entry["debt_to_equity"] = None
                ratio_entry["current_ratio"] = None

            # Add FCF margin if available
            if i < len(cashflow_records):
                cf = cashflow_records[i]
                fcf = cf.get("Free Cash Flow") or cf.get("FreeCashFlow")
                ratio_entry["fcf_margin"] = _safe_divide(fcf, revenue)
            else:
                ratio_entry["fcf_margin"] = None

            ratios_list.append(ratio_entry)

        return json.dumps({
            "ticker": ticker,
            "period": period,
            "ratio_count": len(ratios_list),
            "ratios": ratios_list,
        }, default=str)
    except Exception as e:
        logger.error("key_ratios_error", ticker=ticker, error=str(e))
        return json.dumps({"error": f"Failed to compute ratios for {ticker}: {e}"})


def register(mcp: FastMCP) -> None:
    """Register financial ratio tools with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_key_ratios_snapshot(ticker: str) -> str:
        """Get current key financial ratios from quote data.

        Returns P/E, EV/EBITDA, ROE, margins, dividend yield, and leverage ratios.
        """
        return _make_key_ratios_snapshot(yf, ticker)

    @mcp.tool()
    async def get_key_ratios(
        ticker: str, period: str = "annual", limit: int = 5,
    ) -> str:
        """Get historical financial ratios computed from statements.

        Computes margins, ROE, ROA, debt/equity, current ratio, and FCF margin
        from income statements, balance sheets, and cash flow data.

        Args:
            ticker: Stock ticker symbol.
            period: 'annual' or 'quarterly'.
            limit: Maximum number of periods to return (default 5).
        """
        return _make_key_ratios(yf, ticker, period, limit)
