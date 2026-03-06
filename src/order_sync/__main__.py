"""Entry point for the Order Sync Worker.

Usage: python -m order_sync [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from order_sync.worker import run

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")


def is_market_open_window() -> bool:
    """Return True if current ET time is within the 9:31 AM window (9:26-9:36)."""
    now_et = datetime.now(ET)
    return now_et.hour == 9 and 26 <= now_et.minute <= 36


def main() -> None:
    """Parse CLI arguments and run the order sync worker."""
    parser = argparse.ArgumentParser(description="Order Sync Worker")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show computed intents without placing orders",
    )
    args = parser.parse_args()

    if not args.dry_run and not is_market_open_window():
        now_et = datetime.now(ET)
        logger.info(
            "Outside market open window (current ET: %s). Exiting.",
            now_et.strftime("%H:%M"),
        )
        sys.exit(0)

    exit_code = asyncio.run(run(dry_run=args.dry_run))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
