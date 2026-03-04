"""Startup reconciliation and RTH scan loop for crash recovery.

On startup, the reconciler:
1. Rebuilds the in-memory PlanIndex from active trade plans.
2. Detects filled entry orders with missing protective orders.
3. Detects filled stop/TP orders needing OCO cleanup.
4. Re-places expired protective orders during Regular Trading Hours.

The RTH scan loop runs periodically to detect and re-place expired
protective orders that may have been cancelled by the broker at market
close (DAY orders).
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import orjson
import structlog

from zaza_consumer.config import ConsumerSettings
from zaza_consumer.fill_manager import (
    _FILLED_QTY_RE,
    _get_order_id,
    _is_numeric_order_id,
    handle_entry_fill,
)
from zaza_consumer.oco import handle_stop_fill, handle_tp_fill
from zaza_consumer.plan_index import PlanIndex, PlanLocks
from zaza_consumer.rth import is_rth_open

logger = structlog.get_logger(__name__)

# Type alias for the MCP client interface used at runtime.
McpClientsProtocol = Any

# Regex to find order IDs in Tiger MCP text responses.
_ORDER_ID_IN_TEXT_RE = re.compile(
    r"Order\s*(?:ID|_id)\s*[:=]\s*(\d+)", re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_order_ids_in_text(text: str) -> set[int]:
    """Extract all numeric order IDs found in a Tiger MCP text response."""
    return {int(m.group(1)) for m in _ORDER_ID_IN_TEXT_RE.finditer(text)}


def _is_order_expired(
    order_id_str: str | None,
    open_ids: set[int],
    filled_ids: set[int],
) -> bool:
    """Return True if a numeric order ID is neither open nor filled (i.e. expired)."""
    if not _is_numeric_order_id(order_id_str):
        return False
    oid = int(order_id_str)  # type: ignore[arg-type]
    return oid not in open_ids and oid not in filled_ids


async def _fetch_plan_xmls(
    mcp: McpClientsProtocol,
    plans_list: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    """Fetch XML for each plan, returning (plan_id, xml_string) pairs."""
    result: list[tuple[str, str]] = []
    for plan_info in plans_list:
        plan_id = plan_info["plan_id"]
        plan_result = await mcp.get_trade_plan(plan_id)
        plan_data = orjson.loads(plan_result)
        xml_string = plan_data.get("xml", "")
        if xml_string:
            result.append((plan_id, xml_string))
    return result


async def _fetch_broker_state(
    mcp: McpClientsProtocol,
) -> tuple[set[int], set[int]]:
    """Fetch open and filled order IDs from the broker.

    Returns:
        A tuple of (open_order_ids, filled_order_ids).
    """
    open_text = await mcp.get_open_orders()
    filled_text = await mcp.get_filled_orders()
    return _find_order_ids_in_text(open_text), _find_order_ids_in_text(filled_text)


# ---------------------------------------------------------------------------
# Startup reconciliation
# ---------------------------------------------------------------------------


async def reconcile_on_startup(
    mcp: McpClientsProtocol,
    index: PlanIndex,
    settings: ConsumerSettings,
    locks: PlanLocks | None = None,
) -> None:
    """Reconcile plan state against broker orders after a restart.

    Steps:
        1. List all active trade plans and rebuild the PlanIndex.
        2. Fetch open and recently filled broker orders.
        3. For each plan with a numeric entry order_id, check:
           a. Entry filled + no protective orders -> place them.
           b. Stop/TP filled -> run OCO logic.
           c. Protective orders expired during RTH -> re-place them.
    """
    logger.info("reconcile_starting")

    # 1. List active plans and fetch their XML
    plans_json = await mcp.list_trade_plans()
    plans_list: list[dict[str, Any]] = orjson.loads(plans_json)

    if not plans_list:
        logger.info("reconcile_no_active_plans")
        index.rebuild([])
        return

    plan_xmls = await _fetch_plan_xmls(mcp, plans_list)

    # 2. Rebuild the index
    index.rebuild(plan_xmls)
    logger.info("reconcile_index_rebuilt", plans=len(plan_xmls), orders=len(index))

    # 3. Fetch broker state
    open_order_ids, filled_order_ids = await _fetch_broker_state(mcp)

    logger.info(
        "reconcile_broker_state",
        open_orders=len(open_order_ids),
        filled_orders=len(filled_order_ids),
    )

    # 4. Reconcile each plan (with per-plan locking if available)
    for plan_id, xml_string in plan_xmls:
        if locks is not None:
            async with locks.get(plan_id):
                await _reconcile_plan(
                    plan_id=plan_id,
                    xml_string=xml_string,
                    mcp=mcp,
                    index=index,
                    settings=settings,
                    open_order_ids=open_order_ids,
                    filled_order_ids=filled_order_ids,
                )
        else:
            await _reconcile_plan(
                plan_id=plan_id,
                xml_string=xml_string,
                mcp=mcp,
                index=index,
                settings=settings,
                open_order_ids=open_order_ids,
                filled_order_ids=filled_order_ids,
            )

    logger.info("reconcile_complete")


async def _reconcile_plan(
    plan_id: str,
    xml_string: str,
    mcp: McpClientsProtocol,
    index: PlanIndex,
    settings: ConsumerSettings,
    open_order_ids: set[int],
    filled_order_ids: set[int],
) -> None:
    """Reconcile a single trade plan against broker state.

    Handles four cases in priority order:
        A. Entry filled, no protective orders placed -> place them.
        B. Stop-loss filled -> run OCO (cancel TP, close plan).
        C. Take-profit filled -> run OCO (cancel SL, close plan).
        D. Protective orders expired during RTH -> re-place them.
    """
    entry_oid = _get_order_id(xml_string, "entry/limit-order/order_id")
    sl_oid = _get_order_id(xml_string, "exit/stop-loss/limit-order/order_id")
    tp_oid = _get_order_id(xml_string, "exit/take-profit/limit-order/order_id")

    # Skip plans without a numeric entry order (not yet submitted)
    if not _is_numeric_order_id(entry_oid):
        logger.debug("reconcile_skip_non_numeric_entry", plan_id=plan_id)
        return

    entry_id = int(entry_oid)  # type: ignore[arg-type]

    sl_is_numeric = _is_numeric_order_id(sl_oid)
    tp_is_numeric = _is_numeric_order_id(tp_oid)

    # Determine if entry was filled.  The entry is considered filled if:
    # (a) it appears in the recent filled-orders response, OR
    # (b) numeric protective order IDs exist (they are only placed after
    #     entry fills, so their presence implies a prior fill).
    entry_filled = (
        entry_id in filled_order_ids or sl_is_numeric or tp_is_numeric
    )

    if not entry_filled:
        logger.debug("reconcile_entry_not_filled", plan_id=plan_id, entry_id=entry_id)
        return

    # Case A: Entry filled but protective orders not placed (PENDING)
    if not sl_is_numeric and not tp_is_numeric:
        logger.info(
            "reconcile_entry_filled_no_protectives",
            plan_id=plan_id,
            entry_id=entry_id,
        )
        await _rerun_entry_fill(entry_id, plan_id, mcp, index, settings)
        return

    # Case B: Stop-loss filled -> OCO
    if sl_is_numeric and int(sl_oid) in filled_order_ids:  # type: ignore[arg-type]
        sl_id = int(sl_oid)  # type: ignore[arg-type]
        logger.info("reconcile_stop_filled", plan_id=plan_id, sl_id=sl_id)
        await handle_stop_fill(
            event={"orderId": sl_id, "symbol": ""},
            plan_id=plan_id,
            mcp=mcp,
            index=index,
        )
        return

    # Case C: Take-profit filled -> OCO
    if tp_is_numeric and int(tp_oid) in filled_order_ids:  # type: ignore[arg-type]
        tp_id = int(tp_oid)  # type: ignore[arg-type]
        logger.info("reconcile_tp_filled", plan_id=plan_id, tp_id=tp_id)
        await handle_tp_fill(
            event={"orderId": tp_id, "symbol": ""},
            plan_id=plan_id,
            mcp=mcp,
            index=index,
        )
        return

    # Case D: Protective orders expired (not in open orders, not filled)
    sl_expired = _is_order_expired(sl_oid, open_order_ids, filled_order_ids)
    tp_expired = _is_order_expired(tp_oid, open_order_ids, filled_order_ids)

    if (sl_expired or tp_expired) and is_rth_open(
        rth_open_hour=settings.rth_open_hour,
        rth_open_minute=settings.rth_open_minute,
        rth_close_hour=settings.rth_close_hour,
        rth_close_minute=settings.rth_close_minute,
    ):
        logger.info(
            "reconcile_protectives_expired",
            plan_id=plan_id,
            sl_expired=sl_expired,
            tp_expired=tp_expired,
        )
        await _rerun_entry_fill(entry_id, plan_id, mcp, index, settings)

    logger.debug("reconcile_plan_ok", plan_id=plan_id)


async def _rerun_entry_fill(
    entry_id: int,
    plan_id: str,
    mcp: McpClientsProtocol,
    index: PlanIndex,
    settings: ConsumerSettings,
) -> None:
    """Re-run handle_entry_fill with a synthetic event for crash recovery.

    Fetches the actual filled quantity from the broker order detail so
    that ``handle_entry_fill`` can set correct protective order sizes.
    """
    # Fetch filled qty from broker to avoid passing 0
    filled_qty = 0
    try:
        detail = await mcp.get_order_detail(entry_id)
        match = _FILLED_QTY_RE.search(detail)
        if match:
            filled_qty = int(match.group(1))
    except Exception as exc:
        logger.warning(
            "rerun_order_detail_failed",
            entry_id=entry_id,
            error=str(exc),
        )

    synthetic_event = {
        "orderId": entry_id,
        "symbol": "",
        "filledQuantity": filled_qty,
    }
    await handle_entry_fill(
        event=synthetic_event,
        plan_id=plan_id,
        mcp=mcp,
        index=index,
        order_delay_ms=settings.order_delay_ms,
    )


# ---------------------------------------------------------------------------
# RTH scan loop
# ---------------------------------------------------------------------------


async def rth_scan_loop(
    mcp: McpClientsProtocol,
    index: PlanIndex,
    settings: ConsumerSettings,
    locks: PlanLocks | None = None,
) -> None:
    """Periodically scan for expired protective orders during RTH.

    Runs in a ``while True`` loop, sleeping for
    ``settings.rth_scan_interval_seconds`` between scans.
    Only performs the scan when Regular Trading Hours are open.
    """
    logger.info(
        "rth_scan_loop_started",
        interval=settings.rth_scan_interval_seconds,
    )

    while True:
        await asyncio.sleep(settings.rth_scan_interval_seconds)

        if not is_rth_open(
            rth_open_hour=settings.rth_open_hour,
            rth_open_minute=settings.rth_open_minute,
            rth_close_hour=settings.rth_close_hour,
            rth_close_minute=settings.rth_close_minute,
        ):
            logger.debug("rth_scan_skipped_market_closed")
            continue

        logger.info("rth_scan_running")
        try:
            await _run_rth_scan(mcp, index, settings, locks)
        except Exception as exc:
            logger.error(
                "rth_scan_error", error=str(exc), exc_info=True,
            )


async def _run_rth_scan(
    mcp: McpClientsProtocol,
    index: PlanIndex,
    settings: ConsumerSettings,
    locks: PlanLocks | None = None,
) -> None:
    """Scan active plans for expired protective orders and re-place them."""
    plans_json = await mcp.list_trade_plans()
    plans_list: list[dict[str, Any]] = orjson.loads(plans_json)

    if not plans_list:
        return

    open_order_ids, filled_order_ids = await _fetch_broker_state(mcp)

    for plan_info in plans_list:
        plan_id = plan_info["plan_id"]
        plan_result = await mcp.get_trade_plan(plan_id)
        plan_data = orjson.loads(plan_result)
        xml_string = plan_data.get("xml", "")
        if not xml_string:
            continue

        entry_oid = _get_order_id(
            xml_string, "entry/limit-order/order_id",
        )
        if not _is_numeric_order_id(entry_oid):
            continue

        entry_id = int(entry_oid)  # type: ignore[arg-type]

        # Entry must have been filled
        sl_oid = _get_order_id(
            xml_string, "exit/stop-loss/limit-order/order_id",
        )
        tp_oid = _get_order_id(
            xml_string, "exit/take-profit/limit-order/order_id",
        )
        sl_is_numeric = _is_numeric_order_id(sl_oid)
        tp_is_numeric = _is_numeric_order_id(tp_oid)

        entry_filled = (
            entry_id in filled_order_ids
            or sl_is_numeric
            or tp_is_numeric
        )
        if not entry_filled:
            continue

        sl_expired = _is_order_expired(
            sl_oid, open_order_ids, filled_order_ids,
        )
        tp_expired = _is_order_expired(
            tp_oid, open_order_ids, filled_order_ids,
        )

        if sl_expired or tp_expired:
            logger.info(
                "rth_scan_replacing_expired",
                plan_id=plan_id,
                sl_expired=sl_expired,
                tp_expired=tp_expired,
            )
            if locks is not None:
                async with locks.get(plan_id):
                    await _rerun_entry_fill(
                        entry_id, plan_id, mcp, index, settings,
                    )
            else:
                await _rerun_entry_fill(
                    entry_id, plan_id, mcp, index, settings,
                )
