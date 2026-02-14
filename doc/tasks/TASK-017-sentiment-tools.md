# TASK-017: Sentiment Analysis Tools

## Task ID
TASK-017

## Status
COMPLETED

## Title
Implement Sentiment Analysis Tools (4 Tools)

## Description
Implement 4 sentiment analysis MCP tools: `get_news_sentiment`, `get_social_sentiment`, `get_insider_sentiment`, and `get_fear_greed_index`. These combine news NLP scoring, social media signals, insider behavior analysis, and market-wide fear/greed measurement.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/tools/sentiment/news.py` — `get_news_sentiment(ticker, days=7)`:
  - Fetches news from yfinance, scores each headline, returns aggregate sentiment score (-1 to +1), trend, article count, per-article scores
- [ ] `src/zaza/tools/sentiment/social.py` — `get_social_sentiment(ticker)`:
  - Reddit (r/wallstreetbets, r/stocks) + StockTwits mention volume and sentiment distribution
  - Gracefully degrades without Reddit credentials (StockTwits only)
  - Returns mention volume (24h, 7d), trend, sentiment %, trending rank
- [ ] `src/zaza/tools/sentiment/insider.py` — `get_insider_sentiment(ticker, months=6)`:
  - Analyzes insider transactions for net buying ratio, cluster detection, $ bought vs sold
  - Returns sentiment score (strong buy / buy / neutral / sell / strong sell)
- [ ] `src/zaza/tools/sentiment/market.py` — `get_fear_greed_index()`:
  - Scrapes CNN Fear & Greed Index; returns value (0-100), classification, 1w/1m ago values, component breakdown
- [ ] All 4 tools registered as MCP tools via `register_sentiment_tools(app)`
- [ ] Each uses appropriate cache TTL (news: 2h, social: 1h, insider: 24h, F&G: 4h)

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with mocked data sources; test graceful degradation (missing Reddit creds)
- [ ] **Reliability**: Each tool works independently — one failing source doesn't break others
- [ ] **Observability**: Log when operating in degraded mode (e.g., "Reddit credentials not configured")

## Dependencies
- TASK-001: Project scaffolding
- TASK-003: File-based cache
- TASK-004: yfinance client (news, insider trades)
- TASK-006: MCP server entry point
- TASK-007: Reddit & StockTwits clients
- TASK-011: Shared sentiment utilities

## Technical Notes

### Fear & Greed Index Scraping
```python
import httpx
from bs4 import BeautifulSoup

async def scrape_fear_greed() -> dict:
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers={"User-Agent": "..."})
        data = resp.json()
        return {
            "value": data["fear_and_greed"]["score"],
            "classification": data["fear_and_greed"]["rating"],
            "previous_close": data["fear_and_greed_historical"]["previousClose"],
            "one_week_ago": data["fear_and_greed_historical"]["oneWeekAgo"],
            "one_month_ago": data["fear_and_greed_historical"]["oneMonthAgo"],
        }
```

### Implementation Hints
1. News sentiment scoring uses the keyword-based approach from utils/sentiment.py
2. Social sentiment: combine Reddit + StockTwits scores when both available; weight by recency
3. Insider cluster detection: 3+ insiders buying within 14 days = strong bullish signal
4. Fear & Greed endpoint may change — add fallback parsing logic
5. CNN Fear & Greed components: market momentum, stock price strength, stock price breadth, put/call ratio, junk bond demand, market volatility, safe haven demand

## Estimated Complexity
**Medium** (6-8 hours)

## References
- ZAZA_ARCHITECTURE.md Section 7.6 (Sentiment Analysis Tools)
- ZAZA_ARCHITECTURE.md Section 6.2.7 (Sentiment Analysis Agent)
