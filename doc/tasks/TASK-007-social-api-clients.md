# TASK-007: Reddit & StockTwits API Clients

## Task ID
TASK-007

## Status
COMPLETED

## Title
Implement Reddit & StockTwits API Clients

## Description
Implement two API clients for social sentiment data: `src/zaza/api/reddit_client.py` (using PRAW for Reddit API) and `src/zaza/api/stocktwits_client.py` (using httpx for StockTwits public API). These are used by the `get_social_sentiment` tool.

Reddit requires API credentials (free registration); StockTwits requires none. Both clients gracefully degrade when unavailable.

## Acceptance Criteria

### Functional Requirements
- [ ] `RedditClient` class in `src/zaza/api/reddit_client.py`
  - Constructor accepts `client_id` and `client_secret`
  - `get_ticker_mentions(ticker: str, subreddits: list[str], days: int = 7) -> list[dict]` — searches for ticker mentions in specified subreddits
  - Returns posts with: title, score, num_comments, created_utc, selftext, url
  - Default subreddits: `["wallstreetbets", "stocks", "investing"]`
  - Integrates with FileCache
- [ ] `StockTwitsClient` class in `src/zaza/api/stocktwits_client.py`
  - `get_ticker_stream(ticker: str) -> dict` — recent messages for a ticker with sentiment labels
  - Uses `https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json`
  - Uses `httpx.AsyncClient`
  - Returns messages with: body, sentiment (bullish/bearish/neutral), created_at, user
  - Integrates with FileCache
- [ ] Reddit client returns empty list when credentials are missing (checked via `config.has_reddit_credentials()`)
- [ ] Both clients handle API errors gracefully

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with mocked PRAW and mocked HTTP responses
- [ ] **Observability**: Logging for API calls and degraded mode
- [ ] **Security**: Reddit credentials never logged; accessed only via config
- [ ] **Reliability**: Timeout handling for both APIs

## Dependencies
- TASK-001: Project scaffolding
- TASK-002: Configuration module
- TASK-003: File-based cache system

## Technical Notes

### Reddit Client
```python
import praw
from zaza.config import has_reddit_credentials

class RedditClient:
    def __init__(self, client_id: str, client_secret: str, cache: FileCache):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="Zaza/1.0"
        )
        self.cache = cache

    def get_ticker_mentions(self, ticker: str, subreddits: list[str] = None, days: int = 7) -> list[dict]:
        subreddits = subreddits or ["wallstreetbets", "stocks", "investing"]
        # Search each subreddit for ticker mentions
        # Filter by time (days), sort by relevance
        # Return structured post data
```

### StockTwits Client
```python
import httpx

class StockTwitsClient:
    BASE = "https://api.stocktwits.com/api/2"

    def __init__(self, cache: FileCache):
        self.cache = cache

    async def get_ticker_stream(self, ticker: str) -> dict:
        url = f"{self.BASE}/streams/symbol/{ticker}.json"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
            return resp.json()
```

### Implementation Hints
1. PRAW is synchronous — may need to wrap in `asyncio.to_thread()` for async context
2. StockTwits API returns sentiment labels directly on messages (bullish/bearish)
3. StockTwits has rate limits — respect 429 responses
4. Reddit search uses `subreddit.search(query=f"${ticker}", time_filter="week")`

## Estimated Complexity
**Small** (3-4 hours)

## References
- ZAZA_ARCHITECTURE.md Section 9.1 (Reddit, StockTwits)
- PRAW documentation: https://praw.readthedocs.io/
- StockTwits API: https://api.stocktwits.com/developers/docs/api
