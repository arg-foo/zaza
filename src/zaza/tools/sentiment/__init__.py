"""Sentiment analysis tools.

Provides 4 MCP tools for sentiment analysis:
- get_news_sentiment: news headline sentiment scoring
- get_social_sentiment: Reddit + StockTwits combined sentiment
- get_insider_sentiment: insider transaction pattern analysis
- get_fear_greed_index: CNN Fear & Greed Index
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.tools.sentiment.insider import register as register_insider
from zaza.tools.sentiment.market import register as register_market
from zaza.tools.sentiment.news import register as register_news
from zaza.tools.sentiment.social import register as register_social


def register_sentiment_tools(mcp: FastMCP) -> None:
    """Register all 4 sentiment tools on the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    register_news(mcp, yf, cache)
    register_social(mcp, cache)
    register_insider(mcp, yf, cache)
    register_market(mcp, cache)
