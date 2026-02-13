"""Async FRED API client for economic data."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"


class FredClient:
    """Async client for Federal Reserve Economic Data."""

    def __init__(self, api_key: str, cache: FileCache) -> None:
        self.api_key = api_key
        self.cache = cache

    async def get_series(
        self, series_id: str, start_date: str | None = None, end_date: str | None = None
    ) -> list[dict[str, Any]]:
        """Get economic data series observations."""
        cache_key = self.cache.make_key(
            "fred_series", series_id=series_id,
            start=start_date, end=end_date,
        )
        cached = self.cache.get(cache_key, "economic_calendar")
        if cached is not None:
            return cached

        params: dict[str, str] = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }
        if start_date:
            params["observation_start"] = start_date
        if end_date:
            params["observation_end"] = end_date

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{FRED_BASE}/series/observations", params=params)
                resp.raise_for_status()
                data = resp.json()
            observations = data.get("observations", [])
            self.cache.set(cache_key, "economic_calendar", observations)
            return observations
        except Exception as e:
            logger.warning("fred_error", series_id=series_id, error=str(e))
            return []

    async def get_release_dates(self, days_ahead: int = 14) -> list[dict[str, Any]]:
        """Get upcoming economic release dates."""
        cache_key = self.cache.make_key("fred_releases", days_ahead=days_ahead)
        cached = self.cache.get(cache_key, "economic_calendar")
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{FRED_BASE}/releases/dates",
                    params={
                        "api_key": self.api_key,
                        "file_type": "json",
                        "include_release_dates_with_no_data": "true",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            releases = data.get("release_dates", [])
            self.cache.set(cache_key, "economic_calendar", releases)
            return releases
        except Exception as e:
            logger.warning("fred_error", error=str(e))
            return []
