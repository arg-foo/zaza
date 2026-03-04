"""Entry point for the trade execution consumer.

Usage::

    python -m zaza_consumer

Connects to Tiger and Zaza MCP servers, reconciles plan state on startup,
then consumes the Redis transaction stream and manages the order lifecycle.
"""

from __future__ import annotations

import asyncio

import structlog

from zaza_consumer.config import ConsumerSettings
from zaza_consumer.fill_manager import handle_entry_fill
from zaza_consumer.handler import TransactionHandler
from zaza_consumer.mcp_clients import McpClients
from zaza_consumer.models import TransactionPayload
from zaza_consumer.oco import handle_stop_fill, handle_tp_fill
from zaza_consumer.plan_index import PlanIndex, PlanLocks
from zaza_consumer.reconciler import reconcile_on_startup, rth_scan_loop
from zaza_consumer.stream import consume_stream

logger = structlog.get_logger(__name__)


async def main() -> None:
    """Run the trade execution consumer."""
    settings = ConsumerSettings.from_env()

    # Initialize MCP clients
    mcp = McpClients(settings.tiger_mcp_url, settings.zaza_mcp_url)
    await mcp.connect()

    # Initialize plan index and per-plan locks
    index = PlanIndex()
    locks = PlanLocks()

    # Startup reconciliation
    await reconcile_on_startup(mcp, index, settings, locks)

    # Build handler with closures that capture mcp, index, settings, locks
    async def _on_entry(
        event: TransactionPayload, plan_id: str,
    ) -> None:
        async with locks.get(plan_id):
            await handle_entry_fill(
                event, plan_id, mcp, index, settings.order_delay_ms,
            )

    async def _on_stop(
        event: TransactionPayload, plan_id: str,
    ) -> None:
        async with locks.get(plan_id):
            await handle_stop_fill(event, plan_id, mcp, index)
        locks.remove(plan_id)

    async def _on_tp(
        event: TransactionPayload, plan_id: str,
    ) -> None:
        async with locks.get(plan_id):
            await handle_tp_fill(event, plan_id, mcp, index)
        locks.remove(plan_id)

    tx_handler = TransactionHandler(index, _on_entry, _on_stop, _on_tp)

    # Start RTH scan in background
    rth_task = asyncio.create_task(
        rth_scan_loop(mcp, index, settings, locks),
    )

    # Start Redis consumer loop
    try:
        await consume_stream(settings, tx_handler.handle)
    finally:
        rth_task.cancel()
        try:
            await rth_task
        except asyncio.CancelledError:
            pass
        await mcp.close()
        logger.info("consumer_shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
