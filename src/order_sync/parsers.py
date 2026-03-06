"""Parsers for trade plan XML and Tiger MCP text responses.

Two responsibilities:
1. Trade plan XML parser (new schema) -> TradePlan dataclass
2. Tiger text parsers (positions, open orders) copied from prompt_context.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
# Trade plan dataclass
# ---------------------------------------------------------------------------


@dataclass
class TradePlan:
    """Parsed representation of a trade plan XML document.

    plan_id is set externally after parsing (from Zaza's plan metadata).
    """

    plan_id: str = ""
    ticker: str = ""
    side: str = ""  # BUY or SELL
    quantity: int = 0
    order_id: str = ""  # from <order>/<order_id>
    entry_status: str = ""  # PENDING or COMPLETED
    entry_limit_price: float = 0.0
    sl_stop_price: float = 0.0
    sl_limit_price: float = 0.0
    tp_limit_price: float = 0.0


# ---------------------------------------------------------------------------
# Trade plan XML parser (new schema)
# ---------------------------------------------------------------------------


def parse_trade_plan(xml_string: str | None) -> TradePlan | None:
    """Parse trade plan XML into a TradePlan dataclass.

    Args:
        xml_string: The trade plan XML string.

    Returns:
        Parsed TradePlan, or None if XML is malformed or missing required elements.
    """
    if not xml_string or not isinstance(xml_string, str) or not xml_string.strip():
        return None

    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError:
        return None

    if root.tag != "trade-plan":
        return None

    # Summary (required)
    summary = root.find("summary")
    if summary is None:
        return None

    side_elem = summary.find("side")
    ticker_elem = summary.find("ticker")
    quantity_elem = summary.find("quantity")

    if side_elem is None or ticker_elem is None or quantity_elem is None:
        return None

    # Order (required)
    order_elem = root.find("order")
    if order_elem is None:
        return None

    order_id_elem = order_elem.find("order_id")
    if order_id_elem is None or not (order_id_elem.text or "").strip():
        return None

    # Entry (required)
    entry = order_elem.find("entry")
    if entry is None:
        return None

    status_elem = entry.find("status")
    entry_lo = entry.find("limit-order")
    if entry_lo is None:
        return None

    entry_limit_elem = entry_lo.find("limit_price")

    # Exit (required)
    exit_elem = order_elem.find("exit")
    if exit_elem is None:
        return None

    # Stop-loss
    stop_loss = exit_elem.find("stop-loss")
    if stop_loss is None:
        return None
    sl_lo = stop_loss.find("limit-order")
    if sl_lo is None:
        return None

    sl_stop_elem = sl_lo.find("stop_price")
    sl_limit_elem = sl_lo.find("limit_price")

    # Take-profit
    take_profit = exit_elem.find("take-profit")
    if take_profit is None:
        return None
    tp_lo = take_profit.find("limit-order")
    if tp_lo is None:
        return None

    tp_limit_elem = tp_lo.find("limit_price")

    try:
        quantity = int(float((quantity_elem.text or "0").strip()))
    except (ValueError, TypeError):
        return None

    return TradePlan(
        plan_id="",  # Set externally
        ticker=root.get("ticker", ""),
        side=(side_elem.text or "").strip(),
        quantity=quantity,
        order_id=(order_id_elem.text or "").strip(),
        entry_status=(status_elem.text or "").strip() if status_elem is not None else "",
        entry_limit_price=_safe_float(entry_limit_elem),
        sl_stop_price=_safe_float(sl_stop_elem),
        sl_limit_price=_safe_float(sl_limit_elem),
        tp_limit_price=_safe_float(tp_limit_elem),
    )


def _safe_float(elem: ET.Element | None) -> float:
    """Extract float from an XML element's text, returning 0.0 on failure."""
    if elem is None or not elem.text:
        return 0.0
    try:
        return float(elem.text.strip())
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Tiger text parsers (copied from prompt_context.py)
# ---------------------------------------------------------------------------


def _parse_dollar_value(value_str: str) -> float:
    """Parse a dollar string like '$12,450.00' or '-$125.30' into a float."""
    negative = value_str.startswith("-")
    cleaned = value_str.replace("$", "").replace(",", "").replace("-", "").strip()
    try:
        amount = float(cleaned)
    except (ValueError, TypeError):
        return 0.0
    return -amount if negative else amount


def parse_positions(text: str) -> list[dict]:
    """Parse Tiger's formatted positions text into a list of dicts.

    Args:
        text: Raw text output from Tiger's get_positions tool.

    Returns:
        List of dicts with keys: symbol, quantity, avg_cost,
        market_value, unrealized_pnl, pnl_pct.
    """
    if "No positions found" in text:
        return []

    positions: list[dict] = []
    current_symbol: str | None = None
    current_data: dict = {}

    for line in text.splitlines():
        stripped = line.strip()

        # Skip header lines
        if not stripped or stripped.startswith("Current Positions") or stripped.startswith("==="):
            if current_symbol and current_data:
                current_data["symbol"] = current_symbol
                positions.append(current_data)
                current_data = {}
                current_symbol = None
            continue

        # Check if this line is a ticker symbol (all caps, no colon)
        if ":" not in stripped and re.match(r"^[A-Z]{1,5}([./][A-Z]{1,2})?$", stripped):
            if current_symbol and current_data:
                current_data["symbol"] = current_symbol
                positions.append(current_data)
                current_data = {}
            current_symbol = stripped
            continue

        # Parse data lines with colon
        if ":" in stripped and current_symbol:
            label, value = stripped.split(":", 1)
            label = label.strip()
            value = value.strip()

            if label == "Quantity":
                current_data["quantity"] = int(float(value))
            elif label == "Avg Cost":
                current_data["avg_cost"] = _parse_dollar_value(value)
            elif label == "Market Value":
                current_data["market_value"] = _parse_dollar_value(value)
            elif label == "Unrealized P&L":
                pnl_match = re.match(
                    r"(-?\$[\d,]+\.?\d*)\s*\((-?[\d.]+)%\)",
                    value,
                )
                if pnl_match:
                    current_data["unrealized_pnl"] = _parse_dollar_value(
                        pnl_match.group(1)
                    )
                    current_data["pnl_pct"] = float(pnl_match.group(2))

    # Don't forget the last position
    if current_symbol and current_data:
        current_data["symbol"] = current_symbol
        positions.append(current_data)

    return positions


def parse_open_orders(text: str) -> list[dict]:
    """Parse Tiger's formatted open orders text into a list of dicts.

    Args:
        text: Raw text output from Tiger's get_open_orders tool.

    Returns:
        List of dicts with keys: order_id, symbol, action, quantity,
        filled, order_type, limit_price, status.
    """
    if "No open orders" in text:
        return []

    orders: list[dict] = []
    pattern = re.compile(
        r"Order\s+(\S+):\s+(\S+)\s+(\S+)\s+(\d+)\s+\(filled\s+(\d+)\)"
        r"\s*\|\s*type=(\S+)\s+limit=(\S+)\s+status=(\S+)"
    )

    for line in text.splitlines():
        line = line.strip()
        match = pattern.match(line)
        if match:
            orders.append({
                "order_id": match.group(1),
                "symbol": match.group(2),
                "action": match.group(3),
                "quantity": int(match.group(4)),
                "filled": int(match.group(5)),
                "order_type": match.group(6),
                "limit_price": match.group(7),
                "status": match.group(8),
            })

    return orders


def _extract_text(response: object) -> str:
    """Safely extract text from MCP CallToolResult response.

    Args:
        response: MCP response object with .content list.

    Returns:
        Text string from first content item, or empty string.
    """
    if not getattr(response, "content", None):
        return ""
    content = response.content[0]  # type: ignore[union-attr]
    if hasattr(content, "text"):
        return content.text  # type: ignore[no-any-return]
    return ""
