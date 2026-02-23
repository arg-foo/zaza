"""PKScreener MCP tools -- stock screening via Docker sidecar.

Validates scan types against allowed list to prevent command injection.
No Zaza-level caching (PKScreener manages its own).
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.config import (
    MARKET_INDEX_MAP,
    PKSCREENER_DEFAULT_MARKET,
    PKSCREENER_SCAN_TIMEOUT,
    PKSCREENER_TICKER_TIMEOUT,
)
from zaza.tools.screener.docker import run_pkscreener

logger = structlog.get_logger(__name__)

# Allowed scan types -- validated before passing to Docker exec
# Each value has a "suffix" that goes after "X:{market_index}:" in the -o flag
SCAN_TYPES: dict[str, dict[str, str]] = {
    "breakout": {
        "name": "breakout",
        "description": "Stocks breaking out of consolidation patterns",
        "suffix": "9:2.5",
    },
    "momentum": {
        "name": "momentum",
        "description": "Stocks with strong upward momentum (RSI, MACD)",
        "suffix": "7",
    },
    "consolidation": {
        "name": "consolidation",
        "description": "Stocks in consolidation / narrow range",
        "suffix": "10",
    },
    "volume": {
        "name": "volume",
        "description": "Stocks with unusual volume activity",
        "suffix": "9:1",
    },
    "reversal": {
        "name": "reversal",
        "description": "Stocks showing potential reversal signals",
        "suffix": "6",
    },
    "ipo": {
        "name": "ipo",
        "description": "Recent IPO stocks with momentum",
        "suffix": "4",
    },
    "short_squeeze": {
        "name": "short_squeeze",
        "description": "Stocks with short squeeze potential",
        "suffix": "11",
    },
    "bullish": {
        "name": "bullish",
        "description": "Bullish pattern recognition",
        "suffix": "1",
    },
    "bearish": {
        "name": "bearish",
        "description": "Bearish pattern recognition",
        "suffix": "2",
    },
}

# Regex to validate scan type: only alphanumeric and underscore
_SAFE_PATTERN = re.compile(r"^[a-zA-Z0-9_]+$")


def _resolve_market_index(market: str) -> str:
    """Resolve market name to PKScreener index number.

    Raises:
        ValueError: If market is not supported.
    """
    market_upper = market.upper()
    if market_upper not in MARKET_INDEX_MAP:
        supported = ", ".join(sorted(MARKET_INDEX_MAP.keys()))
        raise ValueError(
            f"Unsupported market '{market}'. Supported: {supported}"
        )
    return MARKET_INDEX_MAP[market_upper]


def _parse_table_output(output: str) -> list[dict[str, str]]:
    """Parse tab-separated PKScreener output into list of dicts."""
    lines = [line.strip() for line in output.strip().split("\n") if line.strip()]
    if len(lines) < 2:
        return []

    headers = [h.strip() for h in lines[0].split("\t")]
    results: list[dict[str, str]] = []
    for line in lines[1:]:
        values = [v.strip() for v in line.split("\t")]
        if len(values) >= len(headers):
            results.append(dict(zip(headers, values[: len(headers)])))
        elif values:
            # Pad with empty strings if fewer values
            padded = values + [""] * (len(headers) - len(values))
            results.append(dict(zip(headers, padded)))

    return results


def _parse_levels_output(output: str) -> dict[str, Any]:
    """Parse buy/sell levels output into a dict."""
    result: dict[str, Any] = {}
    for line in output.strip().split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()
            # Try to convert numeric values
            try:
                result[key] = float(value)
            except ValueError:
                result[key] = value
    return result


def register(mcp: FastMCP) -> None:
    """Register PKScreener tools."""

    @mcp.tool()
    async def screen_stocks(
        scan_type: str,
        market: str = PKSCREENER_DEFAULT_MARKET,
    ) -> str:
        """Screen stocks using PKScreener Docker sidecar.

        Args:
            scan_type: Type of scan. One of: breakout, momentum, consolidation,
                       volume, reversal, ipo, short_squeeze, bullish, bearish.
            market: Market to scan (default NASDAQ). Supported: NASDAQ, NSE.

        Returns:
            JSON with screening results.
        """
        try:
            # Validate scan_type against allowed list
            if not _SAFE_PATTERN.match(scan_type):
                return json.dumps(
                    {"error": f"Invalid scan type format: '{scan_type}'"},
                    default=str,
                )

            scan_type_lower = scan_type.lower()
            if scan_type_lower not in SCAN_TYPES:
                return json.dumps(
                    {
                        "error": f"Unknown scan type '{scan_type}'. "
                        f"Available: {list(SCAN_TYPES.keys())}"
                    },
                    default=str,
                )

            # Resolve market to PKScreener index number
            try:
                index = _resolve_market_index(market)
            except ValueError as e:
                return json.dumps({"error": str(e)}, default=str)

            config = SCAN_TYPES[scan_type_lower]
            suffix = config["suffix"]
            args = ["-o", f"X:{index}:{suffix}"]

            output = await run_pkscreener(args, timeout=PKSCREENER_SCAN_TIMEOUT)
            results = _parse_table_output(output)

            return json.dumps(
                {
                    "scan_type": scan_type_lower,
                    "market": market.upper(),
                    "total_results": len(results),
                    "results": results,
                },
                default=str,
            )

        except Exception as e:
            logger.warning("screen_stocks_error", scan_type=scan_type, error=str(e))
            return json.dumps({"error": str(e)}, default=str)

    @mcp.tool()
    async def get_screening_strategies() -> str:
        """Return available stock screening strategies.

        Returns:
            JSON with list of available strategies and their descriptions.
            No Docker call needed -- returns hardcoded strategy list.
        """
        strategies = [
            {"name": v["name"], "description": v["description"]}
            for v in SCAN_TYPES.values()
        ]
        return json.dumps({"strategies": strategies}, default=str)

    @mcp.tool()
    async def get_buy_sell_levels(
        ticker: str,
        market: str = PKSCREENER_DEFAULT_MARKET,
    ) -> str:
        """Get buy/sell support/resistance levels for a single ticker.

        Args:
            ticker: Stock ticker symbol.
            market: Market the ticker belongs to (default NASDAQ). Supported: NASDAQ, NSE.

        Returns:
            JSON with buy level, sell level, support, resistance.
        """
        try:
            # Validate ticker (alphanumeric, dots, hyphens; max 10 chars)
            if not re.match(r"^[A-Za-z0-9.\-]{1,10}$", ticker):
                return json.dumps(
                    {"error": f"Invalid ticker format: '{ticker}'"},
                    default=str,
                )

            # Resolve market to PKScreener index number
            try:
                index = _resolve_market_index(market)
            except ValueError as e:
                return json.dumps({"error": str(e)}, default=str)

            output = await run_pkscreener(
                ["--stocklist", ticker.upper(), "-o", f"X:{index}:0"],
                timeout=PKSCREENER_TICKER_TIMEOUT,
            )
            levels = _parse_levels_output(output)

            return json.dumps(
                {"ticker": ticker.upper(), **levels},
                default=str,
            )

        except Exception as e:
            logger.warning(
                "buy_sell_levels_error", ticker=ticker, error=str(e)
            )
            return json.dumps({"error": str(e)}, default=str)
