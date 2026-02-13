"""Tests for Phase 3 finance tools (TASK-012 + TASK-013).

Tests all 13 MCP tools:
  TASK-012: get_price_snapshot, get_prices, get_company_facts_tool,
            get_company_news, get_insider_trades
  TASK-013: get_income_statements, get_balance_sheets, get_cash_flow_statements,
            get_all_financial_statements, get_key_ratios_snapshot, get_key_ratios,
            get_analyst_estimates, get_segmented_revenues
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zaza.cache.store import FileCache

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cache(tmp_path):
    """Create a temporary FileCache for test isolation."""
    return FileCache(cache_dir=tmp_path)


@pytest.fixture
def mock_yf_client(cache):
    """Create a mocked YFinanceClient."""
    from zaza.api.yfinance_client import YFinanceClient

    client = YFinanceClient(cache)
    return client


@pytest.fixture
def mock_edgar_client(cache):
    """Create a mocked EdgarClient."""
    from zaza.api.edgar_client import EdgarClient

    client = EdgarClient(cache)
    return client


# ---------------------------------------------------------------------------
# Sample data factories
# ---------------------------------------------------------------------------

def _sample_quote() -> dict:
    return {
        "regularMarketPrice": 185.50,
        "regularMarketChangePercent": 1.25,
        "regularMarketVolume": 52_000_000,
        "marketCap": 2_900_000_000_000,
        "fiftyTwoWeekHigh": 199.62,
        "fiftyTwoWeekLow": 164.08,
        "regularMarketDayHigh": 186.10,
        "regularMarketDayLow": 184.20,
        "regularMarketOpen": 184.80,
        "regularMarketPreviousClose": 183.22,
        "shortName": "Apple Inc.",
        "currency": "USD",
    }


def _sample_history() -> list[dict]:
    return [
        {
            "Date": "2024-01-02",
            "Open": 185.0,
            "High": 186.5,
            "Low": 184.0,
            "Close": 185.5,
            "Volume": 45_000_000,
        },
        {
            "Date": "2024-01-03",
            "Open": 185.5,
            "High": 187.0,
            "Low": 184.5,
            "Close": 186.0,
            "Volume": 48_000_000,
        },
    ]


def _sample_financials() -> dict:
    return {
        "income_statement": [
            {
                "index": "2024-09-28",
                "Total Revenue": 394_000_000_000,
                "Gross Profit": 178_000_000_000,
                "Operating Income": 123_000_000_000,
                "Net Income": 97_000_000_000,
                "Basic EPS": 6.42,
                "EBITDA": 134_000_000_000,
                "Research Development": 30_000_000_000,
            },
        ],
        "balance_sheet": [
            {
                "index": "2024-09-28",
                "Total Assets": 353_000_000_000,
                "Total Liabilities Net Minority Interest": 290_000_000_000,
                "Stockholders Equity": 63_000_000_000,
                "Total Debt": 111_000_000_000,
                "Cash And Cash Equivalents": 30_000_000_000,
                "Net Debt": 81_000_000_000,
                "Current Assets": 153_000_000_000,
                "Current Liabilities": 154_000_000_000,
            },
        ],
        "cash_flow": [
            {
                "index": "2024-09-28",
                "Operating Cash Flow": 118_000_000_000,
                "Capital Expenditure": -11_000_000_000,
                "Free Cash Flow": 107_000_000_000,
                "Investing Cash Flow": -3_000_000_000,
                "Financing Cash Flow": -110_000_000_000,
            },
        ],
    }


def _sample_info_with_ratios() -> dict:
    return {
        "regularMarketPrice": 185.50,
        "trailingPE": 30.5,
        "forwardPE": 28.2,
        "priceToBook": 48.7,
        "priceToSalesTrailing12Months": 7.8,
        "enterpriseToEbitda": 22.1,
        "enterpriseToRevenue": 7.5,
        "returnOnEquity": 1.56,
        "returnOnAssets": 0.28,
        "grossMargins": 0.452,
        "operatingMargins": 0.312,
        "profitMargins": 0.246,
        "dividendYield": 0.005,
        "payoutRatio": 0.155,
        "debtToEquity": 176.3,
        "currentRatio": 0.99,
        "quickRatio": 0.95,
        "earningsGrowth": 0.108,
        "revenueGrowth": 0.05,
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "fullTimeEmployees": 164000,
        "exchange": "NMS",
        "website": "https://www.apple.com",
        "longBusinessSummary": "Apple designs and sells consumer electronics.",
        "marketCap": 2_900_000_000_000,
        "shortName": "Apple Inc.",
    }


def _sample_insider_transactions() -> list[dict]:
    return [
        {
            "Insider": "Tim Cook",
            "Start Date": "2024-04-01",
            "Transaction": "Sale",
            "Shares": 50000,
            "Value": 9250000,
            "URL": "https://www.sec.gov/...",
        },
        {
            "Insider": "Luca Maestri",
            "Start Date": "2024-03-15",
            "Transaction": "Sale",
            "Shares": 20000,
            "Value": 3700000,
            "URL": "https://www.sec.gov/...",
        },
    ]


def _sample_news() -> list[dict]:
    return [
        {
            "title": "Apple beats earnings expectations",
            "publisher": "Reuters",
            "link": "https://reuters.com/apple-earnings",
            "providerPublishTime": 1706600000,
            "type": "STORY",
        },
        {
            "title": "Apple Vision Pro launches",
            "publisher": "Bloomberg",
            "link": "https://bloomberg.com/apple-vision-pro",
            "providerPublishTime": 1706500000,
            "type": "STORY",
        },
    ]


def _sample_earnings() -> dict:
    return {
        "targetMeanPrice": 210.0,
        "targetHighPrice": 250.0,
        "targetLowPrice": 170.0,
        "targetMedianPrice": 205.0,
        "numberOfAnalystOpinions": 40,
        "recommendationKey": "buy",
        "recommendationMean": 2.0,
        "currentPrice": 185.50,
    }


def _sample_company_facts_xbrl() -> dict:
    return {
        "entityName": "APPLE INC",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "label": "Revenue",
                    "units": {
                        "USD": [
                            {
                                "val": 394_000_000_000,
                                "end": "2024-09-28",
                                "fy": 2024,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2024-11-01",
                                "accn": "0000320193-24-000123",
                                "frame": "CY2024",
                            }
                        ]
                    },
                },
                "Revenues": {
                    "label": "Revenues",
                    "units": {
                        "USD": [
                            {
                                "val": 100_000_000_000,
                                "end": "2024-09-28",
                                "fy": 2024,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2024-11-01",
                                "accn": "0000320193-24-000123",
                                "segment": "us-gaap:ProductMember",
                                "frame": "CY2024",
                            },
                            {
                                "val": 85_000_000_000,
                                "end": "2024-09-28",
                                "fy": 2024,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2024-11-01",
                                "accn": "0000320193-24-000123",
                                "segment": "us-gaap:ServiceMember",
                                "frame": "CY2024",
                            },
                        ]
                    },
                },
            }
        },
    }


# ===========================================================================
# TASK-012: Prices & Company Tools
# ===========================================================================


# ---------------------------------------------------------------------------
# get_price_snapshot
# ---------------------------------------------------------------------------


class TestGetPriceSnapshot:
    """Tests for the get_price_snapshot MCP tool."""

    @patch("zaza.tools.finance.prices.YFinanceClient")
    def test_returns_valid_json(self, MockYFClient, cache):
        """get_price_snapshot returns valid JSON with expected fields."""
        mock_instance = MagicMock()
        mock_instance.get_quote.return_value = _sample_quote()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.prices import _make_price_snapshot

        result = _make_price_snapshot(mock_instance, "AAPL")
        parsed = json.loads(result)

        assert parsed["ticker"] == "AAPL"
        assert parsed["price"] == 185.50
        assert parsed["change_pct"] == 1.25
        assert parsed["volume"] == 52_000_000
        assert parsed["market_cap"] == 2_900_000_000_000
        assert parsed["fifty_two_week_high"] == 199.62
        assert parsed["fifty_two_week_low"] == 164.08
        assert parsed["day_high"] == 186.10
        assert parsed["day_low"] == 184.20

    @patch("zaza.tools.finance.prices.YFinanceClient")
    def test_invalid_ticker_returns_error(self, MockYFClient, cache):
        """get_price_snapshot returns an error JSON for an unknown ticker."""
        mock_instance = MagicMock()
        mock_instance.get_quote.return_value = {}
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.prices import _make_price_snapshot

        result = _make_price_snapshot(mock_instance, "INVALID")
        parsed = json.loads(result)
        assert "error" in parsed

    @patch("zaza.tools.finance.prices.YFinanceClient")
    def test_includes_name_and_currency(self, MockYFClient, cache):
        """get_price_snapshot includes shortName and currency."""
        mock_instance = MagicMock()
        mock_instance.get_quote.return_value = _sample_quote()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.prices import _make_price_snapshot

        result = _make_price_snapshot(mock_instance, "AAPL")
        parsed = json.loads(result)
        assert parsed["name"] == "Apple Inc."
        assert parsed["currency"] == "USD"


# ---------------------------------------------------------------------------
# get_prices
# ---------------------------------------------------------------------------


class TestGetPrices:
    """Tests for the get_prices MCP tool."""

    @patch("zaza.tools.finance.prices.YFinanceClient")
    def test_returns_valid_json_with_records(self, MockYFClient, cache):
        """get_prices returns valid JSON with OHLCV records."""
        mock_instance = MagicMock()
        mock_instance.get_history.return_value = _sample_history()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.prices import _make_prices

        result = _make_prices(mock_instance, "AAPL", period="6mo")
        parsed = json.loads(result)
        assert parsed["ticker"] == "AAPL"
        assert len(parsed["records"]) == 2
        assert parsed["record_count"] == 2

    @patch("zaza.tools.finance.prices.YFinanceClient")
    def test_returns_empty_for_no_data(self, MockYFClient, cache):
        """get_prices returns error when no records found."""
        mock_instance = MagicMock()
        mock_instance.get_history.return_value = []
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.prices import _make_prices

        result = _make_prices(mock_instance, "INVALID")
        parsed = json.loads(result)
        assert "error" in parsed

    @patch("zaza.tools.finance.prices.YFinanceClient")
    def test_passes_start_end_dates(self, MockYFClient, cache):
        """get_prices passes start_date and end_date to the client."""
        mock_instance = MagicMock()
        mock_instance.get_history.return_value = _sample_history()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.prices import _make_prices

        _make_prices(
            mock_instance, "AAPL",
            start_date="2024-01-01", end_date="2024-06-30",
        )
        mock_instance.get_history.assert_called_once_with(
            "AAPL", period="6mo", start="2024-01-01", end="2024-06-30",
        )


# ---------------------------------------------------------------------------
# get_company_facts (tool)
# ---------------------------------------------------------------------------


class TestGetCompanyFacts:
    """Tests for the get_company_facts MCP tool."""

    @patch("zaza.tools.finance.facts.YFinanceClient")
    def test_returns_company_info(self, MockYFClient, cache):
        """get_company_facts returns sector, industry, employees, etc."""
        mock_instance = MagicMock()
        mock_instance.get_quote.return_value = _sample_info_with_ratios()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.facts import _make_company_facts

        result = _make_company_facts(mock_instance, "AAPL")
        parsed = json.loads(result)
        assert parsed["ticker"] == "AAPL"
        assert parsed["sector"] == "Technology"
        assert parsed["industry"] == "Consumer Electronics"
        assert parsed["employees"] == 164000
        assert parsed["exchange"] == "NMS"
        assert parsed["website"] == "https://www.apple.com"
        assert "Apple" in parsed["description"]
        assert parsed["market_cap"] == 2_900_000_000_000

    @patch("zaza.tools.finance.facts.YFinanceClient")
    def test_invalid_ticker_returns_error(self, MockYFClient, cache):
        """get_company_facts returns error for invalid ticker."""
        mock_instance = MagicMock()
        mock_instance.get_quote.return_value = {}
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.facts import _make_company_facts

        result = _make_company_facts(mock_instance, "INVALID")
        parsed = json.loads(result)
        assert "error" in parsed

    @patch("zaza.tools.finance.facts.YFinanceClient")
    def test_handles_missing_fields_gracefully(self, MockYFClient, cache):
        """get_company_facts returns None for missing optional fields."""
        mock_instance = MagicMock()
        mock_instance.get_quote.return_value = {
            "regularMarketPrice": 100.0,
            "shortName": "Test Corp",
        }
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.facts import _make_company_facts

        result = _make_company_facts(mock_instance, "TEST")
        parsed = json.loads(result)
        assert parsed["ticker"] == "TEST"
        assert parsed["sector"] is None
        assert parsed["industry"] is None


# ---------------------------------------------------------------------------
# get_company_news
# ---------------------------------------------------------------------------


class TestGetCompanyNews:
    """Tests for the get_company_news MCP tool."""

    @patch("zaza.tools.finance.news.YFinanceClient")
    def test_returns_news_articles(self, MockYFClient, cache):
        """get_company_news returns list of news articles."""
        mock_instance = MagicMock()
        mock_instance.get_news.return_value = _sample_news()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.news import _make_company_news

        result = _make_company_news(mock_instance, "AAPL")
        parsed = json.loads(result)
        assert parsed["ticker"] == "AAPL"
        assert len(parsed["articles"]) == 2
        assert parsed["articles"][0]["title"] == "Apple beats earnings expectations"

    @patch("zaza.tools.finance.news.YFinanceClient")
    def test_empty_news_returns_message(self, MockYFClient, cache):
        """get_company_news returns informative message when no news available."""
        mock_instance = MagicMock()
        mock_instance.get_news.return_value = []
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.news import _make_company_news

        result = _make_company_news(mock_instance, "OBSCURE")
        parsed = json.loads(result)
        assert parsed["ticker"] == "OBSCURE"
        assert parsed["articles"] == []
        assert parsed["article_count"] == 0

    @patch("zaza.tools.finance.news.YFinanceClient")
    def test_returns_valid_json(self, MockYFClient, cache):
        """get_company_news always returns valid JSON."""
        mock_instance = MagicMock()
        mock_instance.get_news.return_value = _sample_news()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.news import _make_company_news

        result = _make_company_news(mock_instance, "AAPL")
        # Should not raise
        json.loads(result)


# ---------------------------------------------------------------------------
# get_insider_trades
# ---------------------------------------------------------------------------


class TestGetInsiderTrades:
    """Tests for the get_insider_trades MCP tool."""

    @patch("zaza.tools.finance.insider.YFinanceClient")
    def test_returns_insider_trades(self, MockYFClient, cache):
        """get_insider_trades returns list of insider transactions."""
        mock_instance = MagicMock()
        mock_instance.get_insider_transactions.return_value = _sample_insider_transactions()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.insider import _make_insider_trades

        result = _make_insider_trades(mock_instance, "AAPL")
        parsed = json.loads(result)
        assert parsed["ticker"] == "AAPL"
        assert len(parsed["transactions"]) == 2
        assert parsed["transactions"][0]["Insider"] == "Tim Cook"

    @patch("zaza.tools.finance.insider.YFinanceClient")
    def test_empty_insider_trades(self, MockYFClient, cache):
        """get_insider_trades returns empty list for tickers with no insider data."""
        mock_instance = MagicMock()
        mock_instance.get_insider_transactions.return_value = []
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.insider import _make_insider_trades

        result = _make_insider_trades(mock_instance, "OBSCURE")
        parsed = json.loads(result)
        assert parsed["ticker"] == "OBSCURE"
        assert parsed["transactions"] == []
        assert parsed["transaction_count"] == 0

    @patch("zaza.tools.finance.insider.YFinanceClient")
    def test_returns_valid_json(self, MockYFClient, cache):
        """get_insider_trades always returns valid JSON."""
        mock_instance = MagicMock()
        mock_instance.get_insider_transactions.return_value = _sample_insider_transactions()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.insider import _make_insider_trades

        result = _make_insider_trades(mock_instance, "AAPL")
        json.loads(result)


# ===========================================================================
# TASK-013: Statements & Ratios Tools
# ===========================================================================


# ---------------------------------------------------------------------------
# get_income_statements
# ---------------------------------------------------------------------------


class TestGetIncomeStatements:
    """Tests for the get_income_statements MCP tool."""

    @patch("zaza.tools.finance.statements.YFinanceClient")
    def test_returns_income_data(self, MockYFClient, cache):
        """get_income_statements returns income statement records."""
        mock_instance = MagicMock()
        mock_instance.get_financials.return_value = _sample_financials()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.statements import _make_income_statements

        result = _make_income_statements(mock_instance, "AAPL", "annual", 5)
        parsed = json.loads(result)
        assert parsed["ticker"] == "AAPL"
        assert parsed["period"] == "annual"
        assert len(parsed["statements"]) == 1
        stmt = parsed["statements"][0]
        assert stmt["total_revenue"] == 394_000_000_000
        assert stmt["net_income"] == 97_000_000_000

    @patch("zaza.tools.finance.statements.YFinanceClient")
    def test_empty_returns_error(self, MockYFClient, cache):
        """get_income_statements returns error when no data available."""
        mock_instance = MagicMock()
        mock_instance.get_financials.return_value = {
            "income_statement": [], "balance_sheet": [], "cash_flow": []
        }
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.statements import _make_income_statements

        result = _make_income_statements(mock_instance, "INVALID", "annual", 5)
        parsed = json.loads(result)
        assert "error" in parsed

    @patch("zaza.tools.finance.statements.YFinanceClient")
    def test_respects_limit(self, MockYFClient, cache):
        """get_income_statements respects the limit parameter."""
        mock_instance = MagicMock()
        financials = _sample_financials()
        financials["income_statement"] = financials["income_statement"] * 5
        mock_instance.get_financials.return_value = financials
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.statements import _make_income_statements

        result = _make_income_statements(mock_instance, "AAPL", "annual", 2)
        parsed = json.loads(result)
        assert len(parsed["statements"]) == 2


# ---------------------------------------------------------------------------
# get_balance_sheets
# ---------------------------------------------------------------------------


class TestGetBalanceSheets:
    """Tests for the get_balance_sheets MCP tool."""

    @patch("zaza.tools.finance.statements.YFinanceClient")
    def test_returns_balance_sheet_data(self, MockYFClient, cache):
        """get_balance_sheets returns balance sheet records."""
        mock_instance = MagicMock()
        mock_instance.get_financials.return_value = _sample_financials()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.statements import _make_balance_sheets

        result = _make_balance_sheets(mock_instance, "AAPL", "annual", 5)
        parsed = json.loads(result)
        assert parsed["ticker"] == "AAPL"
        assert len(parsed["statements"]) == 1
        stmt = parsed["statements"][0]
        assert stmt["total_assets"] == 353_000_000_000
        assert stmt["total_debt"] == 111_000_000_000

    @patch("zaza.tools.finance.statements.YFinanceClient")
    def test_empty_returns_error(self, MockYFClient, cache):
        """get_balance_sheets returns error when no data available."""
        mock_instance = MagicMock()
        mock_instance.get_financials.return_value = {
            "income_statement": [], "balance_sheet": [], "cash_flow": []
        }
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.statements import _make_balance_sheets

        result = _make_balance_sheets(mock_instance, "INVALID", "annual", 5)
        parsed = json.loads(result)
        assert "error" in parsed

    @patch("zaza.tools.finance.statements.YFinanceClient")
    def test_respects_limit(self, MockYFClient, cache):
        """get_balance_sheets respects the limit parameter."""
        mock_instance = MagicMock()
        financials = _sample_financials()
        financials["balance_sheet"] = financials["balance_sheet"] * 5
        mock_instance.get_financials.return_value = financials
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.statements import _make_balance_sheets

        result = _make_balance_sheets(mock_instance, "AAPL", "annual", 3)
        parsed = json.loads(result)
        assert len(parsed["statements"]) == 3


# ---------------------------------------------------------------------------
# get_cash_flow_statements
# ---------------------------------------------------------------------------


class TestGetCashFlowStatements:
    """Tests for the get_cash_flow_statements MCP tool."""

    @patch("zaza.tools.finance.statements.YFinanceClient")
    def test_returns_cash_flow_data(self, MockYFClient, cache):
        """get_cash_flow_statements returns cash flow records."""
        mock_instance = MagicMock()
        mock_instance.get_financials.return_value = _sample_financials()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.statements import _make_cash_flow_statements

        result = _make_cash_flow_statements(mock_instance, "AAPL", "annual", 5)
        parsed = json.loads(result)
        assert parsed["ticker"] == "AAPL"
        assert len(parsed["statements"]) == 1
        stmt = parsed["statements"][0]
        assert stmt["operating_cash_flow"] == 118_000_000_000
        assert stmt["free_cash_flow"] == 107_000_000_000

    @patch("zaza.tools.finance.statements.YFinanceClient")
    def test_empty_returns_error(self, MockYFClient, cache):
        """get_cash_flow_statements returns error when no data available."""
        mock_instance = MagicMock()
        mock_instance.get_financials.return_value = {
            "income_statement": [], "balance_sheet": [], "cash_flow": []
        }
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.statements import _make_cash_flow_statements

        result = _make_cash_flow_statements(mock_instance, "INVALID", "annual", 5)
        parsed = json.loads(result)
        assert "error" in parsed

    @patch("zaza.tools.finance.statements.YFinanceClient")
    def test_respects_limit(self, MockYFClient, cache):
        """get_cash_flow_statements respects the limit parameter."""
        mock_instance = MagicMock()
        financials = _sample_financials()
        financials["cash_flow"] = financials["cash_flow"] * 4
        mock_instance.get_financials.return_value = financials
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.statements import _make_cash_flow_statements

        result = _make_cash_flow_statements(mock_instance, "AAPL", "annual", 2)
        parsed = json.loads(result)
        assert len(parsed["statements"]) == 2


# ---------------------------------------------------------------------------
# get_all_financial_statements
# ---------------------------------------------------------------------------


class TestGetAllFinancialStatements:
    """Tests for the get_all_financial_statements MCP tool."""

    @patch("zaza.tools.finance.statements.YFinanceClient")
    def test_returns_combined_statements(self, MockYFClient, cache):
        """get_all_financial_statements returns income, balance, and cash flow."""
        mock_instance = MagicMock()
        mock_instance.get_financials.return_value = _sample_financials()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.statements import _make_all_financial_statements

        result = _make_all_financial_statements(mock_instance, "AAPL", "annual", 5)
        parsed = json.loads(result)
        assert parsed["ticker"] == "AAPL"
        assert "income_statements" in parsed
        assert "balance_sheets" in parsed
        assert "cash_flow_statements" in parsed

    @patch("zaza.tools.finance.statements.YFinanceClient")
    def test_partial_data_still_returns_available(self, MockYFClient, cache):
        """get_all_financial_statements returns whatever is available."""
        mock_instance = MagicMock()
        financials = _sample_financials()
        financials["balance_sheet"] = []
        mock_instance.get_financials.return_value = financials
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.statements import _make_all_financial_statements

        result = _make_all_financial_statements(mock_instance, "AAPL", "annual", 5)
        parsed = json.loads(result)
        assert len(parsed["income_statements"]) == 1
        assert parsed["balance_sheets"] == []
        assert len(parsed["cash_flow_statements"]) == 1

    @patch("zaza.tools.finance.statements.YFinanceClient")
    def test_all_empty_returns_error(self, MockYFClient, cache):
        """get_all_financial_statements returns error when all empty."""
        mock_instance = MagicMock()
        mock_instance.get_financials.return_value = {
            "income_statement": [], "balance_sheet": [], "cash_flow": []
        }
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.statements import _make_all_financial_statements

        result = _make_all_financial_statements(mock_instance, "INVALID", "annual", 5)
        parsed = json.loads(result)
        assert "error" in parsed


# ---------------------------------------------------------------------------
# get_key_ratios_snapshot
# ---------------------------------------------------------------------------


class TestGetKeyRatiosSnapshot:
    """Tests for the get_key_ratios_snapshot MCP tool."""

    @patch("zaza.tools.finance.ratios.YFinanceClient")
    def test_returns_key_ratios(self, MockYFClient, cache):
        """get_key_ratios_snapshot returns valuation and profitability ratios."""
        mock_instance = MagicMock()
        mock_instance.get_quote.return_value = _sample_info_with_ratios()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.ratios import _make_key_ratios_snapshot

        result = _make_key_ratios_snapshot(mock_instance, "AAPL")
        parsed = json.loads(result)
        assert parsed["ticker"] == "AAPL"
        assert parsed["valuation"]["trailing_pe"] == 30.5
        assert parsed["valuation"]["forward_pe"] == 28.2
        assert parsed["valuation"]["ev_to_ebitda"] == 22.1
        assert parsed["profitability"]["return_on_equity"] == 1.56
        assert parsed["profitability"]["gross_margin"] == 0.452
        assert parsed["profitability"]["operating_margin"] == 0.312
        assert parsed["dividends"]["dividend_yield"] == 0.005

    @patch("zaza.tools.finance.ratios.YFinanceClient")
    def test_invalid_ticker_returns_error(self, MockYFClient, cache):
        """get_key_ratios_snapshot returns error for unknown ticker."""
        mock_instance = MagicMock()
        mock_instance.get_quote.return_value = {}
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.ratios import _make_key_ratios_snapshot

        result = _make_key_ratios_snapshot(mock_instance, "INVALID")
        parsed = json.loads(result)
        assert "error" in parsed

    @patch("zaza.tools.finance.ratios.YFinanceClient")
    def test_handles_missing_ratios(self, MockYFClient, cache):
        """get_key_ratios_snapshot returns None for missing ratio fields."""
        mock_instance = MagicMock()
        mock_instance.get_quote.return_value = {
            "regularMarketPrice": 100.0,
            "trailingPE": 15.0,
        }
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.ratios import _make_key_ratios_snapshot

        result = _make_key_ratios_snapshot(mock_instance, "TEST")
        parsed = json.loads(result)
        assert parsed["ticker"] == "TEST"
        assert parsed["valuation"]["trailing_pe"] == 15.0
        assert parsed["valuation"]["forward_pe"] is None


# ---------------------------------------------------------------------------
# get_key_ratios (historical computed)
# ---------------------------------------------------------------------------


class TestGetKeyRatios:
    """Tests for the get_key_ratios MCP tool (historical computed)."""

    @patch("zaza.tools.finance.ratios.YFinanceClient")
    def test_returns_computed_ratios(self, MockYFClient, cache):
        """get_key_ratios computes ratios from financial statements."""
        mock_instance = MagicMock()
        mock_instance.get_financials.return_value = _sample_financials()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.ratios import _make_key_ratios

        result = _make_key_ratios(mock_instance, "AAPL", "annual", 5)
        parsed = json.loads(result)
        assert parsed["ticker"] == "AAPL"
        assert len(parsed["ratios"]) >= 1
        r = parsed["ratios"][0]
        assert "gross_margin" in r
        assert "operating_margin" in r
        assert "net_margin" in r

    @patch("zaza.tools.finance.ratios.YFinanceClient")
    def test_empty_returns_error(self, MockYFClient, cache):
        """get_key_ratios returns error when no financial data."""
        mock_instance = MagicMock()
        mock_instance.get_financials.return_value = {
            "income_statement": [], "balance_sheet": [], "cash_flow": []
        }
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.ratios import _make_key_ratios

        result = _make_key_ratios(mock_instance, "INVALID", "annual", 5)
        parsed = json.loads(result)
        assert "error" in parsed

    @patch("zaza.tools.finance.ratios.YFinanceClient")
    def test_handles_zero_revenue(self, MockYFClient, cache):
        """get_key_ratios handles zero revenue (division by zero)."""
        mock_instance = MagicMock()
        financials = _sample_financials()
        financials["income_statement"][0]["Total Revenue"] = 0
        mock_instance.get_financials.return_value = financials
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.ratios import _make_key_ratios

        result = _make_key_ratios(mock_instance, "AAPL", "annual", 5)
        parsed = json.loads(result)
        # Should not crash, ratios should be None
        assert parsed["ratios"][0]["gross_margin"] is None


# ---------------------------------------------------------------------------
# get_analyst_estimates
# ---------------------------------------------------------------------------


class TestGetAnalystEstimates:
    """Tests for the get_analyst_estimates MCP tool."""

    @patch("zaza.tools.finance.estimates.YFinanceClient")
    def test_returns_estimates(self, MockYFClient, cache):
        """get_analyst_estimates returns consensus estimates and price targets."""
        mock_instance = MagicMock()
        mock_instance.get_quote.return_value = _sample_earnings()
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.estimates import _make_analyst_estimates

        result = _make_analyst_estimates(mock_instance, "AAPL")
        parsed = json.loads(result)
        assert parsed["ticker"] == "AAPL"
        assert parsed["price_target"]["mean"] == 210.0
        assert parsed["price_target"]["high"] == 250.0
        assert parsed["price_target"]["low"] == 170.0
        assert parsed["recommendation"]["key"] == "buy"
        assert parsed["analyst_count"] == 40

    @patch("zaza.tools.finance.estimates.YFinanceClient")
    def test_invalid_ticker_returns_error(self, MockYFClient, cache):
        """get_analyst_estimates returns error for unknown ticker."""
        mock_instance = MagicMock()
        mock_instance.get_quote.return_value = {}
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.estimates import _make_analyst_estimates

        result = _make_analyst_estimates(mock_instance, "INVALID")
        parsed = json.loads(result)
        assert "error" in parsed

    @patch("zaza.tools.finance.estimates.YFinanceClient")
    def test_handles_missing_targets(self, MockYFClient, cache):
        """get_analyst_estimates handles missing price targets gracefully."""
        mock_instance = MagicMock()
        mock_instance.get_quote.return_value = {
            "regularMarketPrice": 100.0,
            "recommendationKey": "hold",
        }
        MockYFClient.return_value = mock_instance

        from zaza.tools.finance.estimates import _make_analyst_estimates

        result = _make_analyst_estimates(mock_instance, "TEST")
        parsed = json.loads(result)
        assert parsed["ticker"] == "TEST"
        assert parsed["price_target"]["mean"] is None


# ---------------------------------------------------------------------------
# get_segmented_revenues
# ---------------------------------------------------------------------------


class TestGetSegmentedRevenues:
    """Tests for the get_segmented_revenues MCP tool."""

    async def test_returns_segmented_data(self, cache):
        """get_segmented_revenues returns revenue by segment from EDGAR XBRL."""
        from zaza.tools.finance.segments import _make_segmented_revenues

        mock_edgar = AsyncMock()
        mock_edgar.ticker_to_cik.return_value = "0000320193"
        mock_edgar.get_company_facts.return_value = _sample_company_facts_xbrl()

        result = await _make_segmented_revenues(mock_edgar, "AAPL")
        parsed = json.loads(result)
        assert parsed["ticker"] == "AAPL"
        assert len(parsed["segments"]) > 0

    async def test_ticker_not_found_returns_error(self, cache):
        """get_segmented_revenues returns error when ticker not in SEC DB."""
        from zaza.tools.finance.segments import _make_segmented_revenues

        mock_edgar = AsyncMock()
        mock_edgar.ticker_to_cik.side_effect = ValueError("Ticker FAKE not found")

        result = await _make_segmented_revenues(mock_edgar, "FAKE")
        parsed = json.loads(result)
        assert "error" in parsed

    async def test_no_segment_data_returns_error(self, cache):
        """get_segmented_revenues returns error when no segment data found."""
        from zaza.tools.finance.segments import _make_segmented_revenues

        mock_edgar = AsyncMock()
        mock_edgar.ticker_to_cik.return_value = "0000320193"
        mock_edgar.get_company_facts.return_value = {
            "entityName": "APPLE INC",
            "facts": {"us-gaap": {}},
        }

        result = await _make_segmented_revenues(mock_edgar, "AAPL")
        parsed = json.loads(result)
        assert "error" in parsed or parsed.get("segments") == []

    async def test_returns_valid_json(self, cache):
        """get_segmented_revenues always returns valid JSON."""
        from zaza.tools.finance.segments import _make_segmented_revenues

        mock_edgar = AsyncMock()
        mock_edgar.ticker_to_cik.return_value = "0000320193"
        mock_edgar.get_company_facts.return_value = _sample_company_facts_xbrl()

        result = await _make_segmented_revenues(mock_edgar, "AAPL")
        json.loads(result)


# ===========================================================================
# Integration: Register function
# ===========================================================================


class TestFinanceRegister:
    """Tests for the finance tools registration."""

    def test_register_creates_all_tools(self):
        """register_finance_tools registers all 13 MCP tools."""

        mock_mcp = MagicMock()
        # Track tool decorator calls
        mock_mcp.tool.return_value = lambda fn: fn

        from zaza.tools.finance import register_finance_tools

        register_finance_tools(mock_mcp)

        # Verify tool() was called 13 times (13 MCP tools)
        assert mock_mcp.tool.call_count == 13
