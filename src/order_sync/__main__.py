"""Entry point for the Order Sync Worker.

Usage: python -m order_sync [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from order_sync.worker import run


def main() -> None:
    """Parse CLI arguments and run the order sync worker."""
    parser = argparse.ArgumentParser(description="Order Sync Worker")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show computed intents without placing orders",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(run(dry_run=args.dry_run))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
