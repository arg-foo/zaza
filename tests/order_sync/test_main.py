"""Tests for order_sync.__main__ time-gate logic."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from order_sync.__main__ import is_market_open_window

ET = ZoneInfo("America/New_York")


def _mock_et_time(hour: int, minute: int) -> datetime:
    """Create a datetime in ET with the given hour and minute."""
    return datetime(2026, 3, 6, hour, minute, 0, tzinfo=ET)


class TestIsMarketOpenWindow:
    """Tests for the is_market_open_window time-gate."""

    @patch("order_sync.__main__.datetime")
    def test_returns_true_at_931_am_et(self, mock_datetime):
        mock_datetime.now.return_value = _mock_et_time(9, 31)
        assert is_market_open_window() is True

    @patch("order_sync.__main__.datetime")
    def test_returns_true_at_926_am_et(self, mock_datetime):
        mock_datetime.now.return_value = _mock_et_time(9, 26)
        assert is_market_open_window() is True

    @patch("order_sync.__main__.datetime")
    def test_returns_true_at_936_am_et(self, mock_datetime):
        mock_datetime.now.return_value = _mock_et_time(9, 36)
        assert is_market_open_window() is True

    @patch("order_sync.__main__.datetime")
    def test_returns_false_at_831_am_et(self, mock_datetime):
        """During EST, 13:31 UTC = 8:31 AM ET — should exit."""
        mock_datetime.now.return_value = _mock_et_time(8, 31)
        assert is_market_open_window() is False

    @patch("order_sync.__main__.datetime")
    def test_returns_false_at_1031_am_et(self, mock_datetime):
        """During EDT, 14:31 UTC = 10:31 AM ET — should exit."""
        mock_datetime.now.return_value = _mock_et_time(10, 31)
        assert is_market_open_window() is False

    @patch("order_sync.__main__.datetime")
    def test_returns_false_at_925_am_et(self, mock_datetime):
        """Just outside the lower bound of the window."""
        mock_datetime.now.return_value = _mock_et_time(9, 25)
        assert is_market_open_window() is False

    @patch("order_sync.__main__.datetime")
    def test_returns_false_at_937_am_et(self, mock_datetime):
        """Just outside the upper bound of the window."""
        mock_datetime.now.return_value = _mock_et_time(9, 37)
        assert is_market_open_window() is False
