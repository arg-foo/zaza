"""Fund flows proxy tool."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)

# Sector ETF mapping for flow proxy analysis
SECTOR_ETF_MAP: dict[str, str] = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
    "Communication Services": "XLC",
}


def _analyze_flow(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze volume and price trends as a proxy for fund flows."""
    if not history or len(history) < 2:
        return {"flow_signal": "insufficient_data", "trend": "unknown"}

    closes = [r.get("Close", 0) for r in history if r.get("Close")]
    volumes = [r.get("Volume", 0) for r in history if r.get("Volume")]

    if not closes or not volumes:
        return {"flow_signal": "insufficient_data", "trend": "unknown"}

    # Price trend
    price_change = (closes[-1] - closes[0]) / closes[0] * 100 if closes[0] > 0 else 0

    # Volume trend (compare recent vs earlier)
    mid = len(volumes) // 2
    recent_avg_vol = np.mean(volumes[mid:]) if mid > 0 else np.mean(volumes)
    early_avg_vol = np.mean(volumes[:mid]) if mid > 0 else np.mean(volumes)
    vol_change = (
        (recent_avg_vol - early_avg_vol) / early_avg_vol * 100
        if early_avg_vol > 0
        else 0
    )

    # Determine flow signal
    if price_change > 2 and vol_change > 10:
        flow_signal = "strong_inflow"
    elif price_change > 0 and vol_change > 0:
        flow_signal = "mild_inflow"
    elif price_change < -2 and vol_change > 10:
        flow_signal = "strong_outflow"
    elif price_change < 0 and vol_change > 0:
        flow_signal = "mild_outflow"
    else:
        flow_signal = "neutral"

    trend = "up" if price_change > 0 else "down" if price_change < 0 else "flat"

    return {
        "flow_signal": flow_signal,
        "trend": trend,
        "price_change_pct": round(float(price_change), 2),
        "volume_change_pct": round(float(vol_change), 2),
        "recent_avg_volume": int(recent_avg_vol),
    }


def register(mcp: FastMCP) -> None:
    """Register fund flows tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_fund_flows(ticker: str) -> str:
        """Get fund flow proxy data via sector ETF volume and price trends.

        Since direct fund flow data requires paid sources, this tool approximates
        flows using the ticker's sector ETF volume and price trends.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
        """
        cache_key = cache.make_key("fund_flows", ticker=ticker)
        cached = cache.get(cache_key, "fund_flows")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            # Get the ticker's sector
            quote = yf.get_quote(ticker)
            sector = quote.get("sector", "")
            sector_etf = SECTOR_ETF_MAP.get(sector, "SPY")  # Default to SPY

            # Get sector ETF history
            etf_history = yf.get_history(sector_etf, period="1mo")
            etf_flow = _analyze_flow(etf_history)

            # Get ticker's own volume trends
            ticker_history = yf.get_history(ticker, period="1mo")
            ticker_flow = _analyze_flow(ticker_history)

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "sector": sector or "Unknown",
                    "sector_etf": sector_etf,
                    "sector_flow": etf_flow,
                    "ticker_flow": ticker_flow,
                    "flow_signal": ticker_flow.get("flow_signal", "unknown"),
                },
            }
            cache.set(cache_key, "fund_flows", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("fund_flows_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
