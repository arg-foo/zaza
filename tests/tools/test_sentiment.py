"""Tests for sentiment analysis tools (TASK-017)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Synthetic test data
# ---------------------------------------------------------------------------

FAKE_NEWS = [
    {
        "title": "AAPL beats earnings expectations, stock surges",
        "link": "https://example.com/1",
        "publisher": "Reuters",
        "providerPublishTime": 1700000000,
    },
    {
        "title": "Apple faces lawsuit over privacy concerns",
        "link": "https://example.com/2",
        "publisher": "Bloomberg",
        "providerPublishTime": 1699990000,
    },
    {
        "title": "Tech sector shows strong growth in Q4",
        "link": "https://example.com/3",
        "publisher": "CNBC",
        "providerPublishTime": 1699980000,
    },
]

FAKE_REDDIT_POSTS = [
    {
        "subreddit": "wallstreetbets",
        "title": "AAPL to the moon! Strong earnings beat!",
        "score": 500,
        "num_comments": 200,
        "created_utc": 1700000000.0,
        "url": "https://reddit.com/1",
        "selftext": "Amazing earnings report",
    },
    {
        "subreddit": "stocks",
        "title": "Apple weak guidance concerns me",
        "score": 100,
        "num_comments": 50,
        "created_utc": 1699990000.0,
        "url": "https://reddit.com/2",
        "selftext": "Guidance was lowered",
    },
]

FAKE_STOCKTWITS = {
    "ticker": "AAPL",
    "messages": [
        {
            "body": "AAPL bullish breakout incoming!",
            "sentiment": "Bullish",
            "created_at": "2024-01-01",
            "user": "user1",
        },
        {
            "body": "Apple decline looks bad",
            "sentiment": "Bearish",
            "created_at": "2024-01-01",
            "user": "user2",
        },
        {
            "body": "Just holding",
            "sentiment": None,
            "created_at": "2024-01-01",
            "user": "user3",
        },
    ],
    "message_count": 3,
    "cursor": {},
}

FAKE_INSIDER_TRANSACTIONS = [
    {"type": "Purchase", "shares": 10000, "value": 1500000, "insider": "CEO"},
    {"type": "Purchase", "shares": 5000, "value": 750000, "insider": "CFO"},
    {"type": "Purchase", "shares": 3000, "value": 450000, "insider": "CTO"},
    {"type": "Sale", "shares": 2000, "value": 300000, "insider": "VP"},
]

FAKE_FEAR_GREED_RESPONSE = {
    "fear_and_greed": {
        "score": 65.0,
        "rating": "Greed",
        "timestamp": "2024-01-15T10:00:00Z",
        "previous_close": 62.0,
        "previous_1_week": 55.0,
        "previous_1_month": 45.0,
        "previous_1_year": 70.0,
    },
    "fear_and_greed_historical": {
        "data": [
            {"x": 1705300000000, "y": 65.0, "rating": "Greed"},
            {"x": 1705200000000, "y": 62.0, "rating": "Greed"},
        ]
    },
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_cache() -> MagicMock:
    cache = MagicMock()
    cache.get.return_value = None
    cache.make_key.side_effect = lambda *a, **kw: f"key_{'_'.join(str(v) for v in a)}"
    return cache


@pytest.fixture()
def mock_yf(mock_cache: MagicMock) -> MagicMock:
    yf = MagicMock()
    yf.cache = mock_cache
    yf.get_news.return_value = FAKE_NEWS
    yf.get_insider_transactions.return_value = FAKE_INSIDER_TRANSACTIONS
    return yf


# ===========================================================================
# news.py tests
# ===========================================================================

class TestGetNewsSentiment:
    """get_news_sentiment tool tests."""

    async def test_returns_sentiment_scores(
        self, mock_yf: MagicMock, mock_cache: MagicMock
    ) -> None:
        from zaza.tools.sentiment.news import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_news_sentiment"]("AAPL"))
        assert result["ticker"] == "AAPL"
        assert "aggregate" in result
        assert "articles" in result
        assert len(result["articles"]) == 3
        # Aggregate should have sentiment fields
        agg = result["aggregate"]
        assert "sentiment" in agg
        assert "score" in agg
        assert "confidence" in agg

    async def test_bullish_headline_scores_positive(
        self, mock_yf: MagicMock, mock_cache: MagicMock
    ) -> None:
        mock_yf.get_news.return_value = [{
            "title": "Company beats earnings and surges to record high",
            "link": "https://x.com/1",
            "publisher": "R",
        }]
        from zaza.tools.sentiment.news import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_news_sentiment"]("AAPL"))
        assert result["articles"][0]["score"] > 0

    async def test_no_news_returns_neutral(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        mock_yf.get_news.return_value = []
        from zaza.tools.sentiment.news import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_news_sentiment"]("XYZ"))
        assert result["aggregate"]["sentiment"] == "neutral"
        assert result["articles"] == []

    async def test_caches_result(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        from zaza.tools.sentiment.news import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        await tools["get_news_sentiment"]("AAPL")
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][1] == "news_sentiment"


# ===========================================================================
# social.py tests
# ===========================================================================

class TestGetSocialSentiment:
    """get_social_sentiment tool tests."""

    @patch("zaza.tools.sentiment.social.get_reddit_client_secret", return_value="fake_secret")
    @patch("zaza.tools.sentiment.social.get_reddit_client_id", return_value="fake_id")
    @patch("zaza.tools.sentiment.social.has_reddit_credentials", return_value=True)
    @patch("zaza.tools.sentiment.social.RedditClient")
    @patch("zaza.tools.sentiment.social.StockTwitsClient")
    async def test_combined_reddit_and_stocktwits(
        self,
        MockStockTwits: MagicMock,
        MockReddit: MagicMock,
        mock_has_creds: MagicMock,
        mock_get_id: MagicMock,
        mock_get_secret: MagicMock,
        mock_cache: MagicMock,
    ) -> None:
        reddit_instance = MagicMock()
        reddit_instance.get_ticker_mentions.return_value = FAKE_REDDIT_POSTS
        MockReddit.return_value = reddit_instance

        st_instance = MagicMock()
        st_instance.get_ticker_stream = AsyncMock(return_value=FAKE_STOCKTWITS)
        MockStockTwits.return_value = st_instance

        from zaza.tools.sentiment.social import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_cache)

        result = json.loads(await tools["get_social_sentiment"]("AAPL"))
        assert result["ticker"] == "AAPL"
        assert "aggregate" in result
        assert "reddit" in result
        assert "stocktwits" in result
        assert result["reddit"]["post_count"] == 2

    @patch("zaza.tools.sentiment.social.has_reddit_credentials", return_value=False)
    @patch("zaza.tools.sentiment.social.StockTwitsClient")
    async def test_graceful_degradation_without_reddit(
        self,
        MockStockTwits: MagicMock,
        mock_has_creds: MagicMock,
        mock_cache: MagicMock,
    ) -> None:
        """When Reddit credentials are absent, tool should work with StockTwits only."""
        st_instance = MagicMock()
        st_instance.get_ticker_stream = AsyncMock(return_value=FAKE_STOCKTWITS)
        MockStockTwits.return_value = st_instance

        from zaza.tools.sentiment.social import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_cache)

        result = json.loads(await tools["get_social_sentiment"]("AAPL"))
        assert result["ticker"] == "AAPL"
        assert result["reddit"]["post_count"] == 0
        assert result["reddit"]["available"] is False
        assert result["stocktwits"]["message_count"] == 3

    @patch("zaza.tools.sentiment.social.has_reddit_credentials", return_value=False)
    @patch("zaza.tools.sentiment.social.StockTwitsClient")
    async def test_stocktwits_only_caches(
        self,
        MockStockTwits: MagicMock,
        mock_has_creds: MagicMock,
        mock_cache: MagicMock,
    ) -> None:
        st_instance = MagicMock()
        st_instance.get_ticker_stream = AsyncMock(return_value=FAKE_STOCKTWITS)
        MockStockTwits.return_value = st_instance

        from zaza.tools.sentiment.social import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_cache)

        await tools["get_social_sentiment"]("AAPL")
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][1] == "social_sentiment"


# ===========================================================================
# insider.py tests
# ===========================================================================

class TestGetInsiderSentiment:
    """get_insider_sentiment tool tests."""

    async def test_returns_insider_analysis(
        self, mock_yf: MagicMock, mock_cache: MagicMock
    ) -> None:
        from zaza.tools.sentiment.insider import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_insider_sentiment"]("AAPL"))
        assert result["ticker"] == "AAPL"
        assert "analysis" in result
        assert "transactions" in result
        # Our fake data has 3 buys and 1 sell => should be bullish
        assert result["analysis"]["buys"] == 3
        assert result["analysis"]["sells"] == 1
        assert result["analysis"]["cluster_buying"] is True

    async def test_no_insider_data(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        mock_yf.get_insider_transactions.return_value = []
        from zaza.tools.sentiment.insider import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_insider_sentiment"]("XYZ"))
        assert result["analysis"]["sentiment"] == "neutral"
        assert result["transactions"] == []

    async def test_insider_caches_result(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        from zaza.tools.sentiment.insider import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        await tools["get_insider_sentiment"]("AAPL")
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][1] == "insider_sentiment"


# ===========================================================================
# market.py tests
# ===========================================================================

class TestGetFearGreedIndex:
    """get_fear_greed_index tool tests."""

    @patch("zaza.tools.sentiment.market.httpx.AsyncClient")
    async def test_returns_fear_greed_data(
        self, MockClient: MagicMock, mock_cache: MagicMock
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = FAKE_FEAR_GREED_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client

        from zaza.tools.sentiment.market import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_cache)

        result = json.loads(await tools["get_fear_greed_index"]())
        assert "score" in result
        assert "rating" in result
        assert result["score"] == 65.0
        assert result["rating"] == "Greed"

    @patch("zaza.tools.sentiment.market.httpx.AsyncClient")
    async def test_fear_greed_includes_historical(
        self, MockClient: MagicMock, mock_cache: MagicMock
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = FAKE_FEAR_GREED_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client

        from zaza.tools.sentiment.market import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_cache)

        result = json.loads(await tools["get_fear_greed_index"]())
        assert "previous_close" in result
        assert "previous_1_week" in result
        assert "previous_1_month" in result
        assert "previous_1_year" in result

    @patch("zaza.tools.sentiment.market.httpx.AsyncClient")
    async def test_fear_greed_http_error(
        self, MockClient: MagicMock, mock_cache: MagicMock
    ) -> None:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client

        from zaza.tools.sentiment.market import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_cache)

        result = json.loads(await tools["get_fear_greed_index"]())
        assert "error" in result

    @patch("zaza.tools.sentiment.market.httpx.AsyncClient")
    async def test_fear_greed_caches_result(
        self, MockClient: MagicMock, mock_cache: MagicMock
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = FAKE_FEAR_GREED_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client

        from zaza.tools.sentiment.market import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_cache)

        await tools["get_fear_greed_index"]()
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][1] == "fear_greed"


# ===========================================================================
# __init__.py register_sentiment_tools tests
# ===========================================================================

class TestRegisterSentimentTools:
    """Test that register_sentiment_tools registers all 4 tools."""

    async def test_registers_all_tools(self) -> None:
        from zaza.tools.sentiment import register_sentiment_tools
        mcp = MagicMock()
        registered: list[str] = []
        mcp.tool.return_value = lambda fn: registered.append(fn.__name__) or fn
        register_sentiment_tools(mcp)
        expected = {
            "get_news_sentiment",
            "get_social_sentiment",
            "get_insider_sentiment",
            "get_fear_greed_index",
        }
        assert set(registered) == expected


# ===========================================================================
# Error handling tests
# ===========================================================================

class TestSentimentErrorHandling:
    """Ensure tools return JSON error dicts on exceptions, never raise."""

    async def test_news_exception(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        mock_yf.get_news.side_effect = Exception("API error")
        from zaza.tools.sentiment.news import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_news_sentiment"]("AAPL"))
        assert "error" in result

    async def test_insider_exception(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        mock_yf.get_insider_transactions.side_effect = Exception("timeout")
        from zaza.tools.sentiment.insider import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_insider_sentiment"]("AAPL"))
        assert "error" in result
