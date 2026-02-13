"""Market-wide sentiment tool: CNN Fear & Greed Index."""

from __future__ import annotations

import json
from typing import Any

import httpx
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)

FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"


def register(mcp: FastMCP, cache: FileCache) -> None:
    """Register Fear & Greed Index tool on the MCP server."""

    @mcp.tool()
    async def get_fear_greed_index() -> str:
        """Get the CNN Fear & Greed Index.

        Returns the current score (0-100), rating (Extreme Fear to Extreme Greed),
        and historical comparison points. Cached for 4 hours.
        """
        try:
            # Check cache
            cache_key = cache.make_key("fear_greed")
            cached = cache.get(cache_key, "fear_greed")
            if cached is not None:
                return json.dumps(cached, default=str)

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    FEAR_GREED_URL,
                    headers={"User-Agent": "Mozilla/5.0 Zaza/1.0"},
                )
                resp.raise_for_status()
                data = resp.json()

            fg = data.get("fear_and_greed", {})
            result: dict[str, Any] = {
                "score": fg.get("score"),
                "rating": fg.get("rating"),
                "timestamp": fg.get("timestamp"),
                "previous_close": fg.get("previous_close"),
                "previous_1_week": fg.get("previous_1_week"),
                "previous_1_month": fg.get("previous_1_month"),
                "previous_1_year": fg.get("previous_1_year"),
            }

            cache.set(cache_key, "fear_greed", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("get_fear_greed_index_error", error=str(e))
            return json.dumps({"error": f"Failed to get Fear & Greed Index: {e}"})
