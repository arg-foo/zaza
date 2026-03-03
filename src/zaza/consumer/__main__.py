"""Entry point for the trade execution consumer.

Usage::

    python -m zaza.consumer

Connects to Tiger and Zaza MCP servers, reconciles plan state on startup,
then consumes the Redis transaction stream and manages the order lifecycle.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

import structlog

from zaza.consumer.config import ConsumerSettings
from zaza.consumer.fill_manager import handle_entry_fill
from zaza.consumer.handler import TransactionHandler
from zaza.consumer.mcp_clients import McpClients
from zaza.consumer.oco import handle_stop_fill, handle_tp_fill
from zaza.consumer.plan_index import PlanIndex
from zaza.consumer.reconciler import reconcile_on_startup, rth_scan_loop
from zaza.consumer.stream import consume_stream

logger = structlog.get_logger(__name__)


async def main() -> None:
    """Run the trade execution consumer."""
    settings = ConsumerSettings.from_env()

    # Initialize MCP clients
    mcp = McpClients(settings.tiger_mcp_url, settings.zaza_mcp_url)
    await mcp.connect()

    # Initialize plan index
    index = PlanIndex()

    # Startup reconciliation
    await reconcile_on_startup(mcp, index, settings)

    # Build handler with closures that capture mcp, index, and settings
    def _on_entry(event: dict[str, Any], plan_id: str) -> Coroutine[Any, Any, None]:
        return handle_entry_fill(event, plan_id, mcp, index, settings.order_delay_ms)

    def _on_stop(event: dict[str, Any], plan_id: str) -> Coroutine[Any, Any, None]:
        return handle_stop_fill(event, plan_id, mcp, index)

    def _on_tp(event: dict[str, Any], plan_id: str) -> Coroutine[Any, Any, None]:
        return handle_tp_fill(event, plan_id, mcp, index)

    tx_handler = TransactionHandler(index, _on_entry, _on_stop, _on_tp)

    # Start RTH scan in background
    rth_task = asyncio.create_task(rth_scan_loop(mcp, index, settings))

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
