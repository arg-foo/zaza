"""Options levels tools: max pain and gamma exposure."""

from __future__ import annotations

import json
import math
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


def _calculate_max_pain(
    calls: list[dict[str, Any]], puts: list[dict[str, Any]]
) -> float:
    """Calculate the max pain strike price.

    Max pain is the strike price where total pain (intrinsic value owed)
    to option holders is minimized, i.e., where market makers pay the least.
    """
    strikes = sorted(set(c["strike"] for c in calls) | set(p["strike"] for p in puts))
    if not strikes:
        return 0.0

    min_pain = float("inf")
    max_pain_strike = 0.0

    for strike in strikes:
        call_pain = sum(
            max(0, strike - c["strike"]) * c.get("openInterest", 0) for c in calls
        )
        put_pain = sum(
            max(0, p["strike"] - strike) * p.get("openInterest", 0) for p in puts
        )
        total_pain = call_pain + put_pain
        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = strike

    return max_pain_strike


def _estimate_gamma(
    strike: float,
    spot: float,
    iv: float,
    oi: float,
    is_call: bool,
) -> float:
    """Estimate option gamma using a simplified Black-Scholes approach.

    Gamma = (N'(d1)) / (S * sigma * sqrt(T))
    For simplicity, assumes T=30/365 days to expiry.
    """
    if iv <= 0 or spot <= 0 or oi <= 0:
        return 0.0

    T = 30 / 365  # approximate days to expiry
    sigma = iv
    sqrt_T = math.sqrt(T)

    try:
        d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * T) / (sigma * sqrt_T)
        # N'(d1) = standard normal PDF
        n_prime_d1 = math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)
        gamma = n_prime_d1 / (spot * sigma * sqrt_T)
    except (ValueError, ZeroDivisionError):
        return 0.0

    # GEX = gamma * OI * 100 (contract multiplier) * spot
    # Calls add positive gamma, puts add negative gamma (for dealer hedging)
    gex = gamma * oi * 100 * spot
    return gex if is_call else -gex


