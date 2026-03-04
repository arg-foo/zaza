"""Pro-rata protective order placement and modification.

When an entry order fills, this module places (or modifies) the corresponding
stop-loss and take-profit protective orders. Quantities on protective orders
are set to match the filled quantity of the entry.
"""

from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from typing import Any

import orjson
import structlog

from zaza_consumer.models import TransactionPayload
from zaza_consumer.plan_index import PlanIndex

logger = structlog.get_logger(__name__)

# Type alias for the MCP client interface used at runtime.
# At test time this is replaced by an AsyncMock.
McpClientsProtocol = Any


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------


def _text(parent: ET.Element, tag: str) -> str:
    """Get text content of a child element, raising on missing/empty."""
    elem = parent.find(tag)
    if elem is None or not elem.text:
        raise ValueError(f"Missing or empty <{tag}>")
    return elem.text.strip()


def _parse_exit_params(xml_string: str) -> dict[str, Any]:
    """Parse stop-loss and take-profit parameters from trade plan XML.

    Returns dict with keys:
        sl_stop_price, sl_limit_price, sl_ticker,
        tp_limit_price, tp_ticker
    """
    root = ET.fromstring(xml_string)
    exit_elem = root.find("exit")
    if exit_elem is None:
        raise ValueError("Trade plan XML missing <exit> element")

    result: dict[str, Any] = {}

    sl = exit_elem.find("stop-loss/limit-order")
    if sl is not None:
        result["sl_ticker"] = _text(sl, "ticker")
        result["sl_limit_price"] = float(_text(sl, "limit_price"))
        stop_price_elem = sl.find("stop_price")
        if stop_price_elem is not None and stop_price_elem.text:
            result["sl_stop_price"] = float(stop_price_elem.text.strip())
        else:
            # Use limit_price as stop_price for STP_LMT
            result["sl_stop_price"] = result["sl_limit_price"]

    tp = exit_elem.find("take-profit/limit-order")
    if tp is not None:
        result["tp_ticker"] = _text(tp, "ticker")
        result["tp_limit_price"] = float(_text(tp, "limit_price"))

    return result


def _get_order_id(xml_string: str, path: str) -> str | None:
    """Extract order_id text from XML at the given element path.

    Returns the raw string (e.g. ``"12345"`` or ``"PENDING"``), or ``None``
    if the element is missing or empty.
    """
    root = ET.fromstring(xml_string)
    elem = root.find(path)
    if elem is not None and elem.text:
        return elem.text.strip()
    return None


def _is_numeric_order_id(order_id: str | None) -> bool:
    """Check if an order_id string represents a numeric broker order ID."""
    if order_id is None:
        return False
    try:
        int(order_id)
        return True
    except ValueError:
        return False


def _update_order_id_in_xml(xml_string: str, path: str, new_order_id: str) -> str:
    """Replace the text of the element at *path* with *new_order_id*."""
    root = ET.fromstring(xml_string)
    elem = root.find(path)
    if elem is not None:
        elem.text = new_order_id
    return ET.tostring(root, encoding="unicode")


def _update_quantity_in_xml(xml_string: str, path: str, quantity: str) -> str:
    """Replace the text of the quantity element at *path*."""
    root = ET.fromstring(xml_string)
    elem = root.find(path)
    if elem is not None:
        elem.text = quantity
    return ET.tostring(root, encoding="unicode")


# ---------------------------------------------------------------------------
# Order-detail parsing helpers
# ---------------------------------------------------------------------------

_FILLED_QTY_RE = re.compile(
    r"(?:filled\s*(?:qty|quantity))\s*[:=]\s*(\d+)", re.IGNORECASE,
)

_ORDER_ID_RE = re.compile(
    r"(?:order\s*(?:id|_id))\s*[:=]\s*(\d+)", re.IGNORECASE,
)


def _parse_filled_quantity(order_detail: str, event: TransactionPayload) -> int:
    """Extract filled quantity from order detail text or fall back to event data."""
    match = _FILLED_QTY_RE.search(order_detail)
    if match:
        return int(match.group(1))

    # Fall back to event data
    if event.filled_quantity is not None:
        return event.filled_quantity
    return 0


def _extract_order_id_from_result(result: str) -> str | None:
    """Extract a numeric order ID from Tiger MCP place_order result text."""
    match = _ORDER_ID_RE.search(result)
    if match:
        return match.group(1)
    return None


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------


