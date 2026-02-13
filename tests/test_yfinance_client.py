"""Tests for the yfinance API client."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache


@pytest.fixture
def cache(tmp_path):
    return FileCache(cache_dir=tmp_path)


@pytest.fixture
def client(cache):
    return YFinanceClient(cache)


def _make_ohlcv_df():
    dates = pd.date_range("2024-01-01", periods=5, freq="B")
    return pd.DataFrame(
        {
            "Open": [100, 101, 102, 103, 104],
            "High": [101, 102, 103, 104, 105],
            "Low": [99, 100, 101, 102, 103],
            "Close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "Volume": [1000000, 1100000, 1200000, 1300000, 1400000],
        },
        index=dates,
    )


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_quote_returns_info(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.info = {"regularMarketPrice": 150.0, "marketCap": 2500000000000}
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_quote("AAPL")
    assert result["regularMarketPrice"] == 150.0


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_quote_caches(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.info = {"regularMarketPrice": 150.0, "marketCap": 2500000000000}
    mock_ticker_cls.return_value = mock_ticker

    client.get_quote("AAPL")
    client.get_quote("AAPL")
    assert mock_ticker_cls.call_count == 1  # cached on second call


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_quote_empty_info(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.info = {}
    mock_ticker_cls.return_value = mock_ticker
    result = client.get_quote("INVALID")
    assert result == {}


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_quote_error_returns_empty(mock_ticker_cls, client):
    mock_ticker_cls.side_effect = Exception("network error")
    result = client.get_quote("AAPL")
    assert result == {}


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_history(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_ohlcv_df()
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_history("AAPL", period="1mo")
    assert len(result) == 5
    assert "Close" in result[0]


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_history_with_dates(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_ohlcv_df()
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_history("AAPL", start="2024-01-01", end="2024-01-31")
    assert len(result) == 5
    mock_ticker.history.assert_called_once_with(
        start="2024-01-01", end="2024-01-31", interval="1d"
    )


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_history_caches(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_ohlcv_df()
    mock_ticker_cls.return_value = mock_ticker

    client.get_history("AAPL", period="1mo")
    client.get_history("AAPL", period="1mo")
    assert mock_ticker_cls.call_count == 1


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_history_error_returns_empty(mock_ticker_cls, client):
    mock_ticker_cls.side_effect = Exception("network error")
    result = client.get_history("AAPL")
    assert result == []


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_history_empty_df_not_cached(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_history("AAPL")
    assert result == []
    # Second call should still hit yfinance because empty results are not cached
    client.get_history("AAPL")
    assert mock_ticker_cls.call_count == 2


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_financials_annual(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    income_df = pd.DataFrame(
        {"TotalRevenue": [394000000000], "NetIncome": [97000000000]},
        index=pd.to_datetime(["2024-09-28"]),
    )
    mock_ticker.financials = income_df.T
    mock_ticker.balance_sheet = pd.DataFrame()
    mock_ticker.cashflow = pd.DataFrame()
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_financials("AAPL", period="annual")
    assert len(result["income_statement"]) == 1
    assert result["balance_sheet"] == []
    assert result["cash_flow"] == []


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_financials_quarterly(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    income_df = pd.DataFrame(
        {"TotalRevenue": [95000000000]},
        index=pd.to_datetime(["2024-09-28"]),
    )
    mock_ticker.quarterly_financials = income_df.T
    mock_ticker.quarterly_balance_sheet = pd.DataFrame()
    mock_ticker.quarterly_cashflow = pd.DataFrame()
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_financials("AAPL", period="quarterly")
    assert len(result["income_statement"]) == 1


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_financials_error(mock_ticker_cls, client):
    mock_ticker_cls.side_effect = Exception("API error")
    result = client.get_financials("AAPL")
    assert result == {"income_statement": [], "balance_sheet": [], "cash_flow": []}


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_options_expirations(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.options = ("2024-03-15", "2024-04-19")
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_options_expirations("AAPL")
    assert result == ["2024-03-15", "2024-04-19"]


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_options_expirations_caches(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.options = ("2024-03-15",)
    mock_ticker_cls.return_value = mock_ticker

    client.get_options_expirations("AAPL")
    client.get_options_expirations("AAPL")
    assert mock_ticker_cls.call_count == 1


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_options_expirations_error(mock_ticker_cls, client):
    mock_ticker_cls.side_effect = Exception("error")
    result = client.get_options_expirations("AAPL")
    assert result == []


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_options_chain(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    chain = MagicMock()
    chain.calls = pd.DataFrame(
        {"strike": [150, 155], "lastPrice": [5.0, 3.0], "volume": [100, 200]}
    )
    chain.puts = pd.DataFrame(
        {"strike": [145, 150], "lastPrice": [4.0, 6.0], "volume": [150, 250]}
    )
    mock_ticker.option_chain.return_value = chain
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_options_chain("AAPL", "2024-03-15")
    assert len(result["calls"]) == 2
    assert len(result["puts"]) == 2
    assert result["calls"][0]["strike"] == 150


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_options_chain_error(mock_ticker_cls, client):
    mock_ticker_cls.side_effect = Exception("error")
    result = client.get_options_chain("AAPL", "2024-03-15")
    assert result == {"calls": [], "puts": []}


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_news(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.news = [{"title": "Apple earnings beat", "publisher": "Reuters"}]
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_news("AAPL")
    assert len(result) == 1
    assert result[0]["title"] == "Apple earnings beat"


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_news_empty(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.news = []
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_news("AAPL")
    assert result == []


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_news_none(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.news = None
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_news("AAPL")
    assert result == []


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_news_error(mock_ticker_cls, client):
    mock_ticker_cls.side_effect = Exception("error")
    result = client.get_news("AAPL")
    assert result == []


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_insider_transactions(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.insider_transactions = pd.DataFrame(
        {
            "Insider": ["Tim Cook"],
            "Shares": [50000],
            "Value": [7500000],
        }
    )
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_insider_transactions("AAPL")
    assert len(result) == 1
    assert result[0]["Insider"] == "Tim Cook"


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_insider_transactions_error(mock_ticker_cls, client):
    mock_ticker_cls.side_effect = Exception("error")
    result = client.get_insider_transactions("AAPL")
    assert result == []


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_institutional_holders(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.institutional_holders = pd.DataFrame(
        {
            "Holder": ["Vanguard Group"],
            "Shares": [1300000000],
            "Value": [195000000000],
        }
    )
    mock_ticker.major_holders = pd.DataFrame(
        {"Value": ["72.5%"], "Breakdown": ["% of Shares Held by Institutions"]}
    )
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_institutional_holders("AAPL")
    assert len(result["institutional_holders"]) == 1
    assert result["institutional_holders"][0]["Holder"] == "Vanguard Group"
    assert len(result["major_holders"]) == 1


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_institutional_holders_error(mock_ticker_cls, client):
    mock_ticker_cls.side_effect = Exception("error")
    result = client.get_institutional_holders("AAPL")
    assert result == {"institutional_holders": [], "major_holders": []}


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_earnings(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.earnings_history = pd.DataFrame(
        {
            "epsEstimate": [1.50],
            "epsActual": [1.64],
            "epsDifference": [0.14],
        }
    )
    mock_ticker.calendar = {"Earnings Date": "2025-01-30"}
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_earnings("AAPL")
    assert len(result["earnings_history"]) == 1
    assert result["calendar"]["Earnings Date"] == "2025-01-30"


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_earnings_with_df_calendar(mock_ticker_cls, client):
    mock_ticker = MagicMock()
    mock_ticker.earnings_history = pd.DataFrame()
    mock_ticker.calendar = pd.DataFrame(
        {"Earnings Date": ["2025-01-30"]}, index=["Value"]
    )
    mock_ticker_cls.return_value = mock_ticker

    result = client.get_earnings("AAPL")
    assert "Earnings Date" in result["calendar"]


@patch("zaza.api.yfinance_client.yf.Ticker")
def test_get_earnings_error(mock_ticker_cls, client):
    mock_ticker_cls.side_effect = Exception("error")
    result = client.get_earnings("AAPL")
    assert result == {"earnings_history": [], "calendar": {}}


def test_df_to_records_none():
    assert YFinanceClient._df_to_records(None) == []


def test_df_to_records_empty():
    assert YFinanceClient._df_to_records(pd.DataFrame()) == []


def test_df_to_records_with_datetime_index():
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    df = pd.DataFrame({"Close": [100, 101, 102]}, index=dates)
    records = YFinanceClient._df_to_records(df)
    assert len(records) == 3
    # Datetime index should be converted to string
    assert isinstance(records[0]["index"], str)


def test_df_to_records_preserves_values():
    df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
    records = YFinanceClient._df_to_records(df)
    assert len(records) == 3
    assert records[0]["A"] == 1
    assert records[0]["B"] == "x"
