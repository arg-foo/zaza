#!/usr/bin/env python3
"""UserPromptSubmit hook: injects portfolio context into every prompt.

Connects to Zaza MCP (trade plans) and Tiger MCP (account/positions/orders)
via stdio, gathers portfolio state, cross-references trade plan orders with
live order statuses, and outputs structured XML to stdout for Claude Code
to inject into the conversation context.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# --- Environment ---
CLAUDE_PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", ".")
TIGER_MCP_DIR = os.environ.get(
    "TIGER_MCP_DIR",
    str(Path(CLAUDE_PROJECT_DIR).parent / "tiger-brokers-cash-mcp"),
)

# --- MCP Server Parameters ---
ZAZA_CONTAINER = os.environ.get("ZAZA_CONTAINER", "zaza-zaza-1")

ZAZA_SERVER_PARAMS = StdioServerParameters(
    command="docker",
    args=["exec", "-i", ZAZA_CONTAINER, "python", "-m", "zaza.server"],
)

TIGER_SERVER_PARAMS = StdioServerParameters(
    command="uv",
    args=["--directory", TIGER_MCP_DIR, "run", "python", "-m", "tiger_mcp"],
)


# =====================================================================
# Pure parsing functions (no MCP dependency, fully testable)
# =====================================================================


def parse_account_summary(text: str) -> dict:
    """Parse Tiger's formatted account summary text into a dict.

    Handles dollar amounts with commas, negative values in -$X.XX format,
    and standard $X.XX format.

    Args:
        text: Raw text output from Tiger's get_account_summary tool.

    Returns:
        Dict with keys: cash_balance, buying_power, realized_pnl,
        unrealized_pnl, net_liquidation. All values are floats.
    """
    field_map = {
        "Cash Balance": "cash_balance",
        "Buying Power": "buying_power",
        "Realized P&L": "realized_pnl",
        "Unrealized P&L": "unrealized_pnl",
        "Net Liquidation": "net_liquidation",
    }

    result: dict = {}
    for line in text.splitlines():
        line = line.strip()
        for label, key in field_map.items():
            if line.startswith(label):
                # Extract everything after the colon
                value_str = line.split(":", 1)[1].strip()
                result[key] = _parse_dollar_value(value_str)
                break

    return result


def _parse_dollar_value(value_str: str) -> float:
    """Parse a dollar string like '$12,450.00' or '-$125.30' into a float."""
    negative = value_str.startswith("-")
    # Remove $, commas, and leading minus/whitespace
    cleaned = value_str.replace("$", "").replace(",", "").replace("-", "").strip()
    try:
        amount = float(cleaned)
    except (ValueError, TypeError):
        return 0.0
    return -amount if negative else amount


def parse_positions(text: str) -> list[dict]:
    """Parse Tiger's formatted positions text into a list of dicts.

    Handles multiple positions separated by blank lines, single positions,
    and the 'No positions found.' empty case.

    Args:
        text: Raw text output from Tiger's get_positions tool.

    Returns:
        List of dicts, each with keys: symbol, quantity, avg_cost,
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
            # Save previous position if exists
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
                # Format: $125.00 (1.36%) or -$90.00 (-3.40%)
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

    Each order line has the format:
    Order {id}: {sym} {action} {qty} (filled {n}) | type={t} limit={p} status={s} submitted={ts}

    Args:
        text: Raw text output from Tiger's get_open_orders tool.

    Returns:
        List of dicts, each with keys: order_id, symbol, action, quantity,
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


