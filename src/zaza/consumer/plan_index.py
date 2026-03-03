"""In-memory index mapping order_id -> (plan_id, role) for fast fill routing."""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET

import structlog

logger = structlog.get_logger(__name__)

# XPath expressions for each order role within a trade-plan XML.
_ROLE_XPATHS: list[tuple[str, str]] = [
    ("entry", ".//entry/limit-order/order_id"),
    ("stop_loss", ".//exit/stop-loss/limit-order/order_id"),
    ("take_profit", ".//exit/take-profit/limit-order/order_id"),
]


class PlanLocks:
    """Per-plan_id asyncio.Lock manager to serialise concurrent access.

    Prevents race conditions between the Redis stream handler and the
    RTH scan loop / reconciler when they process the same plan.
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def get(self, plan_id: str) -> asyncio.Lock:
        """Return the lock for *plan_id*, creating it if needed."""
        if plan_id not in self._locks:
            self._locks[plan_id] = asyncio.Lock()
        return self._locks[plan_id]

    def remove(self, plan_id: str) -> None:
        """Remove the lock for *plan_id*.  No-op if absent."""
        self._locks.pop(plan_id, None)


class PlanIndex:
    """Maintains an in-memory mapping of order_id (int) -> (plan_id, role).

    Roles are ``"entry"``, ``"stop_loss"``, and ``"take_profit"``.
    Only purely numeric order_ids are indexed; placeholder strings such as
    ``"BUY-AAPL-001"`` are silently skipped.
    """

    def __init__(self) -> None:
        self._index: dict[int, tuple[str, str]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rebuild(self, plans: list[tuple[str, str]]) -> None:
        """Rebuild the index from a list of (plan_id, xml_string) tuples.

        Clears the existing index, then parses each XML and extracts
        numeric order_ids from entry, stop-loss, and take-profit elements.
        """
        self._index.clear()

        for plan_id, xml_string in plans:
            self._index_plan(plan_id, xml_string)

        logger.info(
            "plan_index_rebuilt",
            plans_processed=len(plans),
            orders_indexed=len(self._index),
        )

    def lookup(self, order_id: int) -> tuple[str, str] | None:
        """O(1) lookup of an order_id.

        Returns:
            ``(plan_id, role)`` if found, ``None`` otherwise.
        """
        return self._index.get(order_id)

    def add(self, order_id: int, plan_id: str, role: str) -> None:
        """Add a single order_id -> (plan_id, role) mapping."""
        self._index[order_id] = (plan_id, role)
        logger.debug("plan_index_add", order_id=order_id, plan_id=plan_id, role=role)

    def remove(self, order_id: int) -> None:
        """Remove a single entry. No-op if the order_id is not present."""
        self._index.pop(order_id, None)

    def remove_plan(self, plan_id: str) -> None:
        """Remove ALL entries associated with *plan_id*."""
        to_remove = [
            oid for oid, (pid, _role) in self._index.items() if pid == plan_id
        ]
        for oid in to_remove:
            del self._index[oid]

        logger.debug(
            "plan_index_remove_plan",
            plan_id=plan_id,
            removed_count=len(to_remove),
        )

    def __len__(self) -> int:
        """Return the number of indexed entries."""
        return len(self._index)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _index_plan(self, plan_id: str, xml_string: str) -> None:
        """Parse a single plan XML and add its numeric order_ids."""
        try:
            root = ET.fromstring(xml_string)
        except ET.ParseError:
            logger.warning("plan_index_parse_error", plan_id=plan_id)
            return

        for role, xpath in _ROLE_XPATHS:
            elem = root.find(xpath)
            if elem is None or elem.text is None:
                continue

            raw = elem.text.strip()
            if not raw.isdigit():
                logger.debug(
                    "plan_index_skip_non_numeric",
                    plan_id=plan_id,
                    role=role,
                    order_id_raw=raw,
                )
                continue

            order_id = int(raw)
            self._index[order_id] = (plan_id, role)
            logger.debug(
                "plan_index_indexed",
                plan_id=plan_id,
                role=role,
                order_id=order_id,
            )
