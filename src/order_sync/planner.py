"""Order intent computation — pure functions, no MCP dependency.

Given trade plans, positions, and open orders, determines what order
actions are needed (BRACKET, OCA, or SKIP).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from order_sync.parsers import TradePlan


@dataclass
class OrderIntent:
    """Represents a computed order action for a trade plan.

    action:
        BRACKET — place a bracket order (entry + TP + SL)
        OCA — place an OCA order (TP + SL for existing position)
        SKIP — no action needed (existing orders cover it, or error)
    """

    plan_id: str
    ticker: str
    action: Literal["BRACKET", "OCA", "SKIP"]
    reason: str
    entry_limit_price: float | None  # only for BRACKET
    quantity: int
    tp_limit_price: float
    sl_stop_price: float
    sl_limit_price: float


def compute_order_intents(
    plans: list[TradePlan],
    positions: list[dict],
    open_orders: list[dict],
) -> list[OrderIntent]:
    """For each active trade plan, determine what order action is needed.

    Classification logic per plan:
    - NEEDS_BRACKET: entry PENDING, no position, no existing BUY order for ticker
    - NEEDS_OCA: entry COMPLETED (or position held), no existing SELL orders for ticker
    - SKIP: matching orders already exist, or error conditions

    Args:
        plans: Parsed TradePlan objects from active trade plans.
        positions: Tiger position dicts (symbol, quantity, ...).
        open_orders: Tiger open order dicts (symbol, action, ...).

    Returns:
        List of OrderIntent, one per plan.
    """
    intents: list[OrderIntent] = []

    for plan in plans:
        ticker_buy_orders = [
            o for o in open_orders
            if o["symbol"] == plan.ticker and o["action"] == "BUY"
        ]
        ticker_sell_orders = [
            o for o in open_orders
            if o["symbol"] == plan.ticker and o["action"] == "SELL"
        ]
        held_qty = sum(
            p.get("quantity", 0)
            for p in positions
            if p.get("symbol") == plan.ticker
        )

        if plan.entry_status == "PENDING":
            if ticker_buy_orders:
                intents.append(OrderIntent(
                    plan_id=plan.plan_id,
                    ticker=plan.ticker,
                    action="SKIP",
                    reason="Existing BUY order found",
                    entry_limit_price=None,
                    quantity=plan.quantity,
                    tp_limit_price=plan.tp_limit_price,
                    sl_stop_price=plan.sl_stop_price,
                    sl_limit_price=plan.sl_limit_price,
                ))
            else:
                intents.append(OrderIntent(
                    plan_id=plan.plan_id,
                    ticker=plan.ticker,
                    action="BRACKET",
                    reason="Entry pending, no existing BUY order",
                    entry_limit_price=plan.entry_limit_price,
                    quantity=plan.quantity,
                    tp_limit_price=plan.tp_limit_price,
                    sl_stop_price=plan.sl_stop_price,
                    sl_limit_price=plan.sl_limit_price,
                ))
        elif plan.entry_status == "COMPLETED":
            if held_qty <= 0:
                intents.append(OrderIntent(
                    plan_id=plan.plan_id,
                    ticker=plan.ticker,
                    action="SKIP",
                    reason=f"Entry COMPLETED but no position held for {plan.ticker}",
                    entry_limit_price=None,
                    quantity=plan.quantity,
                    tp_limit_price=plan.tp_limit_price,
                    sl_stop_price=plan.sl_stop_price,
                    sl_limit_price=plan.sl_limit_price,
                ))
            elif ticker_sell_orders:
                intents.append(OrderIntent(
                    plan_id=plan.plan_id,
                    ticker=plan.ticker,
                    action="SKIP",
                    reason="Existing SELL orders found",
                    entry_limit_price=None,
                    quantity=plan.quantity,
                    tp_limit_price=plan.tp_limit_price,
                    sl_stop_price=plan.sl_stop_price,
                    sl_limit_price=plan.sl_limit_price,
                ))
            else:
                oca_qty = min(plan.quantity, held_qty)
                intents.append(OrderIntent(
                    plan_id=plan.plan_id,
                    ticker=plan.ticker,
                    action="OCA",
                    reason="Position held, no existing SELL orders",
                    entry_limit_price=None,
                    quantity=oca_qty,
                    tp_limit_price=plan.tp_limit_price,
                    sl_stop_price=plan.sl_stop_price,
                    sl_limit_price=plan.sl_limit_price,
                ))
        else:
            intents.append(OrderIntent(
                plan_id=plan.plan_id,
                ticker=plan.ticker,
                action="SKIP",
                reason=f"Unknown entry status: {plan.entry_status}",
                entry_limit_price=None,
                quantity=plan.quantity,
                tp_limit_price=plan.tp_limit_price,
                sl_stop_price=plan.sl_stop_price,
                sl_limit_price=plan.sl_limit_price,
            ))

    return intents
