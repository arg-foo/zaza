"""Tests for OCO (One-Cancels-Other) logic for protective order fills."""

from __future__ import annotations

from unittest.mock import AsyncMock

import orjson

from zaza_consumer.models import TransactionPayload
from zaza_consumer.oco import (
    _get_order_id_from_xml,
    handle_stop_fill,
    handle_tp_fill,
)
from zaza_consumer.plan_index import PlanIndex

# ---------------------------------------------------------------------------
# Sample XML fixtures
# ---------------------------------------------------------------------------

PLAN_WITH_ORDERS_XML = '''<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC">
  <summary><side>BUY</side><ticker>AAPL</ticker><quantity>50</quantity></summary>
  <entry>
    <strategy>support_bounce</strategy><trigger>Price holds above $183.50</trigger>
    <limit-order>
      <order_id>12345</order_id><type>LIMIT</type><side>BUY</side><ticker>AAPL</ticker>
      <quantity>50</quantity><limit_price>184.00</limit_price><time_in_force>DAY</time_in_force>
    </limit-order>
  </entry>
  <exit>
    <stop-loss>
      <limit-order>
        <order_id>12346</order_id><type>STOP_LIMIT</type><side>SELL</side><ticker>AAPL</ticker>
        <quantity>50</quantity><limit_price>179.50</limit_price><time_in_force>DAY</time_in_force>
      </limit-order>
    </stop-loss>
    <take-profit>
      <limit-order>
        <order_id>12347</order_id><type>LIMIT</type><side>SELL</side><ticker>AAPL</ticker>
        <quantity>50</quantity><limit_price>194.50</limit_price><time_in_force>DAY</time_in_force>
      </limit-order>
    </take-profit>
  </exit>
</trade-plan>'''

PLAN_WITHOUT_TP_ORDER_XML = '''<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC">
  <summary><side>BUY</side><ticker>AAPL</ticker><quantity>50</quantity></summary>
  <entry>
    <strategy>support_bounce</strategy><trigger>Price holds above $183.50</trigger>
    <limit-order>
      <order_id>12345</order_id><type>LIMIT</type><side>BUY</side><ticker>AAPL</ticker>
      <quantity>50</quantity><limit_price>184.00</limit_price><time_in_force>DAY</time_in_force>
    </limit-order>
  </entry>
  <exit>
    <stop-loss>
      <limit-order>
        <order_id>12346</order_id><type>STOP_LIMIT</type><side>SELL</side><ticker>AAPL</ticker>
        <quantity>50</quantity><limit_price>179.50</limit_price><time_in_force>DAY</time_in_force>
      </limit-order>
    </stop-loss>
    <take-profit>
      <limit-order>
        <order_id>PENDING</order_id><type>LIMIT</type><side>SELL</side><ticker>AAPL</ticker>
        <quantity>50</quantity><limit_price>194.50</limit_price><time_in_force>DAY</time_in_force>
      </limit-order>
    </take-profit>
  </exit>
</trade-plan>'''

PLAN_WITHOUT_SL_ORDER_XML = '''<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC">
  <summary><side>BUY</side><ticker>AAPL</ticker><quantity>50</quantity></summary>
  <entry>
    <strategy>support_bounce</strategy><trigger>Price holds above $183.50</trigger>
    <limit-order>
      <order_id>12345</order_id><type>LIMIT</type><side>BUY</side><ticker>AAPL</ticker>
      <quantity>50</quantity><limit_price>184.00</limit_price><time_in_force>DAY</time_in_force>
    </limit-order>
  </entry>
  <exit>
    <stop-loss>
      <limit-order>
        <order_id>PENDING</order_id><type>STOP_LIMIT</type><side>SELL</side><ticker>AAPL</ticker>
        <quantity>50</quantity><limit_price>179.50</limit_price><time_in_force>DAY</time_in_force>
      </limit-order>
    </stop-loss>
    <take-profit>
      <limit-order>
        <order_id>12347</order_id><type>LIMIT</type><side>SELL</side><ticker>AAPL</ticker>
        <quantity>50</quantity><limit_price>194.50</limit_price><time_in_force>DAY</time_in_force>
      </limit-order>
    </take-profit>
  </exit>
</trade-plan>'''


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan_json(xml: str) -> str:
    """Wrap plan XML in the JSON structure returned by get_trade_plan."""
    return orjson.dumps({"xml": xml}).decode()


def _make_mcp_mock() -> AsyncMock:
    """Create a McpClients mock with sensible defaults."""
    mcp = AsyncMock()
    mcp.cancel_order.return_value = "Order cancelled"
    mcp.close_trade_plan.return_value = "Plan archived"
    return mcp


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