def _get_oi_distribution(
    calls: list[dict[str, Any]],
    puts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build OI distribution by strike."""
    strike_map: dict[float, dict[str, int]] = {}
    for c in calls:
        s = c.get("strike", 0)
        if s not in strike_map:
            strike_map[s] = {"call_oi": 0, "put_oi": 0}
        strike_map[s]["call_oi"] += c.get("openInterest", 0) or 0
    for p in puts:
        s = p.get("strike", 0)
        if s not in strike_map:
            strike_map[s] = {"call_oi": 0, "put_oi": 0}
        strike_map[s]["put_oi"] += p.get("openInterest", 0) or 0
    dist = []
    for strike in sorted(strike_map):
        dist.append({
            "strike": strike,
            "call_oi": strike_map[strike]["call_oi"],
            "put_oi": strike_map[strike]["put_oi"],
            "total_oi": strike_map[strike]["call_oi"] + strike_map[strike]["put_oi"],
        })
    return dist


def register(mcp: FastMCP, yf: YFinanceClient, cache: FileCache) -> None:
    """Register options levels tools on the MCP server."""

    @mcp.tool()
    async def get_max_pain(ticker: str, expiration_date: str | None = None) -> str:
        """Calculate max pain strike price for a ticker.

        Max pain is the price at which option writers would lose the least money.
        Stock prices tend to gravitate toward max pain at expiration.

        If no expiration_date is provided, uses the nearest available expiration.
        """
        try:
            ticker_upper = ticker.upper()

            # Resolve expiration date
            if not expiration_date:
                expirations = yf.get_options_expirations(ticker_upper)
                if not expirations:
                    return json.dumps({"error": f"No options expirations found for {ticker}"})
                expiration_date = expirations[0]

            chain = yf.get_options_chain(ticker_upper, expiration_date)
            calls = chain.get("calls", [])
            puts = chain.get("puts", [])

            if not calls and not puts:
                return json.dumps({"error": f"No options data for {ticker} at {expiration_date}"})

            max_pain_strike = _calculate_max_pain(calls, puts)

            # Get current price
            quote = yf.get_quote(ticker_upper)
            current_price = quote.get("regularMarketPrice", 0)
            distance_pct = (
                round((max_pain_strike - current_price) / current_price * 100, 2)
                if current_price
                else 0.0
            )

            # OI distribution
            oi_dist = _get_oi_distribution(calls, puts)

            result: dict[str, Any] = {
                "ticker": ticker_upper,
                "expiration_date": expiration_date,
                "max_pain_strike": max_pain_strike,
                "current_price": current_price,
                "distance_pct": distance_pct,
                "oi_distribution": oi_dist,
            }
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("get_max_pain_error", ticker=ticker, error=str(e))
            return json.dumps({"error": f"Failed to calculate max pain for {ticker}: {e}"})

    @mcp.tool()
    async def get_gamma_exposure(ticker: str, expiration_date: str | None = None) -> str:
        """Calculate net gamma exposure (GEX) by strike for a ticker.

        GEX measures the expected hedging activity by dealers. Positive GEX
        at a strike means dealers will buy dips and sell rallies (stabilizing).
        Negative GEX means dealers amplify moves.

        The GEX flip point is where net gamma changes sign.

        If no expiration_date is provided, uses the nearest available expiration.
        """
        try:
            ticker_upper = ticker.upper()

            # Resolve expiration date
            if not expiration_date:
                expirations = yf.get_options_expirations(ticker_upper)
                if not expirations:
                    return json.dumps({"error": f"No options expirations found for {ticker}"})
                expiration_date = expirations[0]

            chain = yf.get_options_chain(ticker_upper, expiration_date)
            calls = chain.get("calls", [])
            puts = chain.get("puts", [])

            if not calls and not puts:
                return json.dumps({"error": f"No options data for {ticker} at {expiration_date}"})

            # Get spot price
            quote = yf.get_quote(ticker_upper)
            spot = quote.get("regularMarketPrice", 0)
            if not spot:
                return json.dumps({"error": f"Could not get price for {ticker}"})

            # Calculate GEX per strike
            strike_gex: dict[float, float] = {}
            for c in calls:
                s = c.get("strike", 0)
                iv = c.get("impliedVolatility", 0.3)
                oi = c.get("openInterest", 0) or 0
                gex = _estimate_gamma(s, spot, iv, oi, is_call=True)
                strike_gex[s] = strike_gex.get(s, 0) + gex

            for p in puts:
                s = p.get("strike", 0)
                iv = p.get("impliedVolatility", 0.3)
                oi = p.get("openInterest", 0) or 0
                gex = _estimate_gamma(s, spot, iv, oi, is_call=False)
                strike_gex[s] = strike_gex.get(s, 0) + gex

            sorted_strikes = sorted(strike_gex.keys())
            gex_by_strike = [
                {"strike": s, "net_gex": round(strike_gex[s], 2)} for s in sorted_strikes
            ]

            # Net GEX across all strikes
            net_gex = round(sum(strike_gex.values()), 2)

            # Find GEX flip point (where sign changes)
            gex_flip: float | None = None
            for i in range(1, len(sorted_strikes)):
                prev_gex = strike_gex[sorted_strikes[i - 1]]
                curr_gex = strike_gex[sorted_strikes[i]]
                if prev_gex * curr_gex < 0:  # sign change
                    gex_flip = sorted_strikes[i]
                    break

            # Classify gamma zones
            positive_gamma_zone = [s for s in sorted_strikes if strike_gex[s] > 0]
            negative_gamma_zone = [s for s in sorted_strikes if strike_gex[s] < 0]

            result: dict[str, Any] = {
                "ticker": ticker_upper,
                "expiration_date": expiration_date,
                "current_price": spot,
                "gex_by_strike": gex_by_strike,
                "net_gex": net_gex,
                "gex_flip_point": gex_flip,
                "positive_gamma_strikes": positive_gamma_zone,
                "negative_gamma_strikes": negative_gamma_zone,
            }
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("get_gamma_exposure_error", ticker=ticker, error=str(e))
            return json.dumps({"error": f"Failed to calculate GEX for {ticker}: {e}"})
