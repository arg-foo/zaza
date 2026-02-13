"""Tests for Reddit and StockTwits API clients."""

from unittest.mock import MagicMock

import httpx
import pytest
import respx

from zaza.api.reddit_client import RedditClient
from zaza.api.stocktwits_client import STOCKTWITS_BASE, StockTwitsClient
from zaza.cache.store import FileCache


@pytest.fixture
def cache(tmp_path):
    return FileCache(cache_dir=tmp_path)


# --- StockTwits Tests ---

@pytest.fixture
def st_client(cache):
    return StockTwitsClient(cache)


@respx.mock
async def test_stocktwits_get_ticker_stream(st_client):
    respx.get(f"{STOCKTWITS_BASE}/streams/symbol/AAPL.json").mock(
        return_value=httpx.Response(200, json={
            "messages": [
                {"body": "AAPL to the moon", "entities": {"sentiment": {"basic": "Bullish"}},
                 "created_at": "2024-01-15", "user": {"username": "trader1"}},
                {"body": "Selling AAPL", "entities": {"sentiment": {"basic": "Bearish"}},
                 "created_at": "2024-01-14", "user": {"username": "trader2"}},
            ],
            "cursor": {"max": 100},
        })
    )
    result = await st_client.get_ticker_stream("AAPL")
    assert result["ticker"] == "AAPL"
    assert result["message_count"] == 2
    assert result["messages"][0]["sentiment"] == "Bullish"


@respx.mock
async def test_stocktwits_caches_response(st_client):
    route = respx.get(f"{STOCKTWITS_BASE}/streams/symbol/AAPL.json").mock(
        return_value=httpx.Response(200, json={"messages": [], "cursor": {}})
    )
    await st_client.get_ticker_stream("AAPL")
    await st_client.get_ticker_stream("AAPL")
    assert route.call_count == 1


@respx.mock
async def test_stocktwits_error_returns_empty(st_client):
    respx.get(f"{STOCKTWITS_BASE}/streams/symbol/BAD.json").mock(
        return_value=httpx.Response(404)
    )
    result = await st_client.get_ticker_stream("BAD")
    assert result["messages"] == []
    assert result["message_count"] == 0


# --- Reddit Tests ---

def test_reddit_client_get_ticker_mentions(cache):
    # Bypass __init__ to avoid importing praw at construction time
    client = RedditClient.__new__(RedditClient)
    client.cache = cache
    client.reddit = MagicMock()

    mock_post = MagicMock()
    mock_post.title = "AAPL earnings beat"
    mock_post.score = 500
    mock_post.num_comments = 100
    mock_post.created_utc = 9999999999.0
    mock_post.url = "https://reddit.com/r/stocks/test"
    mock_post.selftext = "Great quarter"

    mock_subreddit = MagicMock()
    mock_subreddit.search.return_value = [mock_post]
    client.reddit.subreddit.return_value = mock_subreddit

    result = client.get_ticker_mentions("AAPL", subreddits=["stocks"])
    assert len(result) == 1
    assert result[0]["title"] == "AAPL earnings beat"
    assert result[0]["score"] == 500


def test_reddit_client_caches_results(cache):
    client = RedditClient.__new__(RedditClient)
    client.reddit = MagicMock()
    client.cache = cache

    mock_post = MagicMock()
    mock_post.title = "Test"
    mock_post.score = 1
    mock_post.num_comments = 0
    mock_post.created_utc = 9999999999.0
    mock_post.url = "https://test.com"
    mock_post.selftext = ""

    mock_sub = MagicMock()
    mock_sub.search.return_value = [mock_post]
    client.reddit.subreddit.return_value = mock_sub

    client.get_ticker_mentions("TSLA", subreddits=["stocks"])
    client.get_ticker_mentions("TSLA", subreddits=["stocks"])
    assert client.reddit.subreddit.call_count == 1  # cached second time
