"""Monte Carlo simulation tool."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.models import monte_carlo_gbm

logger = structlog.get_logger(__name__)

MIN_DATA_POINTS = 30


def register(mcp: FastMCP) -> None:
    """Register Monte Carlo simulation tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_monte_carlo_simulation(
        ticker: str, horizon_days: int = 30, simulations: int = 10000
    ) -> str:
        """Run Monte Carlo (GBM) price simulation.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
            horizon_days: Number of days to simulate (default 30).
            simulations: Number of simulation paths (default 10000).
        """
        cache_key = cache.make_key(
            "monte_carlo",
            ticker=ticker,
            horizon=horizon_days,
            sims=simulations,
        )
        cached = cache.get(cache_key, "quant_models")
        if cached is not None:
            return json.dumps(cached, default=str)

        try:
            history = yf.get_history(ticker, period="1y")
            if not history or len(history) < MIN_DATA_POINTS:
                return json.dumps(
                    {
                        "status": "error",
                        "error": (
                            f"Insufficient data for Monte Carlo"
                            f" (need >= {MIN_DATA_POINTS},"
                            f" got {len(history) if history else 0})"
                        ),
                    }
                )

            closes = np.array(
                [r["Close"] for r in history if r.get("Close") is not None],
                dtype=float,
            )
            if len(closes) < MIN_DATA_POINTS:
                return json.dumps(
                    {"status": "error", "error": "Insufficient valid price data"}
                )

            returns = np.diff(np.log(closes))
            mu = float(np.mean(returns)) * 252  # Annualized drift
            sigma = float(np.std(returns)) * np.sqrt(252)  # Annualized vol
            current_price = float(closes[-1])

            # Use a deterministic seed based on ticker hash for reproducibility
            seed = hash(ticker) % (2**31)
            mc_result = monte_carlo_gbm(
                price=current_price,
                mu=mu,
                sigma=sigma,
                days=horizon_days,
                n_sims=simulations,
                seed=seed,
            )

            result: dict[str, Any] = {
                "status": "ok",
                "data": {
                    "ticker": ticker,
                    "current_price": round(current_price, 2),
                    "horizon_days": horizon_days,
                    "simulations": simulations,
                    "annualized_drift": round(mu, 4),
                    "annualized_vol": round(sigma, 4),
                    **mc_result,
                },
            }
            cache.set(cache_key, "quant_models", result)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("monte_carlo_error", ticker=ticker, error=str(e))
            return json.dumps({"status": "error", "error": str(e)})
