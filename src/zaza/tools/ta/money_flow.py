"""Money flow MCP tool — CMF, MFI, Williams %R."""

from __future__ import annotations

import json

import numpy as np
import structlog
import ta
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.utils.indicators import compute_cmf, compute_mfi, ohlcv_to_dataframe

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Register money flow tool with the MCP server."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_money_flow(
        ticker: str,
        period: str = "6mo",
    ) -> str:
        """Get money flow analysis for a stock.

        Computes Chaikin Money Flow (CMF), Money Flow Index (MFI),
        and Williams %R.

        Args:
            ticker: Stock ticker symbol.
            period: Historical period (default '6mo').
        """
        try:
            history = yf.get_history(ticker, period=period)
            if not history:
                return json.dumps(
                    {"error": f"No price history available for {ticker}"},
                    default=str,
                )

            df = ohlcv_to_dataframe(history)
            cmf_value = compute_cmf(df)
            mfi_data = compute_mfi(df)

            # Williams %R
            williams_r = _compute_williams_r(df)

            # CMF signal
            if cmf_value is not None:
                if cmf_value > 0.05:
                    cmf_signal = "buying_pressure"
                elif cmf_value < -0.05:
                    cmf_signal = "selling_pressure"
                else:
                    cmf_signal = "neutral"
            else:
                cmf_signal = "insufficient_data"

            # Overall money flow assessment
            bullish = 0
            bearish = 0
            if cmf_value is not None and cmf_value > 0:
                bullish += 1
            elif cmf_value is not None and cmf_value < 0:
                bearish += 1

            mfi_sig = mfi_data.get("signal", "")
            if mfi_sig == "oversold":
                bullish += 1
            elif mfi_sig == "overbought":
                bearish += 1

            if williams_r.get("signal") == "oversold":
                bullish += 1
            elif williams_r.get("signal") == "overbought":
                bearish += 1

            if bullish > bearish:
                overall = "inflow"
            elif bearish > bullish:
                overall = "outflow"
            else:
                overall = "neutral"

            return json.dumps({
                "status": "ok",
                "ticker": ticker.upper(),
                "period": period,
                "data": {
                    "cmf": {
                        "value": cmf_value,
                        "signal": cmf_signal,
                    },
                    "mfi": mfi_data,
                    "williams_r": williams_r,
                    "overall_flow": overall,
                },
            }, default=str)

        except Exception as e:
            logger.warning("get_money_flow_error", ticker=ticker, error=str(e))
            return json.dumps({"error": str(e)}, default=str)


def _compute_williams_r(df: object, period: int = 14) -> dict:
    """Compute Williams %R indicator.

    Args:
        df: DataFrame with High, Low, Close columns.
        period: Lookback period (default 14).

    Returns:
        Dict with value and signal classification.
    """
    try:
        wr = ta.momentum.WilliamsRIndicator(
            df["High"], df["Low"], df["Close"], lbp=period  # type: ignore[index]
        )
        val = wr.williams_r().iloc[-1]
        if np.isnan(val):
            return {"value": None, "signal": "insufficient_data"}
        value = round(float(val), 2)
        if value > -20:
            signal = "overbought"
        elif value < -80:
            signal = "oversold"
        else:
            signal = "neutral"
        return {"value": value, "signal": signal}
    except Exception:
        return {"value": None, "signal": "insufficient_data"}
