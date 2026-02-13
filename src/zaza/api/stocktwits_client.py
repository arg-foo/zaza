"""StockTwits API client for social sentiment data."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)

STOCKTWITS_BASE = "https://api.stocktwits.com/api/2"


class StockTwitsClient:
    """Async StockTwits client for ticker sentiment streams."""

    def __init__(self, cache: FileCache) -> None:
        self.cache = cache

    async def get_ticker_stream(self, ticker: str) -> dict[str, Any]:
        """Get recent messages and sentiment for a ticker."""
        cache_key = self.cache.make_key("stocktwits_stream", ticker=ticker)
        cached = self.cache.get(cache_key, "social_sentiment")
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{STOCKTWITS_BASE}/streams/symbol/{ticker}.json"
                )
                resp.raise_for_status()
                data = resp.json()

            messages = []
            for msg in data.get("messages", []):
                sentiment = msg.get("entities", {}).get("sentiment", {})
                messages.append({
                    "body": msg.get("body", ""),
                    "sentiment": sentiment.get("basic") if sentiment else None,
                    "created_at": msg.get("created_at", ""),
                    "user": msg.get("user", {}).get("username", ""),
                })

            result = {
                "ticker": ticker,
                "messages": messages,
                "message_count": len(messages),
                "cursor": data.get("cursor", {}),
            }
            self.cache.set(cache_key, "social_sentiment", result)
            return result
        except Exception as e:
            logger.warning("stocktwits_error", ticker=ticker, error=str(e))
            return {"ticker": ticker, "messages": [], "message_count": 0, "cursor": {}}
