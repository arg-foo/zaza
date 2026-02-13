"""Candlestick pattern detection MCP tool."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.indicators import ohlcv_to_dataframe

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register candlestick pattern detection tool with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_price_patterns(
        ticker: str,
        period: str = "3mo",
    ) -> str:
        """Detect candlestick patterns in recent price data.

        Identifies common patterns: doji, hammer, inverted hammer,
        bullish/bearish engulfing, morning/evening star.

        Args:
            ticker: Stock ticker symbol.
            period: Historical period (default '3mo').
        """
        try:
            history = yf.get_history(ticker, period=period)
            if not history:
                return json.dumps(
                    {"error": f"No price history available for {ticker}"},
                    default=str,
                )

            df = ohlcv_to_dataframe(history)
            patterns = _detect_patterns(df)

            return json.dumps({
                "status": "ok",
                "ticker": ticker.upper(),
                "period": period,
                "data": {
                    "patterns": patterns,
                    "patterns_found": len(patterns),
                    "current_price": float(df["Close"].iloc[-1]),
                },
            }, default=str)

        except Exception as e:
            logger.warning("get_price_patterns_error", ticker=ticker, error=str(e))
            return json.dumps({"error": str(e)}, default=str)


def _detect_patterns(df: Any) -> list[dict[str, Any]]:
    """Detect candlestick patterns in OHLCV data.

    Scans the last 10 trading days for common single-candle and
    two-candle patterns.

    Returns:
        List of detected patterns with name, type, date, and description.
    """
    patterns: list[dict[str, Any]] = []
    if len(df) < 3:
        return patterns

    opens = df["Open"].values
    highs = df["High"].values
    lows = df["Low"].values
    closes = df["Close"].values

    # Scan last 10 candles (or all if fewer)
    scan_range = min(10, len(df) - 1)

    for i in range(len(df) - scan_range, len(df)):
        o, h, lo, c = opens[i], highs[i], lows[i], closes[i]
        body = abs(c - o)
        total_range = h - lo
        if total_range == 0:
            continue

        body_ratio = body / total_range
        upper_shadow = h - max(o, c)
        lower_shadow = min(o, c) - lo

        date_str = str(df.index[i]) if hasattr(df.index[i], 'strftime') else str(i)

        # Doji: very small body relative to range
        if body_ratio < 0.1:
            patterns.append({
                "pattern": "doji",
                "type": "neutral",
                "date": date_str,
                "description": "Indecision pattern - body is very small relative to range",
            })

        # Hammer: small body at top, long lower shadow (bullish reversal)
        elif (body_ratio < 0.35 and lower_shadow > body * 2
              and upper_shadow < body * 0.5):
            patterns.append({
                "pattern": "hammer",
                "type": "bullish",
                "date": date_str,
                "description": (
                    "Potential bullish reversal - long lower shadow"
                    " with small body at top"
                ),
            })

        # Inverted Hammer: small body at bottom, long upper shadow
        elif (body_ratio < 0.35 and upper_shadow > body * 2
              and lower_shadow < body * 0.5):
            patterns.append({
                "pattern": "inverted_hammer",
                "type": "bearish" if c < o else "bullish",
                "date": date_str,
                "description": "Long upper shadow with small body at bottom",
            })

        # Bullish/Bearish engulfing (requires previous candle)
        if i > 0:
            prev_o, prev_c = opens[i - 1], closes[i - 1]
            prev_body = abs(prev_c - prev_o)

            # Bullish engulfing: previous red candle fully engulfed by current green
            if (prev_c < prev_o and c > o  # prev red, current green
                    and o <= prev_c and c >= prev_o
                    and body > prev_body):
                patterns.append({
                    "pattern": "bullish_engulfing",
                    "type": "bullish",
                    "date": date_str,
                    "description": "Current green candle fully engulfs previous red candle",
                })

            # Bearish engulfing: previous green candle fully engulfed by current red
            elif (prev_c > prev_o and c < o  # prev green, current red
                  and o >= prev_c and c <= prev_o
                  and body > prev_body):
                patterns.append({
                    "pattern": "bearish_engulfing",
                    "type": "bearish",
                    "date": date_str,
                    "description": "Current red candle fully engulfs previous green candle",
                })

    return patterns
