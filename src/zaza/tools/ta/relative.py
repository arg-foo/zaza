"""Relative performance MCP tool — vs S&P 500, sector ETF, beta, correlation."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.indicators import ohlcv_to_dataframe

logger = structlog.get_logger(__name__)

SECTOR_ETFS: dict[str, str] = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Consumer Cyclical": "XLY",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
}


def register(mcp: FastMCP) -> None:
    """Register relative performance tool with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_relative_performance(
        ticker: str,
        period: str = "6mo",
    ) -> str:
        """Get relative performance analysis for a stock.

        Compares the stock's return against the S&P 500 (SPY) and its
        sector ETF. Computes beta and correlation.

        Args:
            ticker: Stock ticker symbol.
            period: Historical period (default '6mo').
        """
        try:
            # Fetch ticker history
            history = yf.get_history(ticker, period=period)
            if not history:
                return json.dumps(
                    {"error": f"No price history available for {ticker}"},
                    default=str,
                )

            # Fetch SPY history
            spy_history = yf.get_history("SPY", period=period)

            # Determine sector ETF
            quote = yf.get_quote(ticker)
            sector = quote.get("sector", "")
            sector_etf = SECTOR_ETFS.get(sector)
            sector_history = None
            if sector_etf:
                sector_history = yf.get_history(sector_etf, period=period)

            # Compute returns
            df_ticker = ohlcv_to_dataframe(history)
            ticker_returns = df_ticker["Close"].pct_change().dropna()
            ticker_total = float(
                (df_ticker["Close"].iloc[-1] / df_ticker["Close"].iloc[0] - 1) * 100
            )

            result: dict[str, Any] = {
                "status": "ok",
                "ticker": ticker.upper(),
                "period": period,
                "data": {
                    "ticker_return_pct": round(ticker_total, 2),
                },
            }

            # VS SPY
            if spy_history:
                df_spy = ohlcv_to_dataframe(spy_history)
                spy_returns = df_spy["Close"].pct_change().dropna()
                spy_total = float(
                    (df_spy["Close"].iloc[-1] / df_spy["Close"].iloc[0] - 1) * 100
                )

                # Align return series
                min_len = min(len(ticker_returns), len(spy_returns))
                tr = ticker_returns.values[-min_len:]
                sr = spy_returns.values[-min_len:]

                correlation = float(np.corrcoef(tr, sr)[0, 1])
                # Beta = Cov(ticker, spy) / Var(spy)
                cov = np.cov(tr, sr)
                beta = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] != 0 else None

                result["data"]["vs_spy"] = {
                    "ticker_return": round(ticker_total, 2),
                    "spy_return": round(spy_total, 2),
                    "outperformance": round(ticker_total - spy_total, 2),
                    "correlation": round(correlation, 4),
                    "beta": round(beta, 4) if beta is not None else None,
                }

            # VS Sector ETF
            if sector_history and sector_etf:
                df_sector = ohlcv_to_dataframe(sector_history)
                sector_total = float(
                    (df_sector["Close"].iloc[-1] / df_sector["Close"].iloc[0] - 1) * 100
                )
                sector_returns = df_sector["Close"].pct_change().dropna()
                min_len_s = min(len(ticker_returns), len(sector_returns))
                tr_s = ticker_returns.values[-min_len_s:]
                sr_s = sector_returns.values[-min_len_s:]
                sector_corr = float(np.corrcoef(tr_s, sr_s)[0, 1])

                result["data"]["vs_sector"] = {
                    "sector": sector,
                    "etf": sector_etf,
                    "sector_return": round(sector_total, 2),
                    "outperformance": round(ticker_total - sector_total, 2),
                    "correlation": round(sector_corr, 4),
                }

            return json.dumps(result, default=str)

        except Exception as e:
            logger.warning("get_relative_performance_error", ticker=ticker, error=str(e))
            return json.dumps({"error": str(e)}, default=str)
