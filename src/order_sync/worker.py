"""Order Sync Worker — main orchestration.

Connects to Zaza and Tiger MCP servers, fetches active trade plans,
computes order intents, and places orders to re-create expired DAY orders.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

import structlog

from order_sync import config
from order_sync.executor import OrderResult, place_orders
from order_sync.parsers import TradePlan, _extract_text, parse_open_orders, parse_positions, parse_trade_plan
from order_sync.planner import OrderIntent, compute_order_intents

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _setup_logging() -> structlog.stdlib.BoundLogger:
    """Configure structlog for stderr + file output."""
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)

    # File handler
    file_handler = logging.FileHandler(config.LOG_FILE)
    file_handler.setLevel(logging.DEBUG)

    # Stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.INFO)

    # Root logger
    root_logger = logging.getLogger("order_sync")
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stderr_handler)

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    return structlog.get_logger("order_sync")


logger = _setup_logging()


# ---------------------------------------------------------------------------
# MCP data fetching helpers
# ---------------------------------------------------------------------------


async def _fetch_plans_from_session(zaza_session: Any) -> list[TradePlan]:
    """Fetch and parse all active trade plans from Zaza MCP.

    Args:
        zaza_session: MCP ClientSession connected to Zaza.

    Returns:
        List of parsed TradePlan objects.
    """
    list_resp = await zaza_session.call_tool(
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

    plans: list[TradePlan] = []
    for meta in plans_meta:
        plan_id = meta.get("plan_id", "")
        if not plan_id:
            continue

        try:
            detail_resp = await zaza_session.call_tool(
                "get_trade_plan", {"plan_id": plan_id}
            )
            detail_text = _extract_text(detail_resp) or "{}"
            detail_data = json.loads(detail_text)

            if detail_data.get("status") != "ok":
                continue

            xml_string = detail_data.get("xml", "")
            parsed = parse_trade_plan(xml_string)
            if parsed is not None:
                parsed.plan_id = plan_id
                plans.append(parsed)
            else:
                logger.warning("corrupt_trade_plan", plan_id=plan_id)
        except Exception as exc:
            logger.warning("fetch_plan_error", plan_id=plan_id, error=str(exc))

    return plans


async def _fetch_tiger_state(tiger_session: Any) -> tuple[list[dict], list[dict]]:
    """Fetch positions and open orders from Tiger MCP.

    Args:
        tiger_session: MCP ClientSession connected to Tiger.

    Returns:
        Tuple of (positions, open_orders).
    """
    positions_resp, orders_resp = await asyncio.gather(
        tiger_session.call_tool("get_positions", {}),
        tiger_session.call_tool("get_open_orders", {}),
    )

    positions = parse_positions(_extract_text(positions_resp))
    open_orders = parse_open_orders(_extract_text(orders_resp))

    return positions, open_orders


async def _connect_and_call() -> tuple[list[TradePlan], list[dict], list[dict]]:
    """Connect to both MCP servers and fetch all required data.

    Returns:
        Tuple of (plans, positions, open_orders).
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async def _get_plans() -> list[TradePlan]:
        async with streamable_http_client(config.ZAZA_MCP_URL) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                return await _fetch_plans_from_session(session)

    async def _get_tiger() -> tuple[list[dict], list[dict]]:
        async with streamable_http_client(config.TIGER_MCP_URL) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                return await _fetch_tiger_state(session)

    plans_result, tiger_result = await asyncio.gather(_get_plans(), _get_tiger())
    positions, open_orders = tiger_result

    return plans_result, positions, open_orders


async def _place_orders(intents: list[OrderIntent]) -> list[OrderResult]:
    """Connect to Tiger MCP and place orders for actionable intents.

    Args:
        intents: List of non-SKIP OrderIntent objects.

    Returns:
        List of OrderResult objects.
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with streamable_http_client(config.TIGER_MCP_URL) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            return await place_orders(session, intents)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


async def run(dry_run: bool = False) -> int:
    """Main orchestration entry point.

    1. Connect to Zaza MCP and fetch all active trade plans
    2. Connect to Tiger MCP and fetch positions + open orders
    3. Compute order intents
    4. Place orders (unless dry_run)
    5. Log summary and return exit code

    Args:
        dry_run: If True, compute intents but do not place orders.

    Returns:
        Exit code: 0=ok, 1=warnings (bracket failed), 2=critical (OCA failed).
    """
    # 1+2. Fetch all data
    plans, positions, open_orders = await _connect_and_call()

    if not plans:
        logger.info("no_active_plans")
        return 0

    # 3. Compute intents
    intents = compute_order_intents(plans, positions, open_orders)

    for intent in intents:
        logger.info(
            "order_intent",
            plan_id=intent.plan_id,
            ticker=intent.ticker,
            action=intent.action,
            reason=intent.reason,
        )

    if dry_run:
        logger.info("dry_run_complete", total_intents=len(intents))
        return 0

    # 4. Place orders
    actionable = [i for i in intents if i.action != "SKIP"]
    if not actionable:
        logger.info("no_orders_to_place")
        return 0

    results = await _place_orders(actionable)

    # 5. Determine exit code
    placed = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    oca_failed = sum(1 for r in results if not r.success and r.action == "OCA")

    for result in results:
        logger.info(
            "order_result",
            plan_id=result.plan_id,
            ticker=result.ticker,
            action=result.action,
            success=result.success,
            order_id=result.order_id,
            error=result.error,
        )

    logger.info("sync_complete", placed=placed, failed=failed)

    if oca_failed > 0:
        return 2  # CRITICAL: position unprotected
    elif failed > 0:
        return 1  # WARNING: bracket failed (no position opened)
    return 0