async def handle_entry_fill(
    event: TransactionPayload,
    plan_id: str,
    mcp: McpClientsProtocol,
    index: PlanIndex,
    order_delay_ms: int = 500,
) -> None:
    """Handle an entry order fill by placing or modifying protective orders.

    Steps:
        1. Get trade plan XML.
        2. Parse exit parameters (SL and TP prices).
        3. Get filled quantity from order detail.
        4. If no protective orders exist, place both STP_LMT and LMT.
        5. If protective orders exist, modify quantities.
        6. Update plan XML with new order IDs and quantities.
    """
    order_id = int(event.order_id)  # type: ignore[arg-type]
    symbol = event.symbol or ""

    logger.info("handling_entry_fill", order_id=order_id, plan_id=plan_id, symbol=symbol)

    # 1. Get current plan XML
    plan_xml_result = await mcp.get_trade_plan(plan_id)
    plan_data = orjson.loads(plan_xml_result)
    xml_string = plan_data.get("xml", "")
    if not xml_string:
        logger.error("empty_trade_plan_xml", plan_id=plan_id)
        return

    # 2. Get filled quantity from order detail
    order_detail = await mcp.get_order_detail(order_id)
    filled_qty = _parse_filled_quantity(order_detail, event)

    if filled_qty <= 0:
        logger.warning("zero_filled_quantity", order_id=order_id)
        return

    # 3. Parse exit parameters
    exit_params = _parse_exit_params(xml_string)

    if "sl_ticker" not in exit_params:
        logger.error("missing_stop_loss_params", plan_id=plan_id)
        return
    if "tp_ticker" not in exit_params:
        logger.error("missing_take_profit_params", plan_id=plan_id)
        return

    # 4. Check existing protective order IDs
    sl_order_id = _get_order_id(xml_string, "exit/stop-loss/limit-order/order_id")
    tp_order_id = _get_order_id(xml_string, "exit/take-profit/limit-order/order_id")

    sl_exists = _is_numeric_order_id(sl_order_id)
    tp_exists = _is_numeric_order_id(tp_order_id)

    updated_xml = xml_string

    # 5. Stop-loss: place or modify
    if not sl_exists:
        sl_result = await mcp.place_order(
            symbol=exit_params["sl_ticker"],
            action="SELL",
            quantity=filled_qty,
            order_type="STP_LMT",
            limit_price=exit_params["sl_limit_price"],
            stop_price=exit_params["sl_stop_price"],
        )
        new_sl_id = _extract_order_id_from_result(sl_result)
        if new_sl_id:
            updated_xml = _update_order_id_in_xml(
                updated_xml, "exit/stop-loss/limit-order/order_id", new_sl_id,
            )
            index.add(int(new_sl_id), plan_id, "stop_loss")
            logger.info("stop_loss_placed", order_id=new_sl_id, qty=filled_qty)

        await asyncio.sleep(order_delay_ms / 1000)
    else:
        await mcp.modify_order(
            order_id=int(sl_order_id),  # type: ignore[arg-type]
            quantity=filled_qty,
        )
        logger.info("stop_loss_modified", order_id=sl_order_id, qty=filled_qty)
        await asyncio.sleep(order_delay_ms / 1000)

    # 6. Take-profit: place or modify
    try:
        if not tp_exists:
            tp_result = await mcp.place_order(
                symbol=exit_params["tp_ticker"],
                action="SELL",
                quantity=filled_qty,
                order_type="LMT",
                limit_price=exit_params["tp_limit_price"],
            )
            new_tp_id = _extract_order_id_from_result(tp_result)
            if new_tp_id:
                updated_xml = _update_order_id_in_xml(
                    updated_xml,
                    "exit/take-profit/limit-order/order_id",
                    new_tp_id,
                )
                index.add(int(new_tp_id), plan_id, "take_profit")
                logger.info(
                    "take_profit_placed",
                    order_id=new_tp_id,
                    qty=filled_qty,
                )
        else:
            await mcp.modify_order(
                order_id=int(tp_order_id),  # type: ignore[arg-type]
                quantity=filled_qty,
            )
            logger.info(
                "take_profit_modified",
                order_id=tp_order_id,
                qty=filled_qty,
            )
    except Exception:
        # Persist partial progress (SL order ID) before re-raising
        await mcp.update_trade_plan(plan_id, updated_xml)
        raise

    # 7. Update quantities in XML and persist
    updated_xml = _update_quantity_in_xml(
        updated_xml, "exit/stop-loss/limit-order/quantity", str(filled_qty),
    )
    updated_xml = _update_quantity_in_xml(
        updated_xml, "exit/take-profit/limit-order/quantity", str(filled_qty),
    )

    await mcp.update_trade_plan(plan_id, updated_xml)
    logger.info("trade_plan_updated", plan_id=plan_id)
