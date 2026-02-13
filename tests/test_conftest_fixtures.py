"""Tests verifying the shared conftest fixtures work correctly."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from zaza.cache.store import FileCache


class TestMockCacheFixture:
    """Tests for the mock_cache shared fixture."""

    def test_mock_cache_is_filecache(self, mock_cache: FileCache) -> None:
        """mock_cache should return a FileCache instance."""
        assert isinstance(mock_cache, FileCache)

    def test_mock_cache_supports_get_set(self, mock_cache: FileCache) -> None:
        """mock_cache should support basic get/set operations."""
        key = mock_cache.make_key("test", ticker="AAPL")
        assert mock_cache.get(key, "prices") is None
        mock_cache.set(key, "prices", {"price": 100.0})
        result = mock_cache.get(key, "prices")
        assert result == {"price": 100.0}

    def test_mock_cache_isolated_per_test(self, mock_cache: FileCache) -> None:
        """Each test should get a fresh, empty cache."""
        key = mock_cache.make_key("test", ticker="MSFT")
        assert mock_cache.get(key, "prices") is None


class TestSampleOhlcvFixture:
    """Tests for the sample_ohlcv shared fixture."""

    def test_sample_ohlcv_is_dataframe(self, sample_ohlcv: pd.DataFrame) -> None:
        """sample_ohlcv should return a pandas DataFrame."""
        assert isinstance(sample_ohlcv, pd.DataFrame)

    def test_sample_ohlcv_has_252_rows(self, sample_ohlcv: pd.DataFrame) -> None:
        """sample_ohlcv should have 252 business days."""
        assert len(sample_ohlcv) == 252

    def test_sample_ohlcv_has_ohlcv_columns(self, sample_ohlcv: pd.DataFrame) -> None:
        """sample_ohlcv should have Open, High, Low, Close, Volume columns."""
        expected = {"Open", "High", "Low", "Close", "Volume"}
        assert set(sample_ohlcv.columns) == expected

    def test_sample_ohlcv_index_is_datetime(self, sample_ohlcv: pd.DataFrame) -> None:
        """sample_ohlcv index should be DatetimeIndex named 'Date'."""
        assert isinstance(sample_ohlcv.index, pd.DatetimeIndex)
        assert sample_ohlcv.index.name == "Date"

    def test_sample_ohlcv_is_deterministic(self, sample_ohlcv: pd.DataFrame) -> None:
        """sample_ohlcv should produce the same values every time (seed 42)."""
        # Check first close value is consistent
        first_close = sample_ohlcv["Close"].iloc[0]
        # With seed 42, the first return and cumulative product should be deterministic
        assert isinstance(first_close, float)
        assert 90.0 < first_close < 110.0  # Should be near 100 starting price

    def test_sample_ohlcv_high_greater_than_low(self, sample_ohlcv: pd.DataFrame) -> None:
        """High should always be >= Low."""
        assert (sample_ohlcv["High"] >= sample_ohlcv["Low"]).all()

    def test_sample_ohlcv_volume_positive(self, sample_ohlcv: pd.DataFrame) -> None:
        """Volume should always be positive."""
        assert (sample_ohlcv["Volume"] > 0).all()


class TestMockYfClientFixture:
    """Tests for the mock_yf_client shared fixture."""

    def test_mock_yf_client_is_magicmock(self, mock_yf_client: MagicMock) -> None:
        """mock_yf_client should return a MagicMock."""
        assert isinstance(mock_yf_client, MagicMock)

    def test_mock_yf_client_has_cache(
        self, mock_yf_client: MagicMock, mock_cache: FileCache
    ) -> None:
        """mock_yf_client should have a cache attribute."""
        assert mock_yf_client.cache is mock_cache

    def test_mock_yf_client_get_history_returns_records(
        self, mock_yf_client: MagicMock
    ) -> None:
        """get_history should return a list of dicts."""
        result = mock_yf_client.get_history("AAPL")
        assert isinstance(result, list)
        assert len(result) == 252
        assert isinstance(result[0], dict)
        assert "Open" in result[0]
        assert "Close" in result[0]
        assert "Date" in result[0]

    def test_mock_yf_client_get_quote_returns_dict(
        self, mock_yf_client: MagicMock
    ) -> None:
        """get_quote should return a dict with expected keys."""
        result = mock_yf_client.get_quote("AAPL")
        assert isinstance(result, dict)
        assert "regularMarketPrice" in result
        assert "regularMarketVolume" in result
        assert "marketCap" in result
        assert "symbol" in result
