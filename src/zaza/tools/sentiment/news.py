"""News sentiment analysis tool."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.sentiment import aggregate_sentiment, score_headline

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP, yf: YFinanceClient, cache: FileCache) -> None:
    """Register news sentiment tool on the MCP server."""

    @mcp.tool()
    async def get_news_sentiment(ticker: str, days: int = 7) -> str:
        """Analyze sentiment of recent news for a ticker.

        Fetches news articles via yfinance, scores each headline for
        financial sentiment, and returns aggregate and per-article scores.
        Cached for 2 hours.
        """
        try:
            ticker_upper = ticker.upper()

            # Check cache
            cache_key = cache.make_key("news_sentiment", ticker=ticker_upper, days=days)
            cached = cache.get(cache_key, "news_sentiment")
            if cached is not None:
                return json.dumps(cached, default=str)

            news = yf.get_news(ticker_upper)
            if not news:
                result: dict[str, Any] = {
                    "ticker": ticker_upper,
                    "aggregate": {
                        "sentiment": "neutral",
                        "score": 0.0,
                        "confidence": 0.0,
                        "count": 0,
                    },
                    "articles": [],
                }
                return json.dumps(result, default=str)

            # Score each headline
            articles: list[dict[str, Any]] = []
            scores: list[dict[str, Any]] = []
            for article in news:
                title = article.get("title", "")
                sentiment_data = score_headline(title)
                scores.append(sentiment_data)
                articles.append({
                    "title": title,
                    "publisher": article.get("publisher", ""),
                    "link": article.get("link", ""),
                    **sentiment_data,
                })

            # Aggregate
            agg = aggregate_sentiment(scores)

            result = {
                "ticker": ticker_upper,
                "aggregate": agg,
                "articles": articles,
            }
            cache.set(cache_key, "news_sentiment", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("get_news_sentiment_error", ticker=ticker, error=str(e))
            return json.dumps({"error": f"Failed to get news sentiment for {ticker}: {e}"})