def parse_trade_plan_xml(xml_string: str) -> dict | None:
    """Parse trade plan XML into a structured dict.

    Extracts ticker, side, quantity, optional conviction/ev/rr,
    entry details, stop-loss details, and take-profit details.

    Args:
        xml_string: The trade plan XML string.

    Returns:
        Parsed dict, or None if XML is malformed or missing required elements.
    """
    if not xml_string or not xml_string.strip():
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

    # Optional fields at root level
    conviction_elem = root.find("conviction")
    ev_elem = root.find("expected-value")
    rr_elem = root.find("risk-reward")

    # Entry (required)
    entry = root.find("entry")
    if entry is None:
        return None

    entry_strategy = entry.findtext("strategy")
    entry_trigger = entry.findtext("trigger")
    entry_lo = entry.find("limit-order")

    if entry_lo is None or entry_strategy is None or entry_trigger is None:
        return None

    entry_order_id = entry_lo.findtext("order_id")
    if not entry_order_id:  # None or empty string
        return None

    # Exit (required)
    exit_elem = root.find("exit")
    if exit_elem is None:
        return None

    # Stop-loss
    stop_loss = exit_elem.find("stop-loss")
    if stop_loss is None:
        return None
    sl_trigger = stop_loss.findtext("trigger")
    sl_lo = stop_loss.find("limit-order")
    if sl_lo is None:
        return None
    sl_order_id = sl_lo.findtext("order_id")

    # Take-profit
    take_profit = exit_elem.find("take-profit")
    if take_profit is None:
        return None
    tp_trigger = take_profit.findtext("trigger")
    tp_lo = take_profit.find("limit-order")
    if tp_lo is None:
        return None
    tp_order_id = tp_lo.findtext("order_id")

    return {
        "ticker": root.get("ticker", ""),
        "side": side_elem.text or "",
        "quantity": quantity_elem.text or "",
        "conviction": conviction_elem.text if conviction_elem is not None else None,
        "ev": ev_elem.text if ev_elem is not None else None,
        "rr": rr_elem.text if rr_elem is not None else None,
        "entry": {
            "strategy": entry_strategy,
            "trigger": entry_trigger,
            "order_id": entry_order_id,
        },
        "stop_loss": {
            "trigger": sl_trigger or "",
            "order_id": sl_order_id or "",
        },
        "take_profit": {
            "trigger": tp_trigger or "",
            "order_id": tp_order_id or "",
        },
    }


def cross_reference(plans: list[dict], open_orders: list[dict]) -> list[dict]:
    """Annotate each plan's order_ids with live order status.

    Builds a lookup from order_id -> order dict, then for each plan's
    entry/stop_loss/take_profit, adds an 'order_status' field.

    Args:
        plans: List of parsed trade plan dicts.
        open_orders: List of parsed open order dicts.

    Returns:
        The same plans list with order_status annotations added.
    """
    if not plans:
        return []

    # Build order lookup
    order_lookup: dict[str, dict] = {}
    for order in open_orders:
        order_lookup[order["order_id"]] = order

    result: list[dict] = []
    for plan in plans:
        # Deep copy to avoid mutating originals
        annotated = copy.deepcopy(plan)

        for section_key in ("entry", "stop_loss", "take_profit"):
            section = annotated.get(section_key, {})
            order_id = section.get("order_id", "")
            if order_id in order_lookup:
                section["order_status"] = order_lookup[order_id]["status"]
            else:
                section["order_status"] = "UNKNOWN"

        result.append(annotated)

    return result


