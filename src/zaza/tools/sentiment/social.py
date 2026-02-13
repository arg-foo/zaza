"""Social sentiment tool combining Reddit and StockTwits."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.reddit_client import RedditClient
from zaza.api.stocktwits_client import StockTwitsClient
from zaza.cache.store import FileCache
from zaza.config import (
    get_reddit_client_id,
    get_reddit_client_secret,
    has_reddit_credentials,
)
from zaza.utils.sentiment import aggregate_sentiment, score_social_post

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP, cache: FileCache) -> None:
    """Register social sentiment tool on the MCP server."""

    @mcp.tool()
    async def get_social_sentiment(ticker: str) -> str:
        """Analyze social media sentiment for a ticker from Reddit and StockTwits.

        Gracefully degrades without Reddit credentials (StockTwits only).
        Cached for 1 hour.
        """
        try:
            ticker_upper = ticker.upper()

            # Check cache
            cache_key = cache.make_key("social_sentiment", ticker=ticker_upper)
            cached = cache.get(cache_key, "social_sentiment")
            if cached is not None:
                return json.dumps(cached, default=str)

            all_scores: list[dict[str, Any]] = []

            # Reddit (optional)
            reddit_data: dict[str, Any] = {
                "available": False,
                "post_count": 0,
                "posts": [],
            }
            if has_reddit_credentials():
                try:
                    client_id = get_reddit_client_id()
                    client_secret = get_reddit_client_secret()
                    if client_id and client_secret:
                        reddit_client = RedditClient(client_id, client_secret, cache)
                        posts = reddit_client.get_ticker_mentions(ticker_upper)
                        scored_posts = []
                        for post in posts:
                            text = f"{post.get('title', '')} {post.get('selftext', '')}"
                            sentiment_data = score_social_post(text)
                            all_scores.append(sentiment_data)
                            scored_posts.append({
                                "subreddit": post.get("subreddit", ""),
                                "title": post.get("title", ""),
                                "score": post.get("score", 0),
                                **sentiment_data,
                            })
                        reddit_data = {
                            "available": True,
                            "post_count": len(posts),
                            "posts": scored_posts[:10],  # top 10
                        }
                except Exception as e:
                    logger.warning("reddit_sentiment_error", ticker=ticker, error=str(e))
                    reddit_data["error"] = str(e)

            # StockTwits (always available, no API key needed)
            st_data: dict[str, Any] = {
                "message_count": 0,
                "messages": [],
            }
            try:
                st_client = StockTwitsClient(cache)
                st_result = await st_client.get_ticker_stream(ticker_upper)
                messages = st_result.get("messages", [])
                scored_messages = []
                for msg in messages:
                    body = msg.get("body", "")
                    sentiment_data = score_social_post(body)
                    all_scores.append(sentiment_data)
                    scored_messages.append({
                        "body": body[:200],
                        "user": msg.get("user", ""),
                        **sentiment_data,
                    })
                st_data = {
                    "message_count": len(messages),
                    "messages": scored_messages[:10],  # top 10
                }
            except Exception as e:
                logger.warning("stocktwits_sentiment_error", ticker=ticker, error=str(e))
                st_data["error"] = str(e)

            # Aggregate all scores
            agg = aggregate_sentiment(all_scores)

            result: dict[str, Any] = {
                "ticker": ticker_upper,
                "aggregate": agg,
                "reddit": reddit_data,
                "stocktwits": st_data,
            }
            cache.set(cache_key, "social_sentiment", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("get_social_sentiment_error", ticker=ticker, error=str(e))
            return json.dumps({"error": f"Failed to get social sentiment for {ticker}: {e}"})
