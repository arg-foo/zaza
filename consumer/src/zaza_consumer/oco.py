"""OCO (One-Cancels-Other) logic for protective order fills.

When a stop-loss fills, the take-profit is cancelled (and vice versa).
After cancellation, the trade plan is closed with the appropriate reason
and all entries are removed from the PlanIndex.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

import orjson
import structlog

from zaza_consumer.models import TransactionPayload
from zaza_consumer.plan_index import PlanIndex

logger = structlog.get_logger(__name__)

# Type alias for the MCP client interface used at runtime.
McpClientsProtocol = Any

# Regex patterns for parsing order detail text.
_FILLED_QTY_RE = re.compile(
    r"(?:filled\s*(?:qty|quantity))\s*[:=]\s*(\d+)", re.IGNORECASE,
)
_TOTAL_QTY_RE = re.compile(
    r"(?:qty|quantity)\s*[:=]\s*(\d+)", re.IGNORECASE,
)


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


def _parse_fill_completeness(
    order_detail: str,
) -> tuple[int, int]:
    """Parse filled and total quantities from order detail text.

    Returns:
        A tuple of ``(filled_qty, total_qty)``.  Both default to ``0``
        if parsing fails.
    """
    filled_match = _FILLED_QTY_RE.search(order_detail)
    filled_qty = int(filled_match.group(1)) if filled_match else 0

    # _TOTAL_QTY_RE matches "Qty: N" generically.  The first match that
    # is NOT the filled quantity line is the total qty.  We iterate all
    # matches and pick the first one whose value differs from the filled
    # line offset (i.e., not the filled qty match).
    total_qty = 0
    for m in _TOTAL_QTY_RE.finditer(order_detail):
        # Skip the match that belongs to "Filled Qty: ..."
        if filled_match and m.start() == filled_match.start():
            continue
        total_qty = int(m.group(1))
        break

    return filled_qty, total_qty


async def _is_fully_filled(
    order_id: int,
    mcp: McpClientsProtocol,
) -> bool:
    """Check whether the order is fully filled via ``get_order_detail``.

    Returns ``True`` when ``filled_qty >= total_qty`` and both are > 0.
    If the order detail cannot be parsed, defaults to ``True`` (safe
    fallback -- proceed with OCO closure rather than leaving orphaned
    orders).
    """
    try:
        detail = await mcp.get_order_detail(order_id)
    except Exception as exc:
        logger.warning(
            "order_detail_fetch_failed",
            order_id=order_id,
            error=str(exc),
        )
        return True  # safe fallback

    filled_qty, total_qty = _parse_fill_completeness(detail)

    if filled_qty <= 0 or total_qty <= 0:
        # Cannot determine -- assume fully filled (safe fallback)
        return True

    return filled_qty >= total_qty


# ---------------------------------------------------------------------------
# OCO handlers
# ---------------------------------------------------------------------------


async def handle_stop_fill(
    event: TransactionPayload,
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
    order_id = int(event.order_id)  # type: ignore[arg-type]
    logger.info("handling_stop_fill", order_id=order_id, plan_id=plan_id)

    # Check if this is a partial or full fill
    if not await _is_fully_filled(order_id, mcp):
        logger.info(
            "partial_stop_fill_ignored",
            order_id=order_id,
            plan_id=plan_id,
        )
        return

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
            logger.warning(
                "cancel_tp_failed",
                order_id=tp_order_id,
                error=str(exc),
            )

    # Close the trade plan
    await mcp.close_trade_plan(plan_id, reason="stop_hit")
    logger.info("plan_closed", plan_id=plan_id, reason="stop_hit")

    # Remove all entries from index
    index.remove_plan(plan_id)


async def handle_tp_fill(
    event: TransactionPayload,
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
    order_id = int(event.order_id)  # type: ignore[arg-type]
    logger.info("handling_tp_fill", order_id=order_id, plan_id=plan_id)

    # Check if this is a partial or full fill
    if not await _is_fully_filled(order_id, mcp):
        logger.info(
            "partial_tp_fill_ignored",
            order_id=order_id,
            plan_id=plan_id,
        )
        return

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
            logger.warning(
                "cancel_sl_failed",
                order_id=sl_order_id,
                error=str(exc),
            )

    # Close the trade plan
    await mcp.close_trade_plan(plan_id, reason="target_hit")
    logger.info("plan_closed", plan_id=plan_id, reason="target_hit")

    # Remove all entries from index
    index.remove_plan(plan_id)
