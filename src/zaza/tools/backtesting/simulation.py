"""Strategy simulation tool -- full round-trip entry/exit simulation.

Computes total trades, win rate, avg P&L, max drawdown, Sharpe, vs buy-and-hold.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
import structlog
from mcp.server.fastmcp import FastMCP

from zaza.api.yfinance_client import YFinanceClient
from zaza.cache.store import FileCache
from zaza.tools.backtesting.signals import SUPPORTED_SIGNALS, _detect_signals
from zaza.utils.indicators import ohlcv_to_dataframe

logger = structlog.get_logger(__name__)


def _simulate_trades(
    df: pd.DataFrame,
    entry_indices: list[int],
    exit_indices: set[int],
    stop_loss_pct: float = 5.0,
    take_profit_pct: float | None = None,
) -> list[dict[str, Any]]:
    """Simulate round-trip trades with stop loss and optional take profit.

    No look-ahead bias: entries trigger, then we scan forward for exit.
    """
    trades: list[dict[str, Any]] = []
    in_trade = False
    entry_price = 0.0
    entry_idx = 0

    for i in range(len(df)):
        if not in_trade and i in entry_indices:
            entry_price = float(df["Close"].iloc[i])
            entry_idx = i
            in_trade = True
            continue

        if in_trade:
            current_price = float(df["Close"].iloc[i])
            pnl_pct = (current_price - entry_price) / entry_price * 100

            # Check stop loss
            if pnl_pct <= -stop_loss_pct:
                trades.append({
                    "entry_idx": entry_idx,
                    "exit_idx": i,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(current_price, 2),
                    "pnl_pct": round(pnl_pct, 4),
                    "exit_reason": "stop_loss",
                    "days_held": i - entry_idx,
                })
                in_trade = False
                continue

            # Check take profit
            if take_profit_pct is not None and pnl_pct >= take_profit_pct:
                trades.append({
                    "entry_idx": entry_idx,
                    "exit_idx": i,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(current_price, 2),
                    "pnl_pct": round(pnl_pct, 4),
                    "exit_reason": "take_profit",
                    "days_held": i - entry_idx,
                })
                in_trade = False
                continue

            # Check exit signal
            if i in exit_indices:
                trades.append({
                    "entry_idx": entry_idx,
                    "exit_idx": i,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(current_price, 2),
                    "pnl_pct": round(pnl_pct, 4),
                    "exit_reason": "signal",
                    "days_held": i - entry_idx,
                })
                in_trade = False

    return trades


def _compute_simulation_stats(
    trades: list[dict[str, Any]], df: pd.DataFrame
) -> dict[str, Any]:
    """Compute aggregate statistics from a list of trades."""
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": None,
            "avg_pnl_pct": None,
            "max_drawdown_pct": None,
            "sharpe_ratio": None,
            "vs_buy_and_hold": None,
        }

    pnls = [t["pnl_pct"] for t in trades]
    wins = sum(1 for p in pnls if p > 0)

    # Compute max drawdown from trade equity curve
    equity = [100.0]
    for p in pnls:
        equity.append(equity[-1] * (1 + p / 100))
    equity_arr = np.array(equity)
    peak = np.maximum.accumulate(equity_arr)
    drawdowns = (peak - equity_arr) / peak * 100
    max_dd = float(np.max(drawdowns))

    # Sharpe (annualized, assuming ~252 trading days, avg 10 day hold)
    pnl_arr = np.array(pnls)
    if len(pnl_arr) > 1 and np.std(pnl_arr) > 0:
        avg_days_held = np.mean([t["days_held"] for t in trades])
        trades_per_year = 252 / max(avg_days_held, 1)
        sharpe = (float(np.mean(pnl_arr)) / float(np.std(pnl_arr))) * np.sqrt(
            trades_per_year
        )
        sharpe = round(float(sharpe), 4)
    else:
        sharpe = None

    # Buy and hold comparison
    first_price = float(df["Close"].iloc[0])
    last_price = float(df["Close"].iloc[-1])
    buy_hold_return = (last_price - first_price) / first_price * 100

    strategy_return = equity[-1] - 100.0

    return {
        "total_trades": len(trades),
        "win_rate": round(wins / len(trades), 4),
        "avg_pnl_pct": round(float(np.mean(pnls)), 4),
        "max_drawdown_pct": round(max_dd, 4),
        "sharpe_ratio": sharpe,
        "strategy_return_pct": round(strategy_return, 4),
        "buy_hold_return_pct": round(buy_hold_return, 4),
        "vs_buy_and_hold": round(strategy_return - buy_hold_return, 4),
    }


def register(mcp: FastMCP) -> None:
    """Register the strategy simulation tool."""
    cache = FileCache()
    yf = YFinanceClient(cache)

    @mcp.tool()
    async def get_strategy_simulation(
        ticker: str,
        entry_signal: str,
        exit_signal: str,
        stop_loss_pct: float = 5.0,
        take_profit_pct: float | None = None,
    ) -> str:
        """Simulate a full entry/exit trading strategy on historical data.

        Args:
            ticker: Stock ticker symbol.
            entry_signal: Signal for entering trades. One of: rsi_below_30,
                          rsi_above_70, macd_crossover, golden_cross,
                          death_cross, bollinger_lower_touch, volume_spike.
            exit_signal: Signal for exiting trades (same options as entry).
            stop_loss_pct: Stop loss percentage (default 5).
            take_profit_pct: Optional take profit percentage.

        Returns:
            JSON with total trades, win rate, avg P&L, max drawdown,
            Sharpe ratio, and comparison vs buy-and-hold.
        """
        try:
            for sig_name, sig_val in [
                ("entry_signal", entry_signal),
                ("exit_signal", exit_signal),
            ]:
                if sig_val not in SUPPORTED_SIGNALS:
                    return json.dumps(
                        {
                            "error": f"Unsupported {sig_name} '{sig_val}'. "
                            f"Supported: {SUPPORTED_SIGNALS}"
                        },
                        default=str,
                    )

            cache_key = cache.make_key(
                "strategy_sim",
                ticker=ticker,
                entry=entry_signal,
                exit=exit_signal,
                sl=stop_loss_pct,
                tp=take_profit_pct,
            )
            cached = cache.get(cache_key, "backtest_results")
            if cached is not None:
                return json.dumps(cached, default=str)

            history = yf.get_history(ticker, period="5y")
            if not history:
                return json.dumps(
                    {"error": f"No historical data for {ticker}"},
                    default=str,
                )

            df = ohlcv_to_dataframe(history)

            entry_indices_list = _detect_signals(df, entry_signal)
            exit_indices_list = _detect_signals(df, exit_signal)

            exit_set = set(exit_indices_list)

            trades = _simulate_trades(
                df,
                entry_indices_list,
                exit_set,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
            )

            stats = _compute_simulation_stats(trades, df)

            result = {
                "ticker": ticker,
                "entry_signal": entry_signal,
                "exit_signal": exit_signal,
                "stop_loss_pct": stop_loss_pct,
                "take_profit_pct": take_profit_pct,
                **stats,
            }

            cache.set(cache_key, "backtest_results", result)
            return json.dumps(result, default=str)

        except Exception as e:
            logger.warning("strategy_simulation_error", ticker=ticker, error=str(e))
            return json.dumps({"error": str(e)}, default=str)
