"""Implied volatility analysis tools."""

from __future__ import annotations

import json
import statistics
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def _compute_historical_vol(history: list[dict[str, Any]], window: int = 252) -> float:
    """Compute annualized historical volatility from daily close prices."""
    closes = [h.get("Close", 0) for h in history if h.get("Close")]
    if len(closes) < 20:
        return 0.0
    returns = [(closes[i] / closes[i - 1]) - 1 for i in range(1, len(closes))]
    if not returns:
        return 0.0
    std = statistics.stdev(returns) if len(returns) > 1 else 0.0
    return std * (252 ** 0.5)  # annualize


def register(mcp: FastMCP, yf: YFinanceClient, cache: FileCache) -> None:
    """Register implied volatility tools on the MCP server."""

    @mcp.tool()
    async def get_implied_volatility(ticker: str) -> str:
        """Get implied volatility analysis: ATM IV, IV rank (approx), and IV skew.

        ATM IV is the implied volatility of the nearest at-the-money options.
        IV rank approximates where current IV sits relative to historical volatility.
        IV skew measures the difference between OTM put IV and OTM call IV.
        """
        try:
            ticker_upper = ticker.upper()

            # Check cache first
            cache_key = cache.make_key("implied_vol", ticker=ticker_upper)
            cached = cache.get(cache_key, "implied_vol")
            if cached is not None:
                return json.dumps(cached, default=str)

            # Get nearest expiration
            expirations = yf.get_options_expirations(ticker_upper)
            if not expirations:
                return json.dumps({"error": f"No options expirations found for {ticker}"})

            nearest_exp = expirations[0]
            chain = yf.get_options_chain(ticker_upper, nearest_exp)
            calls = chain.get("calls", [])
            puts = chain.get("puts", [])

            if not calls and not puts:
                return json.dumps({"error": f"No options data found for {ticker}"})

            # Get current price for ATM determination
            quote = yf.get_quote(ticker_upper)
            current_price = quote.get("regularMarketPrice", 0)
            if not current_price:
                return json.dumps({"error": f"Could not get current price for {ticker}"})

            # Find ATM strike (closest to current price)
            all_strikes = sorted(set(c.get("strike", 0) for c in calls))
            if not all_strikes:
                return json.dumps({"error": f"No strike data found for {ticker}"})

            atm_strike = min(all_strikes, key=lambda s: abs(s - current_price))

            # ATM IV: average of ATM call and put IV
            atm_call_iv = next(
                (c.get("impliedVolatility", 0) for c in calls if c.get("strike") == atm_strike),
                0,
            )
            atm_put_iv = next(
                (p.get("impliedVolatility", 0) for p in puts if p.get("strike") == atm_strike),
                0,
            )
            if atm_call_iv and atm_put_iv:
                atm_iv = (atm_call_iv + atm_put_iv) / 2
            else:
                atm_iv = atm_call_iv or atm_put_iv

            # Historical vol for IV rank approximation
            history = yf.get_history(ticker_upper, period="1y")
            hv = _compute_historical_vol(history)
            # IV rank: simplified as ATM IV percentile vs HV
            # A rough approximation: (current IV - HV_low) / (HV_high - HV_low)
            # Since we only have one HV value, use ratio approach
            iv_rank = min(max((atm_iv / hv) * 50, 0), 100) if hv > 0 else 50.0

            # IV skew: OTM put IV - OTM call IV
            otm_puts = [p for p in puts if p.get("strike", 0) < current_price]
            otm_calls = [c for c in calls if c.get("strike", 0) > current_price]

            otm_put_iv_avg = (
                statistics.mean(p.get("impliedVolatility", 0) for p in otm_puts)
                if otm_puts
                else 0
            )
            otm_call_iv_avg = (
                statistics.mean(c.get("impliedVolatility", 0) for c in otm_calls)
                if otm_calls
                else 0
            )
            iv_skew = otm_put_iv_avg - otm_call_iv_avg

            result: dict[str, Any] = {
                "ticker": ticker_upper,
                "expiration": nearest_exp,
                "current_price": current_price,
                "atm_strike": atm_strike,
                "atm_iv": round(atm_iv, 4),
                "historical_vol": round(hv, 4),
                "iv_rank": round(iv_rank, 2),
                "iv_skew": round(iv_skew, 4),
                "otm_put_iv_avg": round(otm_put_iv_avg, 4),
                "otm_call_iv_avg": round(otm_call_iv_avg, 4),
            }
            cache.set(cache_key, "implied_vol", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("get_implied_volatility_error", ticker=ticker, error=str(e))
            return json.dumps({"error": f"Failed to get IV for {ticker}: {e}"})
