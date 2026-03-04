"""Transaction event dispatcher."""

from __future__ import annotations

from typing import Any

import structlog

from zaza_consumer.plan_index import PlanIndex

logger = structlog.get_logger(__name__)


class TransactionHandler:
    """Routes transaction events to the appropriate handler based on order role."""

    def __init__(
        self,
        plan_index: PlanIndex,
        on_entry_fill: Any,  # Callable -- set after construction to avoid circular imports
        on_stop_fill: Any,
        on_tp_fill: Any,
    ) -> None:
        self._index = plan_index
        self._on_entry_fill = on_entry_fill
        self._on_stop_fill = on_stop_fill
        self._on_tp_fill = on_tp_fill

    async def handle(self, event: dict[str, Any]) -> None:
        """Process a transaction event from the Redis stream.

        Expected event shape: {"orderId": int, "symbol": str, "filledPrice": float,
                               "filledQuantity": int, "action": str, ...}
        """
        order_id = event.get("orderId")
        if order_id is None:
            logger.warning("event_missing_order_id", raw_event=event)
            return

        # Ensure order_id is int
        try:
            order_id = int(order_id)
        except (ValueError, TypeError):
            logger.warning("event_invalid_order_id", order_id=order_id)
            return

        result = self._index.lookup(order_id)
        if result is None:
            logger.debug("event_unknown_order", order_id=order_id)
            return

        plan_id, role = result
        logger.info(
            "event_matched",
            order_id=order_id,
            plan_id=plan_id,
            role=role,
            symbol=event.get("symbol"),
        )

        if role == "entry":
            await self._on_entry_fill(event, plan_id)
        elif role == "stop_loss":
            await self._on_stop_fill(event, plan_id)
        elif role == "take_profit":
            await self._on_tp_fill(event, plan_id)
        else:
            logger.warning("event_unknown_role", role=role, plan_id=plan_id)