def format_output(
    account: dict,
    positions: list[dict],
    open_orders: list[dict],
    plans: list[dict],
    timestamp: str,
) -> str:
    """Build the portfolio context XML output string.

    Computes derived values like weight_pct and current_price per position,
    and formats all sections into well-formed XML.

    Args:
        account: Parsed account summary dict.
        positions: List of parsed position dicts.
        open_orders: List of parsed open order dicts.
        plans: List of cross-referenced trade plan dicts.
        timestamp: ISO 8601 timestamp for the generated attribute.

    Returns:
        Well-formed XML string of the portfolio context.
    """
    root = ET.Element("portfolio-context", generated=timestamp)

    # --- Account section ---
    acct_elem = ET.SubElement(root, "account")
    net_liq = account.get("net_liquidation", 0.0)

    _add_text_child(acct_elem, "cash_balance", f"{account.get('cash_balance', 0.0):.2f}")
    _add_text_child(acct_elem, "buying_power", f"{account.get('buying_power', 0.0):.2f}")
    _add_text_child(acct_elem, "unrealized_pnl", f"{account.get('unrealized_pnl', 0.0):.2f}")
    _add_text_child(acct_elem, "net_liquidation", f"{net_liq:.2f}")
    _add_text_child(acct_elem, "total_portfolio", f"{net_liq:.2f}")

    # --- Positions section ---
    pos_elem = ET.SubElement(root, "positions", count=str(len(positions)))
    for pos in positions:
        market_value = pos.get("market_value", 0.0)
        quantity = pos.get("quantity", 0)
        current_price = market_value / quantity if quantity > 0 else 0.0
        weight_pct = (market_value / net_liq * 100) if net_liq > 0 else 0.0
        pnl = pos.get("unrealized_pnl", 0.0)
        pnl_pct = pos.get("pnl_pct", 0.0)

        attrs = {
            "ticker": pos.get("symbol", ""),
            "qty": str(quantity),
            "avg_cost": f"{pos.get('avg_cost', 0.0):.2f}",
            "current_price": f"{current_price:.2f}",
            "current_value": f"{market_value:.2f}",
            "unrealized_pnl": _format_signed(pnl),
            "pnl_pct": _format_signed_pct(pnl_pct),
            "weight_pct": f"{weight_pct:.1f}%",
        }
        ET.SubElement(pos_elem, "position", **attrs)

    # --- Open orders section ---
    orders_elem = ET.SubElement(root, "open-orders", count=str(len(open_orders)))
    for order in open_orders:
        order_type = order.get("order_type", "")
        attrs: dict[str, str] = {
            "order_id": order.get("order_id", ""),
            "ticker": order.get("symbol", ""),
            "side": order.get("action", ""),
            "type": order_type,
            "qty": str(order.get("quantity", 0)),
        }

        limit_price = order.get("limit_price", "N/A")

        # For STOP_LIMIT orders, use limit_price for both stop and limit
        # (Tiger's get_open_orders doesn't expose aux_price separately)
        if order_type == "STOP_LIMIT":
            attrs["stop"] = limit_price
            attrs["limit"] = limit_price
        else:
            attrs["limit"] = limit_price

        attrs["status"] = order.get("status", "")
        ET.SubElement(orders_elem, "order", **attrs)

    # --- Active trade plans section ---
    plans_elem = ET.SubElement(root, "active-trade-plans", count=str(len(plans)))
    for plan in plans:
        plan_attrs: dict[str, str] = {
            "plan_id": plan.get("plan_id", ""),
            "ticker": plan.get("ticker", ""),
            "side": plan.get("side", ""),
            "qty": plan.get("quantity", ""),
        }

        # Add optional attributes only if present
        if plan.get("conviction") is not None:
            plan_attrs["conviction"] = plan["conviction"]
        if plan.get("ev") is not None:
            plan_attrs["ev"] = plan["ev"]
        if plan.get("rr") is not None:
            plan_attrs["rr"] = plan["rr"]

        plan_elem = ET.SubElement(plans_elem, "trade-plan", **plan_attrs)

        # Entry sub-element
        entry = plan.get("entry", {})
        ET.SubElement(
            plan_elem,
            "entry",
            strategy=entry.get("strategy", ""),
            order_id=entry.get("order_id", ""),
            order_status=entry.get("order_status", "UNKNOWN"),
        )

        # Stop-loss sub-element
        sl = plan.get("stop_loss", {})
        ET.SubElement(
            plan_elem,
            "stop-loss",
            trigger=sl.get("trigger", ""),
            order_id=sl.get("order_id", ""),
            order_status=sl.get("order_status", "UNKNOWN"),
        )

        # Take-profit sub-element
        tp = plan.get("take_profit", {})
        ET.SubElement(
            plan_elem,
            "take-profit",
            trigger=tp.get("trigger", ""),
            order_id=tp.get("order_id", ""),
            order_status=tp.get("order_status", "UNKNOWN"),
        )

    # Serialize to string
    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def _add_text_child(parent: ET.Element, tag: str, text: str) -> ET.Element:
    """Add a child element with text content."""
    child = ET.SubElement(parent, tag)
    child.text = text
    return child


def _extract_text(response) -> str:
    """Safely extract text from MCP response, handling non-text content."""
    if not response.content:
        return ""
    content = response.content[0]
    if hasattr(content, "text"):
        return content.text
    return ""


def _format_signed(value: float) -> str:
    """Format a float with explicit + or - sign."""
    if value >= 0:
        return f"+{value:.2f}"
    return f"{value:.2f}"


def _format_signed_pct(value: float) -> str:
    """Format a percentage with explicit + or - sign and % suffix."""
    if value >= 0:
        return f"+{value:.2f}%"
    return f"{value:.2f}%"


# =====================================================================
# Async MCP orchestration
# =====================================================================


async def fetch_tiger_data(session: ClientSession) -> dict:
    """Call Tiger MCP tools and parse text responses.

    Calls get_account_summary, get_positions, and get_open_orders in
    parallel via asyncio.gather, then parses each text result.

    Args:
        session: An initialized MCP ClientSession connected to Tiger MCP.

    Returns:
        Dict with keys: account, positions, open_orders.
    """
    account_resp, positions_resp, orders_resp = await asyncio.gather(
        session.call_tool("get_account_summary", {}),
        session.call_tool("get_positions", {}),
        session.call_tool("get_open_orders", {}),
    )

    # Extract text content from MCP responses
    account_text = _extract_text(account_resp)
    positions_text = _extract_text(positions_resp)
    orders_text = _extract_text(orders_resp)

    return {
        "account": parse_account_summary(account_text),
        "positions": parse_positions(positions_text),
        "open_orders": parse_open_orders(orders_text),
    }


