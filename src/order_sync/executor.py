"""MCP client calls to place orders and extract results.

Handles bracket and OCA order placement via Tiger MCP,
with single-retry on failure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from order_sync.parsers import _extract_text
from order_sync.planner import OrderIntent


@dataclass
class OrderResult:
    """Result of an order placement attempt."""

    plan_id: str
    ticker: str
    action: str  # BRACKET or OCA
    success: bool
    order_id: str | None
    error: str | None


async def place_orders(
    tiger_session: object,
    intents: list[OrderIntent],
) -> list[OrderResult]:
    """Place orders for all non-SKIP intents.

    For each actionable intent, attempts placement once. On failure,
    retries once before recording the error.

    Args:
        tiger_session: MCP ClientSession connected to Tiger MCP.
        intents: List of OrderIntent objects to process.

    Returns:
        List of OrderResult for each non-SKIP intent.
    """
    results: list[OrderResult] = []

    for intent in intents:
        if intent.action == "SKIP":
            continue

        result = await _place_single_order(tiger_session, intent)
        if not result.success:
            # Retry once
            result = await _place_single_order(tiger_session, intent)
        results.append(result)

    return results


async def _place_single_order(
    tiger_session: object,
    intent: OrderIntent,
) -> OrderResult:
    """Place a single order via MCP.

    Args:
        tiger_session: MCP ClientSession connected to Tiger MCP.
        intent: The OrderIntent describing what to place.

    Returns:
        OrderResult indicating success/failure.
    """
    try:
        if intent.action == "BRACKET":
            resp = await tiger_session.call_tool(  # type: ignore[union-attr]
                "place_bracket_order",
                {
                    "symbol": intent.ticker,
                    "quantity": intent.quantity,
                    "entry_limit_price": intent.entry_limit_price,
                    "tp_limit_price": intent.tp_limit_price,
                    "sl_stop_price": intent.sl_stop_price,
                    "sl_limit_price": intent.sl_limit_price,
                },
            )
        elif intent.action == "OCA":
            resp = await tiger_session.call_tool(  # type: ignore[union-attr]
                "place_oca_order",
                {
                    "symbol": intent.ticker,
                    "quantity": intent.quantity,
                    "tp_limit_price": intent.tp_limit_price,
                    "sl_stop_price": intent.sl_stop_price,
                    "sl_limit_price": intent.sl_limit_price,
                },
            )
        else:
            return OrderResult(
                plan_id=intent.plan_id,
                ticker=intent.ticker,
                action=intent.action,
                success=False,
                order_id=None,
                error=f"Unknown action: {intent.action}",
            )

        text = _extract_text(resp)
        if "Error" in text or "BLOCKED" in text:
            return OrderResult(
                plan_id=intent.plan_id,
                ticker=intent.ticker,
                action=intent.action,
                success=False,
                order_id=None,
                error=text,
            )

        order_id = _extract_order_id(text)
        return OrderResult(
            plan_id=intent.plan_id,
            ticker=intent.ticker,
            action=intent.action,
            success=True,
            order_id=order_id,
            error=None,
        )
    except Exception as exc:
        return OrderResult(
            plan_id=intent.plan_id,
            ticker=intent.ticker,
            action=intent.action,
            success=False,
            order_id=None,
            error=str(exc),
        )


def _extract_order_id(text: str) -> str | None:
    """Extract Order ID from Tiger response text.

    Looks for patterns like 'Order ID:    12345' or 'Order ID: ABC-123'.

    Args:
        text: Tiger MCP response text.

    Returns:
        Order ID string, or None if not found.
    """
    match = re.search(r"Order ID:\s+(\S+)", text)
    return match.group(1) if match else None
