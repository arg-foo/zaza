"""Economic calendar tool."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.fred_client import FredClient
from zaza.cache.store import FileCache
from zaza.config import get_fred_api_key, has_fred_key

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register economic calendar tool."""
    cache = FileCache()

    @mcp.tool()
    async def get_economic_calendar(days_ahead: int = 14) -> str:
        """Get upcoming economic events and data releases.

        Uses FRED API when available. Degrades gracefully without FRED API key,
        returning a message about unavailability.

        Args:
            days_ahead: Number of days to look ahead for events (default 14).
        """
        cache_key = cache.make_key("economic_calendar", days_ahead=days_ahead)
        cached = cache.get(cache_key, "economic_calendar")
        if cached is not None:
            return json.dumps(cached, default=str)

        if not has_fred_key():
            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "source": "FRED API unavailable",
                    "message": (
                        "FRED API key not configured."
                        " Set FRED_API_KEY environment variable"
                        " for economic calendar data."
                    ),
                    "events": [],
                },
            }
            return json.dumps(result, default=str)

        try:
            fred = FredClient(api_key=get_fred_api_key(), cache=cache)
            releases = await fred.get_release_dates(days_ahead=days_ahead)

            events = []
            for release in releases:
                events.append({
                    "release_id": release.get("release_id", ""),
                    "name": release.get("release_name", "Unknown"),
                    "date": release.get("date", ""),
                })

            result = {
                "status": "ok",
                "data": {
                    "source": "FRED",
                    "days_ahead": days_ahead,
                    "events": events,
                },
            }
            cache.set(cache_key, "economic_calendar", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("economic_calendar_error", error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
