"""Financial statements MCP tools.

Tools:
  - get_income_statements: Revenue, gross profit, operating income, net income, EPS.
  - get_balance_sheets: Assets, liabilities, equity, debt, cash.
  - get_cash_flow_statements: Operating, investing, financing, FCF.
  - get_all_financial_statements: Combined view of all three.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def _safe_get(record: dict[str, Any], *keys: str) -> Any:
    """Try multiple key names, returning the first found value or None."""
    for key in keys:
        if key in record:
            return record[key]
    return None


def _extract_income(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Extract standardized income statement fields from raw records."""
    statements: list[dict[str, Any]] = []
    for record in records[:limit]:
        statements.append({
            "date": _safe_get(record, "index", "Date"),
            "total_revenue": _safe_get(record, "Total Revenue", "TotalRevenue"),
            "gross_profit": _safe_get(record, "Gross Profit", "GrossProfit"),
            "operating_income": _safe_get(
                record, "Operating Income", "OperatingIncome",
                "EBIT", "Ebit",
            ),
            "net_income": _safe_get(record, "Net Income", "NetIncome"),
            "basic_eps": _safe_get(record, "Basic EPS", "BasicEPS", "Diluted EPS"),
            "ebitda": _safe_get(record, "EBITDA", "Ebitda"),
            "research_development": _safe_get(
                record, "Research Development", "ResearchDevelopment",
                "Research And Development",
            ),
        })
    return statements


