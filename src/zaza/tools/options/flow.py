"""Options flow analysis tools: unusual activity and put/call ratios."""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)

# Volume/OI threshold for unusual activity
UNUSUAL_VOL_OI_RATIO = 3.0
# Minimum volume to consider
MIN_VOLUME = 50


def _find_unusual_activity(
    contracts: list[dict[str, Any]], option_type: str
) -> list[dict[str, Any]]:
    """Identify contracts with unusual volume relative to open interest."""
    unusual = []
    for c in contracts:
        volume = c.get("volume", 0) or 0
        oi = c.get("openInterest", 0) or 0
        if volume < MIN_VOLUME:
            continue
        vol_oi_ratio = volume / oi if oi > 0 else float("inf")
        if vol_oi_ratio >= UNUSUAL_VOL_OI_RATIO:
            strike = c.get("strike", 0)
            last_price = c.get("lastPrice", 0)
            notional = volume * last_price * 100  # each contract = 100 shares
            unusual.append({
                "type": option_type,
                "strike": strike,
                "volume": volume,
                "openInterest": oi,
                "vol_oi_ratio": round(vol_oi_ratio, 2),
                "lastPrice": last_price,
                "impliedVolatility": c.get("impliedVolatility", 0),
                "notional": round(notional, 2),
                "contractSymbol": c.get("contractSymbol", ""),
            })
    return unusual


def register(mcp: FastMCP, yf: YFinanceClient, cache: FileCache) -> None:
    """Register options flow tools on the MCP server."""

    @mcp.tool()
    async def get_options_flow(ticker: str) -> str:
        """Detect unusual options activity for a ticker.

        Identifies contracts where volume significantly exceeds open interest,
        indicating potential institutional positioning or sweep activity.
        Returns sorted by notional value descending.
        """
        try:
            ticker_upper = ticker.upper()
            expirations = yf.get_options_expirations(ticker_upper)
            if not expirations:
                return json.dumps({
                    "ticker": ticker_upper,
                    "unusual_activity": [],
                    "total_unusual": 0,
                    "message": "No options data available",
                })

            # Check nearest 2-3 expirations for unusual activity
            all_unusual: list[dict[str, Any]] = []
            for exp in expirations[:3]:
                chain = yf.get_options_chain(ticker_upper, exp)
                calls = chain.get("calls", [])
                puts = chain.get("puts", [])

                call_unusual = _find_unusual_activity(calls, "call")
                put_unusual = _find_unusual_activity(puts, "put")

                for u in call_unusual + put_unusual:
                    u["expiration"] = exp

                all_unusual.extend(call_unusual)
                all_unusual.extend(put_unusual)

            # Sort by notional value descending
            all_unusual.sort(key=lambda x: x.get("notional", 0), reverse=True)

            result: dict[str, Any] = {
                "ticker": ticker_upper,
                "unusual_activity": all_unusual[:20],  # top 20
                "total_unusual": len(all_unusual),
                "expirations_scanned": expirations[:3],
            }
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("get_options_flow_error", ticker=ticker, error=str(e))
            return json.dumps({"error": f"Failed to get options flow for {ticker}: {e}"})

    @mcp.tool()
    async def get_put_call_ratio(ticker: str) -> str:
        """Get put/call ratio by volume and open interest for a ticker.

        A high P/C ratio (>1.0) suggests bearish sentiment.
        A low P/C ratio (<0.7) suggests bullish sentiment.
        """
        try:
            ticker_upper = ticker.upper()
            expirations = yf.get_options_expirations(ticker_upper)
            if not expirations:
                return json.dumps({"error": f"No options data for {ticker}"})

            total_call_vol = 0
            total_put_vol = 0
            total_call_oi = 0
            total_put_oi = 0

            # Aggregate across nearest expirations
            for exp in expirations[:3]:
                chain = yf.get_options_chain(ticker_upper, exp)
                for c in chain.get("calls", []):
                    total_call_vol += c.get("volume", 0) or 0
                    total_call_oi += c.get("openInterest", 0) or 0
                for p in chain.get("puts", []):
                    total_put_vol += p.get("volume", 0) or 0
                    total_put_oi += p.get("openInterest", 0) or 0

            pc_volume = total_put_vol / total_call_vol if total_call_vol > 0 else 0.0
            pc_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0.0

            # Interpretation
            if pc_volume > 1.2:
                interpretation = "bearish"
            elif pc_volume > 0.9:
                interpretation = "neutral"
            elif pc_volume > 0.5:
                interpretation = "moderately_bullish"
            else:
                interpretation = "bullish"

            result: dict[str, Any] = {
                "ticker": ticker_upper,
                "pc_volume_ratio": round(pc_volume, 4),
                "pc_oi_ratio": round(pc_oi, 4),
                "total_call_volume": total_call_vol,
                "total_put_volume": total_put_vol,
                "total_call_oi": total_call_oi,
                "total_put_oi": total_put_oi,
                "interpretation": interpretation,
                "expirations_included": expirations[:3],
            }
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("get_put_call_ratio_error", ticker=ticker, error=str(e))
            return json.dumps({"error": f"Failed to get put/call ratio for {ticker}: {e}"})
