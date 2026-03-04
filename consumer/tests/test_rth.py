"""Tests for Regular Trading Hours (RTH) module."""

from datetime import datetime
from zoneinfo import ZoneInfo

import time_machine

from zaza_consumer.rth import get_seconds_until_rth_open, is_rth_open

ET = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# is_rth_open tests
# ---------------------------------------------------------------------------


class TestIsRthOpen:
    """Tests for is_rth_open."""

    def test_rth_open_at_930_et(self) -> None:
        with time_machine.travel(datetime(2026, 3, 2, 9, 30, tzinfo=ET)):
            assert is_rth_open() is True

    def test_rth_open_at_noon_et(self) -> None:
        with time_machine.travel(datetime(2026, 3, 3, 12, 0, tzinfo=ET)):
            assert is_rth_open() is True

    def test_rth_closed_at_929_et(self) -> None:
        with time_machine.travel(datetime(2026, 3, 4, 9, 29, tzinfo=ET)):
            assert is_rth_open() is False

    def test_rth_closed_at_1600_et(self) -> None:
        with time_machine.travel(datetime(2026, 3, 5, 16, 0, tzinfo=ET)):
            assert is_rth_open() is False

    def test_rth_closed_saturday(self) -> None:
        with time_machine.travel(datetime(2026, 3, 7, 10, 0, tzinfo=ET)):
            assert is_rth_open() is False

    def test_rth_closed_sunday(self) -> None:
        with time_machine.travel(datetime(2026, 3, 8, 10, 0, tzinfo=ET)):
            assert is_rth_open() is False

    def test_rth_closed_holiday(self) -> None:
        with time_machine.travel(datetime(2026, 1, 1, 10, 0, tzinfo=ET)):
            assert is_rth_open() is False

    def test_rth_open_day_after_holiday(self) -> None:
        with time_machine.travel(datetime(2026, 1, 2, 10, 0, tzinfo=ET)):
            assert is_rth_open() is True


# ---------------------------------------------------------------------------
# get_seconds_until_rth_open tests
# ---------------------------------------------------------------------------


class TestGetSecondsUntilRthOpen:
    """Tests for get_seconds_until_rth_open."""

    def test_returns_none_when_rth_open(self) -> None:
        with time_machine.travel(datetime(2026, 3, 2, 12, 0, tzinfo=ET)):
            assert get_seconds_until_rth_open() is None

    def test_seconds_before_open_same_day(self) -> None:
        with time_machine.travel(datetime(2026, 3, 2, 9, 0, tzinfo=ET)):
            result = get_seconds_until_rth_open()
            assert result is not None
            assert result == 1800.0

    def test_seconds_after_close_same_day(self) -> None:
        with time_machine.travel(datetime(2026, 3, 2, 17, 0, tzinfo=ET)):
            result = get_seconds_until_rth_open()
            assert result is not None
            assert result == 59400.0

    def test_seconds_friday_after_close(self) -> None:
        with time_machine.travel(datetime(2026, 3, 6, 17, 0, tzinfo=ET)):
            result = get_seconds_until_rth_open()
            assert result is not None
            assert result == 232200.0

    def test_seconds_saturday(self) -> None:
        with time_machine.travel(datetime(2026, 3, 7, 10, 0, tzinfo=ET)):
            result = get_seconds_until_rth_open()
            assert result is not None
            assert result == 171000.0

    def test_seconds_sunday(self) -> None:
        with time_machine.travel(datetime(2026, 3, 8, 10, 0, tzinfo=ET)):
            result = get_seconds_until_rth_open()
            assert result is not None
            assert result == 84600.0

    def test_seconds_before_holiday(self) -> None:
        with time_machine.travel(datetime(2025, 12, 31, 22, 0, tzinfo=ET)):
            result = get_seconds_until_rth_open()
            assert result is not None
            assert result == 127800.0

    def test_seconds_on_holiday_morning(self) -> None:
        with time_machine.travel(datetime(2026, 1, 1, 9, 0, tzinfo=ET)):
            result = get_seconds_until_rth_open()
            assert result is not None
            assert result == 88200.0
