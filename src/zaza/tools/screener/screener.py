"""Pure-Python yfinance stock screener with TA scoring.

Tools:
  - screen_stocks: Screen stocks by scan type with TA scoring.
  - get_screening_strategies: List available screening strategies.
  - get_buy_sell_levels: Get buy/sell support/resistance levels for a ticker.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import structlog
import yfinance as yf
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.config import (
    MARKET_EXCHANGE_MAP,
    SCREENER_DEFAULT_MARKET,
    SCREENER_MAX_CANDIDATES,
    SCREENER_PAGE_SIZE,
    SCREENER_TA_CONCURRENCY,
    SCREENER_TOP_N,
)
from zaza.tools.screener.scan_types import SCAN_TYPES
from zaza.utils.indicators import (
    compute_fibonacci_levels,
    compute_pivot_points,
    compute_sma,
    ohlcv_to_dataframe,
)

logger = structlog.get_logger(__name__)

# Regex to validate ticker: alphanumeric, dots, hyphens; max 10 chars
_TICKER_PATTERN = re.compile(r"^[A-Za-z0-9.\-]{1,10}$")


def _resolve_exchange(market: str) -> str:
    """Resolve market name to yfinance exchange code.

    Raises:
        ValueError: If market is not supported.
    """
    market_upper = market.upper()
    if market_upper not in MARKET_EXCHANGE_MAP:
        supported = ", ".join(sorted(MARKET_EXCHANGE_MAP.keys()))
        raise ValueError(
            f"Unsupported market '{market}'. Supported: {supported}"
        )
    return MARKET_EXCHANGE_MAP[market_upper]


async def _score_symbol(
    yf_client: YFinanceClient,
    symbol: str,
    quote: dict[str, Any],
    score_fn: Any,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any] | None:
    """Fetch history and score a single symbol, respecting concurrency limit."""
    async with semaphore:
        try:
            records = await asyncio.to_thread(
                yf_client.get_history, symbol, period="1y"
            )
            if not records:
                return None
            df = ohlcv_to_dataframe(records)
            if len(df) < 20:
                return None
            result = score_fn(df, quote)
            return {
                "symbol": symbol,
                "score": result["score"],
                "signals": result["signals"],
                "price": quote.get("regularMarketPrice"),
                "change_pct": quote.get("regularMarketChangePercent"),
                "volume": quote.get("averageDailyVolume3Month"),
            }
        except Exception as e:
            logger.debug("score_symbol_error", symbol=symbol, error=str(e))
            return None


def register(mcp: FastMCP) -> None:
    """Register screener tools with the MCP server."""
    cache = FileCache()
    yf_client = YFinanceClient(cache)

    @mcp.tool()
    async def screen_stocks(
        scan_type: str,
        market: str = SCREENER_DEFAULT_MARKET,
    ) -> str:
        """Screen stocks using yfinance with TA-based scoring.

        Args:
            scan_type: Type of scan. One of: breakout, momentum, consolidation,
                       volume, reversal, ipo, short_squeeze, bullish, bearish.
            market: Market to scan (default NASDAQ). Supported: NASDAQ, NYSE, AMEX.

        Returns:
            JSON with scored and ranked screening results.
        """
        try:
            # Validate scan type
            scan_lower = scan_type.lower()
            if scan_lower not in SCAN_TYPES:
                return json.dumps(
                    {
                        "error": f"Unknown scan type '{scan_type}'. "
                        f"Available: {list(SCAN_TYPES.keys())}"
                    },
                    default=str,
                )

            # Validate market
            try:
                exchange_code = _resolve_exchange(market)
            except ValueError as e:
                return json.dumps({"error": str(e)}, default=str)

            # Check cache
            cache_key = cache.make_key(
                "screen", scan_type=scan_lower, market=market.upper()
            )
            cached = cache.get(cache_key, "screener_results")
            if cached is not None:
                return json.dumps(cached, default=str)

            config = SCAN_TYPES[scan_lower]

            # Phase 1: Build query and paginate through all yfinance results
            query = config.build_query(exchange_code)
            quotes: list[dict[str, Any]] = []
            offset = 0

            while offset < SCREENER_MAX_CANDIDATES:
                screen_result = await asyncio.to_thread(
                    yf.screen,
                    query,
                    size=SCREENER_PAGE_SIZE,
                    offset=offset,
                    sortField=config.sort_field,
                    sortAsc=config.sort_asc,
                )
                page_quotes = screen_result.get("quotes", [])
                if not page_quotes:
                    break
                quotes.extend(page_quotes)
                total = screen_result.get("total", 0)
                offset += len(page_quotes)
                logger.debug(
                    "screen_page_fetched",
                    scan_type=scan_lower,
                    page_size=len(page_quotes),
                    total_so_far=len(quotes),
                    server_total=total,
                )
                # Stop if we've fetched all available results
                if offset >= total:
                    break

            if not quotes:
                result = {
                    "scan_type": scan_lower,
                    "market": market.upper(),
                    "total_results": 0,
                    "results": [],
                }
                return json.dumps(result, default=str)

            # Phase 2: Score each candidate with TA indicators
            semaphore = asyncio.Semaphore(SCREENER_TA_CONCURRENCY)
            tasks = [
                _score_symbol(
                    yf_client,
                    q["symbol"],
                    q,
                    config.score_candidate,
                    semaphore,
                )
                for q in quotes
                if "symbol" in q
            ]
            scored_results = await asyncio.gather(*tasks)

            # Filter None results and sort by score descending
            valid_results = [r for r in scored_results if r is not None]
            valid_results.sort(key=lambda x: x["score"], reverse=True)

            # Return top N
            top_results = valid_results[:SCREENER_TOP_N]

            result = {
                "scan_type": scan_lower,
                "market": market.upper(),
                "total_candidates": len(quotes),
                "total_results": len(top_results),
                "results": top_results,
            }

            # Cache results
            cache.set(cache_key, "screener_results", result)

            return json.dumps(result, default=str)

        except Exception as e:
            logger.warning("screen_stocks_error", scan_type=scan_type, error=str(e))
            return json.dumps({"error": str(e)}, default=str)

    @mcp.tool()
    async def get_screening_strategies() -> str:
        """Return available stock screening strategies.

        Returns:
            JSON with list of available strategies and their descriptions.
        """
        strategies = [
            {"name": cfg.name, "description": cfg.description}
            for cfg in SCAN_TYPES.values()
        ]
        return json.dumps({"strategies": strategies}, default=str)

    @mcp.tool()
    async def get_buy_sell_levels(
        ticker: str,
        market: str = SCREENER_DEFAULT_MARKET,
    ) -> str:
        """Get buy/sell support/resistance levels for a single ticker.

        Computes pivot points, Fibonacci retracement levels, and SMA-based
        buy/sell zones.

        Args:
            ticker: Stock ticker symbol.
            market: Market the ticker belongs to (default NASDAQ).
                    Supported: NASDAQ, NYSE, AMEX.

        Returns:
            JSON with pivot points, fibonacci levels, buy zone, sell zone.
        """
        try:
            # Validate ticker
            if not _TICKER_PATTERN.match(ticker):
                return json.dumps(
                    {"error": f"Invalid ticker format: '{ticker}'"},
                    default=str,
                )

            # Validate market
            try:
                _resolve_exchange(market)
            except ValueError as e:
                return json.dumps({"error": str(e)}, default=str)

            # Fetch history
            records = await asyncio.to_thread(
                yf_client.get_history, ticker.upper(), period="1y"
            )
            if not records:
                return json.dumps(
                    {"error": f"No price history found for {ticker.upper()}"},
                    default=str,
                )

            df = ohlcv_to_dataframe(records)
            if len(df) < 5:
                return json.dumps(
                    {"error": f"Insufficient price history for {ticker.upper()}"},
                    default=str,
                )

            # Compute levels
            pivots = compute_pivot_points(df)
            high = float(df["High"].max())
            low = float(df["Low"].min())
            fib = compute_fibonacci_levels(high, low)
            sma_data = compute_sma(df, periods=[20, 50, 200])

            # Derive buy and sell zones
            # Buy zone: between S1 and fib 618 level (support area)
            buy_lower = min(pivots["s2"], fib["level_786"])
            buy_upper = max(pivots["s1"], fib["level_618"])
            # Sell zone: between R1 and fib 236 level (resistance area)
            sell_lower = min(pivots["r1"], fib["level_236"])
            sell_upper = max(pivots["r2"], fib["level_0"])

            # Ensure buy zone is below sell zone
            if buy_upper > sell_lower:
                midpoint = (buy_upper + sell_lower) / 2
                buy_upper = round(midpoint - 0.01, 2)
                sell_lower = round(midpoint + 0.01, 2)

            # Prevent zone inversion from midpoint adjustment
            buy_lower = min(buy_lower, buy_upper)
            sell_lower = min(sell_lower, sell_upper)

            result = {
                "ticker": ticker.upper(),
                "current_price": sma_data.get("current_price"),
                "pivot_points": pivots,
                "fibonacci_levels": fib,
                "sma": sma_data.get("sma", {}),
                "buy_zone": {
                    "lower": round(buy_lower, 2),
                    "upper": round(buy_upper, 2),
                },
                "sell_zone": {
                    "lower": round(sell_lower, 2),
                    "upper": round(sell_upper, 2),
                },
            }

            return json.dumps(result, default=str)

        except Exception as e:
            logger.warning(
                "buy_sell_levels_error", ticker=ticker, error=str(e)
            )
            return json.dumps({"error": str(e)}, default=str)
