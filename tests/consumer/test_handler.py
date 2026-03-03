"""Tests for TransactionHandler event dispatch."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from zaza.consumer.handler import TransactionHandler
from zaza.consumer.plan_index import PlanIndex


@pytest.fixture
def plan_index():
    idx = PlanIndex()
    idx.add(100, "plan-001", "entry")
    idx.add(101, "plan-001", "stop_loss")
    idx.add(102, "plan-001", "take_profit")
    return idx


@pytest.fixture
def handler(plan_index):
    return TransactionHandler(
        plan_index=plan_index,
        on_entry_fill=AsyncMock(),
        on_stop_fill=AsyncMock(),
        on_tp_fill=AsyncMock(),
    )


class TestHandle:
    async def test_entry_fill_dispatched(self, handler: TransactionHandler) -> None:
        event = {"orderId": 100, "symbol": "AAPL", "filledQuantity": 50}
        await handler.handle(event)
        handler._on_entry_fill.assert_called_once_with(event, "plan-001")
        handler._on_stop_fill.assert_not_called()
        handler._on_tp_fill.assert_not_called()

    async def test_stop_fill_dispatched(self, handler: TransactionHandler) -> None:
        event = {"orderId": 101, "symbol": "AAPL", "filledQuantity": 50}
        await handler.handle(event)
        handler._on_stop_fill.assert_called_once_with(event, "plan-001")

    async def test_tp_fill_dispatched(self, handler: TransactionHandler) -> None:
        event = {"orderId": 102, "symbol": "AAPL", "filledQuantity": 50}
        await handler.handle(event)
        handler._on_tp_fill.assert_called_once_with(event, "plan-001")

    async def test_unknown_order_id_ignored(self, handler: TransactionHandler) -> None:
        event = {"orderId": 999, "symbol": "AAPL", "filledQuantity": 50}
        await handler.handle(event)
        handler._on_entry_fill.assert_not_called()
        handler._on_stop_fill.assert_not_called()
        handler._on_tp_fill.assert_not_called()

    async def test_missing_order_id_ignored(self, handler: TransactionHandler) -> None:
        event = {"symbol": "AAPL", "filledQuantity": 50}
        await handler.handle(event)
        handler._on_entry_fill.assert_not_called()

    async def test_string_order_id_converted(self, handler: TransactionHandler) -> None:
        """String orderId should be converted to int."""
        event = {"orderId": "100", "symbol": "AAPL", "filledQuantity": 50}
        await handler.handle(event)
        handler._on_entry_fill.assert_called_once_with(event, "plan-001")

    async def test_invalid_order_id_ignored(self, handler: TransactionHandler) -> None:
        """Non-numeric string orderId should be ignored."""
        event = {"orderId": "not-a-number", "symbol": "AAPL"}
        await handler.handle(event)
        handler._on_entry_fill.assert_not_called()
