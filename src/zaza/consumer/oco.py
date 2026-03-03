"""OCO (One-Cancels-Other) logic for protective order fills.

When a stop-loss fills, the take-profit is cancelled (and vice versa).
After cancellation, the trade plan is closed with the appropriate reason
and all entries are removed from the PlanIndex.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import orjson
import structlog

from zaza.consumer.plan_index import PlanIndex

logger = structlog.get_logger(__name__)

# Type alias for the MCP client interface used at runtime.
McpClientsProtocol = Any


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------


def _get_order_id_from_xml(xml_string: str, path: str) -> int | None:
    """Extract a numeric order_id from XML at the given element path.

    Returns the integer order_id, or ``None`` if the element is missing,
    empty, or contains a non-numeric placeholder (e.g. ``"PENDING"``).
    """
    root = ET.fromstring(xml_string)
    elem = root.find(path)
    if elem is not None and elem.text:
        text = elem.text.strip()
        try:
            return int(text)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# OCO handlers
# ---------------------------------------------------------------------------


async def handle_stop_fill(
    event: dict[str, Any],
    plan_id: str,
    mcp: McpClientsProtocol,
    index: PlanIndex,
) -> None:
    """Handle stop-loss fill: cancel take-profit, close plan.

    Steps:
        1. Get trade plan to find take-profit order_id.
        2. Cancel the take-profit order (best-effort).
        3. Close the trade plan with reason ``"stop_hit"``.
        4. Remove all plan entries from index.
    """
    order_id = int(event["orderId"])
    logger.info("handling_stop_fill", order_id=order_id, plan_id=plan_id)

    # Get trade plan to find the TP order_id
    plan_result = await mcp.get_trade_plan(plan_id)
    plan_data = orjson.loads(plan_result)
    xml_string = plan_data.get("xml", "")

    tp_order_id = _get_order_id_from_xml(
        xml_string, "exit/take-profit/limit-order/order_id",
    )

    if tp_order_id is not None:
        try:
            await mcp.cancel_order(tp_order_id)
            logger.info("take_profit_cancelled", order_id=tp_order_id)
        except Exception as exc:
            # Order may already be expired/cancelled -- log and continue
            logger.warning("cancel_tp_failed", order_id=tp_order_id, error=str(exc))

    # Close the trade plan
    await mcp.close_trade_plan(plan_id, reason="stop_hit")
    logger.info("plan_closed", plan_id=plan_id, reason="stop_hit")

    # Remove all entries from index
    index.remove_plan(plan_id)


async def handle_tp_fill(
    event: dict[str, Any],
    plan_id: str,
    mcp: McpClientsProtocol,
    index: PlanIndex,
) -> None:
    """Handle take-profit fill: cancel stop-loss, close plan.

    Steps:
        1. Get trade plan to find stop-loss order_id.
        2. Cancel the stop-loss order (best-effort).
        3. Close the trade plan with reason ``"target_hit"``.
        4. Remove all plan entries from index.
    """
    order_id = int(event["orderId"])
    logger.info("handling_tp_fill", order_id=order_id, plan_id=plan_id)

    # Get trade plan to find the SL order_id
    plan_result = await mcp.get_trade_plan(plan_id)
    plan_data = orjson.loads(plan_result)
    xml_string = plan_data.get("xml", "")

    sl_order_id = _get_order_id_from_xml(
        xml_string, "exit/stop-loss/limit-order/order_id",
    )

    if sl_order_id is not None:
        try:
            await mcp.cancel_order(sl_order_id)
            logger.info("stop_loss_cancelled", order_id=sl_order_id)
        except Exception as exc:
            # Order may already be expired/cancelled -- log and continue
            logger.warning("cancel_sl_failed", order_id=sl_order_id, error=str(exc))

    # Close the trade plan
    await mcp.close_trade_plan(plan_id, reason="target_hit")
    logger.info("plan_closed", plan_id=plan_id, reason="target_hit")

    # Remove all entries from index
    index.remove_plan(plan_id)
