"""Tests for Regular Trading Hours (RTH) module."""

from datetime import datetime
from zoneinfo import ZoneInfo

import time_machine

from zaza.consumer.rth import get_seconds_until_rth_open, is_rth_open

ET = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# is_rth_open tests
# ---------------------------------------------------------------------------


class TestIsRthOpen:
    """Tests for is_rth_open."""

    def test_rth_open_at_930_et(self) -> None:
        """09:30 ET Monday should be open."""
        with time_machine.travel(datetime(2026, 3, 2, 9, 30, tzinfo=ET)):  # Monday
            assert is_rth_open() is True

    def test_rth_open_at_noon_et(self) -> None:
        """12:00 ET Tuesday should be open."""
        with time_machine.travel(datetime(2026, 3, 3, 12, 0, tzinfo=ET)):  # Tuesday
            assert is_rth_open() is True

    def test_rth_closed_at_929_et(self) -> None:
        """09:29 ET Wednesday should be closed."""
        with time_machine.travel(datetime(2026, 3, 4, 9, 29, tzinfo=ET)):  # Wednesday
            assert is_rth_open() is False

    def test_rth_closed_at_1600_et(self) -> None:
        """16:00 ET Thursday should be closed (boundary is exclusive)."""
        with time_machine.travel(datetime(2026, 3, 5, 16, 0, tzinfo=ET)):  # Thursday
            assert is_rth_open() is False

    def test_rth_closed_saturday(self) -> None:
        """10:00 ET Saturday should be closed."""
        with time_machine.travel(datetime(2026, 3, 7, 10, 0, tzinfo=ET)):  # Saturday
            assert is_rth_open() is False

    def test_rth_closed_sunday(self) -> None:
        """10:00 ET Sunday should be closed."""
        with time_machine.travel(datetime(2026, 3, 8, 10, 0, tzinfo=ET)):  # Sunday
            assert is_rth_open() is False

    def test_rth_closed_holiday(self) -> None:
        """10:00 ET on Jan 1, 2026 (holiday) should be closed."""
        with time_machine.travel(datetime(2026, 1, 1, 10, 0, tzinfo=ET)):  # New Year's Day
            assert is_rth_open() is False

    def test_rth_open_day_after_holiday(self) -> None:
        """10:00 ET on Jan 2, 2026 (Friday, not a holiday) should be open."""
        with time_machine.travel(datetime(2026, 1, 2, 10, 0, tzinfo=ET)):  # Friday
            assert is_rth_open() is True


# ---------------------------------------------------------------------------
# get_seconds_until_rth_open tests
# ---------------------------------------------------------------------------


class TestGetSecondsUntilRthOpen:
    """Tests for get_seconds_until_rth_open."""

    def test_returns_none_when_rth_open(self) -> None:
        """Should return None during RTH."""
        with time_machine.travel(datetime(2026, 3, 2, 12, 0, tzinfo=ET)):  # Mon noon
            assert get_seconds_until_rth_open() is None

    def test_seconds_before_open_same_day(self) -> None:
        """09:00 ET Monday -> 30 minutes (1800s) until 09:30 open."""
        with time_machine.travel(datetime(2026, 3, 2, 9, 0, tzinfo=ET)):  # Mon 09:00
            result = get_seconds_until_rth_open()
            assert result is not None
            assert result == 1800.0

    def test_seconds_after_close_same_day(self) -> None:
        """17:00 ET Monday -> next open is Tuesday 09:30 = 16.5 hours = 59400s."""
        with time_machine.travel(datetime(2026, 3, 2, 17, 0, tzinfo=ET)):  # Mon 17:00
            result = get_seconds_until_rth_open()
            assert result is not None
            assert result == 59400.0  # 16h30m = 59400s

    def test_seconds_friday_after_close(self) -> None:
        """17:00 ET Friday -> next open is Monday 09:30 = 64.5 hours = 232200s."""
        with time_machine.travel(datetime(2026, 3, 6, 17, 0, tzinfo=ET)):  # Fri 17:00
            result = get_seconds_until_rth_open()
            assert result is not None
            assert result == 232200.0  # Fri 17:00 -> Mon 09:30 = 64h30m

    def test_seconds_saturday(self) -> None:
        """10:00 ET Saturday -> next open is Monday 09:30 = 47.5 hours = 171000s."""
        with time_machine.travel(datetime(2026, 3, 7, 10, 0, tzinfo=ET)):  # Sat 10:00
            result = get_seconds_until_rth_open()
            assert result is not None
            assert result == 171000.0  # Sat 10:00 -> Mon 09:30 = 47h30m

    def test_seconds_sunday(self) -> None:
        """10:00 ET Sunday -> next open is Monday 09:30 = 23.5 hours = 84600s."""
        with time_machine.travel(datetime(2026, 3, 8, 10, 0, tzinfo=ET)):  # Sun 10:00
            result = get_seconds_until_rth_open()
            assert result is not None
            assert result == 84600.0  # Sun 10:00 -> Mon 09:30 = 23h30m

    def test_seconds_before_holiday(self) -> None:
        """22:00 ET Dec 31, 2025 -> next open skips Jan 1 holiday, opens Jan 2 09:30.
        Dec 31 22:00 -> Jan 2 09:30 = 35.5 hours = 127800s."""
        with time_machine.travel(datetime(2025, 12, 31, 22, 0, tzinfo=ET)):  # Wed 22:00
            result = get_seconds_until_rth_open()
            assert result is not None
            assert result == 127800.0  # 35h30m

    def test_seconds_on_holiday_morning(self) -> None:
        """09:00 ET on Jan 1, 2026 (holiday, Thursday) -> next open is Jan 2 09:30 (Friday).
        24.5 hours = 88200s."""
        with time_machine.travel(datetime(2026, 1, 1, 9, 0, tzinfo=ET)):  # Holiday 09:00
            result = get_seconds_until_rth_open()
            assert result is not None
            assert result == 88200.0  # 24h30m