class TestGetOrderIdFromXml:
    """Tests for _get_order_id_from_xml."""

    def test_returns_numeric_order_id(self) -> None:
        oid = _get_order_id_from_xml(
            PLAN_WITH_ORDERS_XML, "exit/stop-loss/limit-order/order_id"
        )
        assert oid == 12346

    def test_returns_none_for_non_numeric(self) -> None:
        oid = _get_order_id_from_xml(
            PLAN_WITHOUT_TP_ORDER_XML, "exit/take-profit/limit-order/order_id"
        )
        assert oid is None

    def test_returns_none_for_missing_path(self) -> None:
        oid = _get_order_id_from_xml(
            PLAN_WITH_ORDERS_XML, "exit/nonexistent/order_id"
        )
        assert oid is None


# ---------------------------------------------------------------------------
# Integration tests for handle_stop_fill
# ---------------------------------------------------------------------------


class TestHandleStopFill:
    """Tests for handle_stop_fill — stop-loss fill triggers TP cancellation."""

    async def test_stop_fill_cancels_tp_and_closes_plan(self) -> None:
        """Stop-loss fill cancels take-profit order and closes plan as stop_hit."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(PLAN_WITH_ORDERS_XML)
        mcp.get_order_detail.return_value = (
            "Order ID: 12346\nQty: 50\nFilled Qty: 50\n"
            "Status: FILLED"
        )

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")
        index.add(12346, "plan-001", "stop_loss")
        index.add(12347, "plan-001", "take_profit")

        event = TransactionPayload(
            order_id="12346", symbol="AAPL", filled_quantity=50,
        )

        await handle_stop_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index,
        )

        # TP order should be cancelled
        mcp.cancel_order.assert_called_once_with(12347)

        # Plan closed with reason "stop_hit"
        mcp.close_trade_plan.assert_called_once_with(
            "plan-001", reason="stop_hit",
        )

    async def test_cancel_failure_still_closes_plan(self) -> None:
        """If cancel_order fails (e.g., already expired), plan is still closed."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(PLAN_WITH_ORDERS_XML)
        mcp.get_order_detail.return_value = (
            "Order ID: 12346\nQty: 50\nFilled Qty: 50\n"
            "Status: FILLED"
        )
        mcp.cancel_order.side_effect = Exception("Order already cancelled")

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")
        index.add(12346, "plan-001", "stop_loss")
        index.add(12347, "plan-001", "take_profit")

        event = TransactionPayload(
            order_id="12346", symbol="AAPL", filled_quantity=50,
        )

        # Should NOT raise despite cancel failure
        await handle_stop_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index,
        )

        # Plan still closed
        mcp.close_trade_plan.assert_called_once_with(
            "plan-001", reason="stop_hit",
        )

    async def test_removes_plan_from_index(self) -> None:
        """After stop fill, all plan entries removed from PlanIndex."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(PLAN_WITH_ORDERS_XML)
        mcp.get_order_detail.return_value = (
            "Order ID: 12346\nQty: 50\nFilled Qty: 50\n"
            "Status: FILLED"
        )

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")
        index.add(12346, "plan-001", "stop_loss")
        index.add(12347, "plan-001", "take_profit")
        # Add another plan to verify it survives
        index.add(99999, "plan-other", "entry")

        event = TransactionPayload(
            order_id="12346", symbol="AAPL", filled_quantity=50,
        )

        await handle_stop_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index,
        )

        # plan-001 entries gone
        assert index.lookup(12345) is None
        assert index.lookup(12346) is None
        assert index.lookup(12347) is None
        # Other plan survives
        assert index.lookup(99999) == ("plan-other", "entry")

    async def test_no_counterpart_order_still_closes(self) -> None:
        """If TP order_id is non-numeric (PENDING), skip cancel but still close."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(
            PLAN_WITHOUT_TP_ORDER_XML
        )
        mcp.get_order_detail.return_value = (
            "Order ID: 12346\nQty: 50\nFilled Qty: 50\n"
            "Status: FILLED"
        )

        index = PlanIndex()
        index.add(12346, "plan-001", "stop_loss")

        event = TransactionPayload(
            order_id="12346", symbol="AAPL", filled_quantity=50,
        )

        await handle_stop_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index,
        )

        # No cancel attempt
        mcp.cancel_order.assert_not_called()
        # Plan still closed
        mcp.close_trade_plan.assert_called_once_with(
            "plan-001", reason="stop_hit",
        )

    async def test_partial_stop_fill_does_not_close_plan(self) -> None:
        """Partial SL fill (25 of 50) keeps plan open, TP not cancelled."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(
            PLAN_WITH_ORDERS_XML,
        )
        # Order detail shows partial fill: 25 of 50
        mcp.get_order_detail.return_value = (
            "Order ID: 12346\nQty: 50\nFilled Qty: 25\n"
            "Status: PARTIALLY_FILLED"
        )

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")
        index.add(12346, "plan-001", "stop_loss")
        index.add(12347, "plan-001", "take_profit")

        event = TransactionPayload(
            order_id="12346", symbol="AAPL", filled_quantity=25,
        )

        await handle_stop_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index,
        )

        # TP should NOT be cancelled on partial fill
        mcp.cancel_order.assert_not_called()
        # Plan should NOT be closed
        mcp.close_trade_plan.assert_not_called()
        # Index should still have all entries
        assert index.lookup(12345) == ("plan-001", "entry")
        assert index.lookup(12346) == ("plan-001", "stop_loss")
        assert index.lookup(12347) == ("plan-001", "take_profit")


# ---------------------------------------------------------------------------
# Integration tests for handle_tp_fill
# ---------------------------------------------------------------------------


class TestHandleTpFill:
    """Tests for handle_tp_fill — take-profit fill triggers SL cancellation."""

    async def test_tp_fill_cancels_sl_and_closes_plan(self) -> None:
        """Take-profit fill cancels stop-loss order and closes plan as target_hit."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(PLAN_WITH_ORDERS_XML)
        mcp.get_order_detail.return_value = (
            "Order ID: 12347\nQty: 50\nFilled Qty: 50\n"
            "Status: FILLED"
        )

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")
        index.add(12346, "plan-001", "stop_loss")
        index.add(12347, "plan-001", "take_profit")

        event = TransactionPayload(
            order_id="12347", symbol="AAPL", filled_quantity=50,
        )

        await handle_tp_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index,
        )

        # SL order should be cancelled
        mcp.cancel_order.assert_called_once_with(12346)

        # Plan closed with reason "target_hit"
        mcp.close_trade_plan.assert_called_once_with(
            "plan-001", reason="target_hit",
        )

    async def test_cancel_failure_still_closes_plan(self) -> None:
        """If cancel_order fails, plan is still closed."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(PLAN_WITH_ORDERS_XML)
        mcp.get_order_detail.return_value = (
            "Order ID: 12347\nQty: 50\nFilled Qty: 50\n"
            "Status: FILLED"
        )
        mcp.cancel_order.side_effect = Exception("Order already cancelled")

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")
        index.add(12346, "plan-001", "stop_loss")
        index.add(12347, "plan-001", "take_profit")

        event = TransactionPayload(
            order_id="12347", symbol="AAPL", filled_quantity=50,
        )

        await handle_tp_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index,
        )

        mcp.close_trade_plan.assert_called_once_with(
            "plan-001", reason="target_hit",
        )

    async def test_removes_plan_from_index(self) -> None:
        """After TP fill, all plan entries removed from PlanIndex."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(PLAN_WITH_ORDERS_XML)
        mcp.get_order_detail.return_value = (
            "Order ID: 12347\nQty: 50\nFilled Qty: 50\n"
            "Status: FILLED"
        )

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")
        index.add(12346, "plan-001", "stop_loss")
        index.add(12347, "plan-001", "take_profit")

        event = TransactionPayload(
            order_id="12347", symbol="AAPL", filled_quantity=50,
        )

        await handle_tp_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index,
        )

        assert index.lookup(12345) is None
        assert index.lookup(12346) is None
        assert index.lookup(12347) is None

    async def test_no_counterpart_order_still_closes(self) -> None:
        """If SL order_id is non-numeric (PENDING), skip cancel but still close."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(
            PLAN_WITHOUT_SL_ORDER_XML
        )
        mcp.get_order_detail.return_value = (
            "Order ID: 12347\nQty: 50\nFilled Qty: 50\n"
            "Status: FILLED"
        )

        index = PlanIndex()
        index.add(12347, "plan-001", "take_profit")

        event = TransactionPayload(
            order_id="12347", symbol="AAPL", filled_quantity=50,
        )

        await handle_tp_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index,
        )

        # No cancel attempt
        mcp.cancel_order.assert_not_called()
        # Plan still closed
        mcp.close_trade_plan.assert_called_once_with(
            "plan-001", reason="target_hit",
        )

    async def test_partial_tp_fill_does_not_close_plan(self) -> None:
        """Partial TP fill (25 of 50) keeps plan open, SL not cancelled."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(
            PLAN_WITH_ORDERS_XML,
        )
        # Order detail shows partial fill: 25 of 50
        mcp.get_order_detail.return_value = (
            "Order ID: 12347\nQty: 50\nFilled Qty: 25\n"
            "Status: PARTIALLY_FILLED"
        )

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")
        index.add(12346, "plan-001", "stop_loss")
        index.add(12347, "plan-001", "take_profit")

        event = TransactionPayload(
            order_id="12347", symbol="AAPL", filled_quantity=25,
        )

        await handle_tp_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index,
        )

        # SL should NOT be cancelled on partial fill
        mcp.cancel_order.assert_not_called()
        # Plan should NOT be closed
        mcp.close_trade_plan.assert_not_called()
        # Index should still have all entries
        assert index.lookup(12345) == ("plan-001", "entry")
        assert index.lookup(12346) == ("plan-001", "stop_loss")
        assert index.lookup(12347) == ("plan-001", "take_profit")