async def _fetch_single_plan(
    session: ClientSession, plan_id: str
) -> dict | None:
    """Fetch and parse a single trade plan by ID.

    Args:
        session: An initialized MCP ClientSession connected to Zaza MCP.
        plan_id: The trade plan ID to fetch.

    Returns:
        Parsed trade plan dict with plan_id, or None on failure.
    """
    try:
        detail_resp = await session.call_tool(
            "get_trade_plan", {"plan_id": plan_id}
        )
        detail_text = _extract_text(detail_resp) or "{}"
        detail_data = json.loads(detail_text)

        if detail_data.get("status") != "ok":
            return None

        xml_string = detail_data.get("xml", "")
        parsed = parse_trade_plan_xml(xml_string)
        if parsed is not None:
            parsed["plan_id"] = plan_id
            return parsed
        else:
            print(
                f"Warning: Skipping corrupt trade plan {plan_id}",
                file=sys.stderr,
            )
            return None
    except Exception as exc:
        print(
            f"Warning: Error fetching trade plan {plan_id}: {exc}",
            file=sys.stderr,
        )
        return None


async def fetch_zaza_data(session: ClientSession) -> list[dict]:
    """Call Zaza MCP tools to get active trade plans.

    First calls list_trade_plans to get plan IDs, then calls get_trade_plan
    for each active plan concurrently and parses the XML.

    Args:
        session: An initialized MCP ClientSession connected to Zaza MCP.

    Returns:
        List of parsed trade plan dicts (with plan_id added).
    """
    list_resp = await session.call_tool(
        "list_trade_plans", {"include_archived": False}
    )

    list_text = _extract_text(list_resp) or "{}"
    try:
        list_data = json.loads(list_text)
    except (json.JSONDecodeError, TypeError):
        return []

    if list_data.get("status") != "ok":
        return []

    plans_meta = list_data.get("plans", [])
    if not plans_meta:
        return []

    # Fetch all plan details concurrently
    tasks = [
        _fetch_single_plan(session, m.get("plan_id", ""))
        for m in plans_meta
        if m.get("plan_id")
    ]
    results = await asyncio.gather(*tasks)
    return [p for p in results if p is not None]


async def fetch_all() -> dict:
    """Open both MCP connections and gather all portfolio data.

    Connects to Tiger MCP and Zaza MCP servers concurrently via stdio,
    fetches data from both in parallel, and cross-references trade plans
    with orders.

    Returns:
        Dict with keys: account, positions, open_orders, plans, timestamp.
    """
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    async def _get_tiger() -> dict:
        async with stdio_client(TIGER_SERVER_PARAMS) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                return await fetch_tiger_data(session)

    async def _get_zaza() -> list[dict]:
        async with stdio_client(ZAZA_SERVER_PARAMS) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                return await fetch_zaza_data(session)

    tiger_result, zaza_plans = await asyncio.gather(_get_tiger(), _get_zaza())

    # Cross-reference plans with open orders
    annotated_plans = cross_reference(zaza_plans, tiger_result["open_orders"])

    return {
        "account": tiger_result["account"],
        "positions": tiger_result["positions"],
        "open_orders": tiger_result["open_orders"],
        "plans": annotated_plans,
        "timestamp": timestamp,
    }


def main() -> None:
    """Entry point for the UserPromptSubmit hook.

    Reads and discards stdin (hook payload), fetches all portfolio data
    from MCP servers, formats as XML, and prints to stdout. Exits with
    code 0 on success, code 2 on any failure.
    """
    # Consume stdin (hook payload) -- required but unused
    sys.stdin.read()

    async def _run_with_timeout() -> dict:
        return await asyncio.wait_for(fetch_all(), timeout=18.0)

    try:
        data = asyncio.run(_run_with_timeout())

        output = format_output(
            account=data["account"],
            positions=data["positions"],
            open_orders=data["open_orders"],
            plans=data["plans"],
            timestamp=data["timestamp"],
        )

        print(output)
        sys.exit(0)

    except Exception as exc:
        print(f"Hook error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
