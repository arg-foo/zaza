"""Regular Trading Hours (RTH) utilities for US equity markets.

Provides helpers to determine whether the US stock market is currently open
and how many seconds remain until the next open.
"""

import datetime
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")

# Static set of US market holidays (NYSE/NASDAQ observed closures) for 2025-2027.
US_MARKET_HOLIDAYS: set[tuple[int, int, int]] = {
    # 2025
    (2025, 1, 1),
    (2025, 1, 20),
    (2025, 2, 17),
    (2025, 4, 18),
    (2025, 5, 26),
    (2025, 6, 19),
    (2025, 7, 4),
    (2025, 9, 1),
    (2025, 11, 27),
    (2025, 12, 25),
    # 2026
    (2026, 1, 1),
    (2026, 1, 19),
    (2026, 2, 16),
    (2026, 4, 3),
    (2026, 5, 25),
    (2026, 6, 19),
    (2026, 7, 3),
    (2026, 9, 7),
    (2026, 11, 26),
    (2026, 12, 25),
    # 2027
    (2027, 1, 1),
    (2027, 1, 18),
    (2027, 2, 15),
    (2027, 3, 26),
    (2027, 5, 31),
    (2027, 6, 18),
    (2027, 7, 5),
    (2027, 9, 6),
    (2027, 11, 25),
    (2027, 12, 24),
}


def _is_trading_day(dt: datetime.datetime) -> bool:
    """Return True if *dt* falls on a weekday that is not a US market holiday."""
    if dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return (dt.year, dt.month, dt.day) not in US_MARKET_HOLIDAYS


def is_rth_open(
    rth_open_hour: int = 9,
    rth_open_minute: int = 30,
    rth_close_hour: int = 16,
    rth_close_minute: int = 0,
) -> bool:
    """Return True if the current time is within US Regular Trading Hours.

    Default hours: 09:30 -- 16:00 ET, Monday--Friday, excluding US market
    holidays.  The open boundary is inclusive; the close boundary is exclusive
    (i.e. exactly 16:00 is considered closed).
    """
    now = datetime.datetime.now(tz=_ET)

    if not _is_trading_day(now):
        return False

    market_open = now.replace(hour=rth_open_hour, minute=rth_open_minute, second=0, microsecond=0)
    market_close = now.replace(
        hour=rth_close_hour, minute=rth_close_minute, second=0, microsecond=0
    )

    return market_open <= now < market_close


def get_seconds_until_rth_open(
    rth_open_hour: int = 9,
    rth_open_minute: int = 30,
) -> float | None:
    """Return seconds until the next RTH open, or None if RTH is currently open.

    Skips weekends and US market holidays when computing the next open.
    """
    if is_rth_open():
        return None

    now = datetime.datetime.now(tz=_ET).replace(microsecond=0)

    # Build a candidate open time for today.
    candidate = now.replace(hour=rth_open_hour, minute=rth_open_minute, second=0, microsecond=0)

    # If the candidate is still in the future today *and* today is a trading day,
    # we can open today.
    if candidate > now and _is_trading_day(now):
        return (candidate - now).total_seconds()

    # Otherwise advance day-by-day until we find a trading day.
    candidate = (candidate + datetime.timedelta(days=1)).replace(
        hour=rth_open_hour, minute=rth_open_minute, second=0, microsecond=0
    )
    while not _is_trading_day(candidate):
        candidate += datetime.timedelta(days=1)

    return (candidate - now).total_seconds()