def _extract_balance(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Extract standardized balance sheet fields from raw records."""
    statements: list[dict[str, Any]] = []
    for record in records[:limit]:
        statements.append({
            "date": _safe_get(record, "index", "Date"),
            "total_assets": _safe_get(record, "Total Assets", "TotalAssets"),
            "total_liabilities": _safe_get(
                record,
                "Total Liabilities Net Minority Interest",
                "TotalLiabilitiesNetMinorityInterest",
                "Total Liab",
            ),
            "stockholders_equity": _safe_get(
                record, "Stockholders Equity", "StockholdersEquity",
                "Total Stockholders Equity",
            ),
            "total_debt": _safe_get(record, "Total Debt", "TotalDebt"),
            "cash_and_equivalents": _safe_get(
                record,
                "Cash And Cash Equivalents",
                "CashAndCashEquivalents",
                "Cash",
            ),
            "net_debt": _safe_get(record, "Net Debt", "NetDebt"),
            "current_assets": _safe_get(record, "Current Assets", "CurrentAssets"),
            "current_liabilities": _safe_get(
                record, "Current Liabilities", "CurrentLiabilities",
            ),
        })
    return statements


def _extract_cashflow(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Extract standardized cash flow fields from raw records."""
    statements: list[dict[str, Any]] = []
    for record in records[:limit]:
        statements.append({
            "date": _safe_get(record, "index", "Date"),
            "operating_cash_flow": _safe_get(
                record, "Operating Cash Flow", "OperatingCashFlow",
                "Total Cash From Operating Activities",
            ),
            "capital_expenditure": _safe_get(
                record, "Capital Expenditure", "CapitalExpenditure",
            ),
            "free_cash_flow": _safe_get(record, "Free Cash Flow", "FreeCashFlow"),
            "investing_cash_flow": _safe_get(
                record, "Investing Cash Flow", "InvestingCashFlow",
                "Total Cashflows From Investing Activities",
            ),
            "financing_cash_flow": _safe_get(
                record, "Financing Cash Flow", "FinancingCashFlow",
                "Total Cash From Financing Activities",
            ),
        })
    return statements


def _make_income_statements(
    yf: YFinanceClient, ticker: str, period: str, limit: int,
) -> str:
    """Build income statements JSON from a YFinanceClient instance."""
    try:
        data = yf.get_financials(ticker, period=period)
        records = data.get("income_statement", [])
        if not records:
            return json.dumps({"error": f"No income statement data for {ticker}"})
        statements = _extract_income(records, limit)
        return json.dumps({
            "ticker": ticker,
            "period": period,
            "statement_count": len(statements),
            "statements": statements,
        }, default=str)
    except Exception as e:
        logger.error("income_statements_error", ticker=ticker, error=str(e))
        return json.dumps({"error": f"Failed to get income statements for {ticker}: {e}"})


def _make_balance_sheets(
    yf: YFinanceClient, ticker: str, period: str, limit: int,
) -> str:
    """Build balance sheets JSON from a YFinanceClient instance."""
    try:
        data = yf.get_financials(ticker, period=period)
        records = data.get("balance_sheet", [])
        if not records:
            return json.dumps({"error": f"No balance sheet data for {ticker}"})
        statements = _extract_balance(records, limit)
        return json.dumps({
            "ticker": ticker,
            "period": period,
            "statement_count": len(statements),
            "statements": statements,
        }, default=str)
    except Exception as e:
        logger.error("balance_sheets_error", ticker=ticker, error=str(e))
        return json.dumps({"error": f"Failed to get balance sheets for {ticker}: {e}"})


def _make_cash_flow_statements(
    yf: YFinanceClient, ticker: str, period: str, limit: int,
) -> str:
    """Build cash flow statements JSON from a YFinanceClient instance."""
    try:
        data = yf.get_financials(ticker, period=period)
        records = data.get("cash_flow", [])
        if not records:
            return json.dumps({"error": f"No cash flow data for {ticker}"})
        statements = _extract_cashflow(records, limit)
        return json.dumps({
            "ticker": ticker,
            "period": period,
            "statement_count": len(statements),
            "statements": statements,
        }, default=str)
    except Exception as e:
        logger.error("cash_flow_error", ticker=ticker, error=str(e))
        return json.dumps({"error": f"Failed to get cash flow for {ticker}: {e}"})


def _make_all_financial_statements(
    yf: YFinanceClient, ticker: str, period: str, limit: int,
) -> str:
    """Build combined financial statements JSON from a YFinanceClient instance."""
    try:
        data = yf.get_financials(ticker, period=period)
        income_records = data.get("income_statement", [])
        balance_records = data.get("balance_sheet", [])
        cashflow_records = data.get("cash_flow", [])

        if not income_records and not balance_records and not cashflow_records:
            return json.dumps({"error": f"No financial data available for {ticker}"})

        income_stmts = _extract_income(income_records, limit)
        balance_stmts = _extract_balance(balance_records, limit)
        cashflow_stmts = _extract_cashflow(cashflow_records, limit)

        return json.dumps({
            "ticker": ticker,
            "period": period,
            "income_statements": income_stmts,
            "balance_sheets": balance_stmts,
            "cash_flow_statements": cashflow_stmts,
        }, default=str)
    except Exception as e:
        logger.error("all_statements_error", ticker=ticker, error=str(e))
        return json.dumps({"error": f"Failed to get financial statements for {ticker}: {e}"})


def register(mcp: FastMCP) -> None:
    """Register financial statement tools with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_income_statements(
        ticker: str, period: str = "annual", limit: int = 5,
    ) -> str:
        """Get income statements for a company.

        Returns revenue, gross profit, operating income, net income, EPS, and EBITDA.

        Args:
            ticker: Stock ticker symbol.
            period: 'annual' or 'quarterly'.
            limit: Maximum number of periods to return (default 5).
        """
        return _make_income_statements(yf, ticker, period, limit)

    @mcp.tool()
    async def get_balance_sheets(
        ticker: str, period: str = "annual", limit: int = 5,
    ) -> str:
        """Get balance sheets for a company.

        Returns total assets, liabilities, equity, debt, cash, and current ratio components.

        Args:
            ticker: Stock ticker symbol.
            period: 'annual' or 'quarterly'.
            limit: Maximum number of periods to return (default 5).
        """
        return _make_balance_sheets(yf, ticker, period, limit)

    @mcp.tool()
    async def get_cash_flow_statements(
        ticker: str, period: str = "annual", limit: int = 5,
    ) -> str:
        """Get cash flow statements for a company.

        Returns operating, investing, and financing cash flows plus free cash flow.

        Args:
            ticker: Stock ticker symbol.
            period: 'annual' or 'quarterly'.
            limit: Maximum number of periods to return (default 5).
        """
        return _make_cash_flow_statements(yf, ticker, period, limit)

    @mcp.tool()
    async def get_all_financial_statements(
        ticker: str, period: str = "annual", limit: int = 5,
    ) -> str:
        """Get all financial statements (income, balance sheet, cash flow) in one call.

        Args:
            ticker: Stock ticker symbol.
            period: 'annual' or 'quarterly'.
            limit: Maximum number of periods to return (default 5).
        """
        return _make_all_financial_statements(yf, ticker, period, limit)
