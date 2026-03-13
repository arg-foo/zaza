#!/usr/bin/env python3
"""UserPromptSubmit hook: injects portfolio context into every prompt.

Connects to Zaza MCP (trade plans) and Tiger MCP (account/positions/orders)
via streamable-http, gathers portfolio state, cross-references trade plan orders with
live order statuses, and outputs structured XML to stdout for Claude Code
to inject into the conversation context.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from order_sync.parsers import (
    TradePlan,
    _extract_text,
    _parse_dollar_value,
    parse_open_orders,
    parse_positions,
    parse_trade_plan,
)

# --- MCP Server Parameters ---
ZAZA_MCP_URL = os.environ.get("ZAZA_MCP_URL", "http://localhost:8100/mcp")
TIGER_MCP_URL = os.environ.get("TIGER_MCP_URL", "http://localhost:8000/mcp")


# =====================================================================
# Local parsers (account summary is Tiger-specific, not shared)
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


def cross_reference(plans: list[TradePlan], open_orders: list[dict]) -> list[dict]:
    """Annotate each TradePlan with live order status from broker.

    Args:
        plans: List of parsed TradePlan dataclasses.
        open_orders: List of parsed open order dicts.

    Returns:
        List of dicts with plan fields + order_status annotation.
    """
    if not plans:
        return []

    order_lookup = {o["order_id"]: o for o in open_orders}

    result: list[dict] = []
    for plan in plans:
        plan_dict = {
            "plan_id": plan.plan_id,
            "ticker": plan.ticker,
            "side": plan.side,
            "quantity": str(plan.quantity),
            "conviction": plan.conviction or None,
            "ev": plan.expected_value or None,
            "rr": plan.risk_reward_ratio or None,
            "entry_strategy": plan.entry_strategy,
            "entry_status": plan.entry_status,
            "order_id": plan.order_id,
            "entry_limit_price": plan.entry_limit_price,
            "sl_stop_price": plan.sl_stop_price,
            "sl_limit_price": plan.sl_limit_price,
            "tp_limit_price": plan.tp_limit_price,
            "position_status": plan.position_status,
            "position_quantity": plan.position_quantity,
            "position_avg_cost": plan.position_avg_cost,
            "order_status": order_lookup[plan.order_id]["status"]
            if plan.order_id in order_lookup
            else "UNKNOWN",
        }
        result.append(plan_dict)

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
            "position_status": plan.get("position_status", "NONE"),
        }

        # Add position details when HELD
        if plan.get("position_status") == "HELD":
            plan_attrs["position_qty"] = str(plan.get("position_quantity", 0))
            plan_attrs["position_avg_cost"] = f"{plan.get('position_avg_cost', 0.0):.2f}"

        # Add optional attributes only if present
        if plan.get("conviction") is not None:
            plan_attrs["conviction"] = plan["conviction"]
        if plan.get("ev") is not None:
            plan_attrs["ev"] = plan["ev"]
        if plan.get("rr") is not None:
            plan_attrs["rr"] = plan["rr"]

        plan_elem = ET.SubElement(plans_elem, "trade-plan", **plan_attrs)

        # Order sub-element (mirrors <order>-wrapped schema)
        order_attrs: dict[str, str] = {
            "order_id": plan.get("order_id", ""),
            "order_status": plan.get("order_status", "UNKNOWN"),
            "entry_status": plan.get("entry_status", ""),
        }
        order_elem = ET.SubElement(plan_elem, "order", **order_attrs)

        # Entry
        entry_attrs: dict[str, str] = {
            "strategy": plan.get("entry_strategy", ""),
        }
        entry_limit = plan.get("entry_limit_price")
        if entry_limit:
            entry_attrs["limit_price"] = f"{entry_limit:.2f}"
        ET.SubElement(order_elem, "entry", **entry_attrs)

        # Stop-loss
        sl_attrs: dict[str, str] = {}
        sl_stop = plan.get("sl_stop_price")
        sl_limit = plan.get("sl_limit_price")
        if sl_stop:
            sl_attrs["stop_price"] = f"{sl_stop:.2f}"
        if sl_limit:
            sl_attrs["limit_price"] = f"{sl_limit:.2f}"
        ET.SubElement(order_elem, "stop-loss", **sl_attrs)

        # Take-profit
        tp_attrs: dict[str, str] = {}
        tp_limit = plan.get("tp_limit_price")
        if tp_limit:
            tp_attrs["limit_price"] = f"{tp_limit:.2f}"
        ET.SubElement(order_elem, "take-profit", **tp_attrs)

    # Serialize to string
    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def _add_text_child(parent: ET.Element, tag: str, text: str) -> ET.Element:
    """Add a child element with text content."""
    child = ET.SubElement(parent, tag)
    child.text = text
    return child


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
) -> TradePlan | None:
    """Fetch and parse a single trade plan by ID.

    Args:
        session: An initialized MCP ClientSession connected to Zaza MCP.
        plan_id: The trade plan ID to fetch.

    Returns:
        Parsed TradePlan with plan_id set, or None on failure.
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
        parsed = parse_trade_plan(xml_string)
        if parsed is not None:
            parsed.plan_id = plan_id
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


async def fetch_zaza_data(session: ClientSession) -> list[TradePlan]:
    """Call Zaza MCP tools to get active trade plans.

    First calls list_trade_plans to get plan IDs, then calls get_trade_plan
    for each active plan concurrently and parses the XML.

    Args:
        session: An initialized MCP ClientSession connected to Zaza MCP.

    Returns:
        List of parsed TradePlan dataclasses (with plan_id set).
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
        async with streamable_http_client(TIGER_MCP_URL) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                return await fetch_tiger_data(session)

    async def _get_zaza() -> list[TradePlan]:
        async with streamable_http_client(ZAZA_MCP_URL) as (r, w, _):
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

        # Log summary directly to terminal (bypass Claude Code capture)
        cash = data["account"].get("cash_balance", 0.0)
        net_liq = data["account"].get("net_liquidation", 0.0)
        n_pos = len(data["positions"])
        n_orders = len(data["open_orders"])
        n_plans = len(data["plans"])
        try:
            with open("/dev/tty", "w") as tty:
                tty.write(
                    f"\033[90m[portfolio] cash=${cash:,.2f} | net_liq=${net_liq:,.2f} | "
                    f"positions={n_pos} | orders={n_orders} | plans={n_plans}\033[0m\n"
                )
        except OSError:
            pass  # No controlling terminal (e.g. CI)

        print(output)
        sys.exit(0)

    except Exception as exc:
        print(f"Hook error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
