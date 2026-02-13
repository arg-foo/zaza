"""Reddit API client using PRAW for social sentiment data."""

from __future__ import annotations

import time
from typing import Any

import structlog

from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


class RedditClient:
    """Cached Reddit client for ticker mention analysis."""

    def __init__(self, client_id: str, client_secret: str, cache: FileCache) -> None:
        import praw
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="Zaza/1.0 Financial Research"
        )
        self.cache = cache

    def get_ticker_mentions(
        self, ticker: str, subreddits: list[str] | None = None, days: int = 7
    ) -> list[dict[str, Any]]:
        """Search subreddits for ticker mentions."""
        subreddits = subreddits or ["wallstreetbets", "stocks", "investing"]
        cache_key = self.cache.make_key(
            "reddit_mentions", ticker=ticker, subs="_".join(sorted(subreddits)), days=days
        )
        cached = self.cache.get(cache_key, "social_sentiment")
        if cached is not None:
            return cached

        posts: list[dict[str, Any]] = []
        cutoff = time.time() - (days * 86400)
        try:
            for sub_name in subreddits:
                try:
                    subreddit = self.reddit.subreddit(sub_name)
                    for post in subreddit.search(f"${ticker}", time_filter="week", limit=25):
                        if post.created_utc >= cutoff:
                            posts.append({
                                "subreddit": sub_name,
                                "title": post.title,
                                "score": post.score,
                                "num_comments": post.num_comments,
                                "created_utc": post.created_utc,
                                "url": post.url,
                                "selftext": (post.selftext or "")[:500],
                            })
                except Exception as e:
                    logger.warning("reddit_subreddit_error", subreddit=sub_name, error=str(e))
            posts.sort(key=lambda p: p["score"], reverse=True)
            self.cache.set(cache_key, "social_sentiment", posts)
        except Exception as e:
            logger.warning("reddit_error", ticker=ticker, error=str(e))
        return posts
