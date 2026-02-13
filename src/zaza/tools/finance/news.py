"""Company news MCP tool.

Tools:
  - get_company_news: Recent news articles for a ticker.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def _make_company_news(yf: YFinanceClient, ticker: str) -> str:
    """Build company news JSON from a YFinanceClient instance."""
    try:
        articles = yf.get_news(ticker)
        result: dict[str, Any] = {
            "ticker": ticker,
            "article_count": len(articles),
            "articles": articles,
        }
        return json.dumps(result, default=str)
    except Exception as e:
        logger.error("company_news_error", ticker=ticker, error=str(e))
        return json.dumps({"error": f"Failed to get news for {ticker}: {e}"})


def register(mcp: FastMCP) -> None:
    """Register company news tool with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_company_news(ticker: str) -> str:
        """Get recent news articles for a stock."""
        return _make_company_news(yf, ticker)
