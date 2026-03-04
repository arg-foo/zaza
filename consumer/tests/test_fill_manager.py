"""Tests for fill_manager — pro-rata protective order placement and modification."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock

import orjson
import pytest

from zaza_consumer.fill_manager import (
    _extract_order_id_from_result,
    _get_order_id,
    _is_numeric_order_id,
    _parse_exit_params,
    _parse_filled_quantity,
    _update_order_id_in_xml,
    _update_quantity_in_xml,
    handle_entry_fill,
)
from zaza_consumer.models import TransactionPayload
from zaza_consumer.plan_index import PlanIndex

# ---------------------------------------------------------------------------
# Sample XML fixtures
# ---------------------------------------------------------------------------

SAMPLE_PLAN_XML = '''<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC">
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
        <order_id>PENDING</order_id><type>LIMIT</type><side>SELL</side><ticker>AAPL</ticker>
        <quantity>50</quantity><limit_price>194.50</limit_price><time_in_force>DAY</time_in_force>
      </limit-order>
    </take-profit>
  </exit>
</trade-plan>'''

PLAN_WITH_EXISTING_ORDERS_XML = '''<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC">
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
        <quantity>30</quantity><limit_price>179.50</limit_price><time_in_force>DAY</time_in_force>
      </limit-order>
    </stop-loss>
    <take-profit>
      <limit-order>
        <order_id>12347</order_id><type>LIMIT</type><side>SELL</side><ticker>AAPL</ticker>
        <quantity>30</quantity><limit_price>194.50</limit_price><time_in_force>DAY</time_in_force>
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
    mcp.get_order_detail.return_value = "Filled Qty: 50\nAvg Price: 184.00"
    mcp.place_order.return_value = "Order ID: 99001\nStatus: FILLED"
    mcp.modify_order.return_value = "Order 12346 modified"
    mcp.update_trade_plan.return_value = "Plan updated"
    return mcp


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestParseExitParams:
    """Tests for _parse_exit_params."""

    def test_parses_stop_loss_and_take_profit(self) -> None:
        """Both SL and TP parameters extracted from well-formed XML."""
        params = _parse_exit_params(SAMPLE_PLAN_XML)

        assert params["sl_ticker"] == "AAPL"
        assert params["sl_limit_price"] == 179.50
        assert params["sl_stop_price"] == 179.50  # falls back to limit_price
        assert params["tp_ticker"] == "AAPL"
        assert params["tp_limit_price"] == 194.50

    def test_missing_exit_element_raises(self) -> None:
        """XML without <exit> raises ValueError."""
        xml = "<trade-plan><entry></entry></trade-plan>"
        with pytest.raises(ValueError, match="missing <exit> element"):
            _parse_exit_params(xml)

    def test_explicit_stop_price(self) -> None:
        """When <stop_price> is present, it is used instead of limit_price."""
        xml = '''<trade-plan>
          <exit>
            <stop-loss>
              <limit-order>
                <ticker>AAPL</ticker>
                <limit_price>179.50</limit_price>
                <stop_price>180.00</stop_price>
              </limit-order>
            </stop-loss>
          </exit>
        </trade-plan>'''
        params = _parse_exit_params(xml)
        assert params["sl_stop_price"] == 180.00
        assert params["sl_limit_price"] == 179.50


class TestGetOrderId:
    """Tests for _get_order_id."""

    def test_returns_numeric_order_id(self) -> None:
        oid = _get_order_id(SAMPLE_PLAN_XML, "entry/limit-order/order_id")
        assert oid == "12345"

    def test_returns_pending_placeholder(self) -> None:
        oid = _get_order_id(SAMPLE_PLAN_XML, "exit/stop-loss/limit-order/order_id")
        assert oid == "PENDING"

    def test_returns_none_for_missing_path(self) -> None:
        oid = _get_order_id(SAMPLE_PLAN_XML, "exit/nonexistent/order_id")
        assert oid is None


class TestIsNumericOrderId:
    """Tests for _is_numeric_order_id."""

    def test_numeric_string(self) -> None:
        assert _is_numeric_order_id("12345") is True

    def test_pending_string(self) -> None:
        assert _is_numeric_order_id("PENDING") is False

    def test_none(self) -> None:
        assert _is_numeric_order_id(None) is False

    def test_empty_string(self) -> None:
        assert _is_numeric_order_id("") is False


class TestUpdateOrderIdInXml:
    """Tests for _update_order_id_in_xml."""

    def test_updates_order_id(self) -> None:
        updated = _update_order_id_in_xml(
            SAMPLE_PLAN_XML, "exit/stop-loss/limit-order/order_id", "99999"
        )
        root = ET.fromstring(updated)
        elem = root.find("exit/stop-loss/limit-order/order_id")
        assert elem is not None
        assert elem.text == "99999"

    def test_other_fields_unchanged(self) -> None:
        updated = _update_order_id_in_xml(
            SAMPLE_PLAN_XML, "exit/stop-loss/limit-order/order_id", "99999"
        )
        root = ET.fromstring(updated)
        # Entry order_id should remain unchanged
        entry_id = root.find("entry/limit-order/order_id")
        assert entry_id is not None
        assert entry_id.text == "12345"


class TestUpdateQuantityInXml:
    """Tests for _update_quantity_in_xml."""

    def test_updates_quantity(self) -> None:
        updated = _update_quantity_in_xml(
            SAMPLE_PLAN_XML, "exit/stop-loss/limit-order/quantity", "25"
        )
        root = ET.fromstring(updated)
        elem = root.find("exit/stop-loss/limit-order/quantity")
        assert elem is not None
        assert elem.text == "25"


class TestParseFilledQuantity:
    """Tests for _parse_filled_quantity."""

    def test_from_order_detail_text(self) -> None:
        detail = "Order 12345\nFilled Qty: 50\nAvg Price: 184.00"
        qty = _parse_filled_quantity(
            detail, TransactionPayload(filled_quantity=0),
        )
        assert qty == 50

    def test_from_event_fallback(self) -> None:
        detail = "Order 12345 details with no quantity info"
        qty = _parse_filled_quantity(
            detail, TransactionPayload(filled_quantity=30),
        )
        assert qty == 30

    def test_zero_when_no_data(self) -> None:
        detail = "No quantity info here"
        qty = _parse_filled_quantity(detail, TransactionPayload())
        assert qty == 0

    def test_case_insensitive_parsing(self) -> None:
        detail = "filled quantity: 42"
        qty = _parse_filled_quantity(detail, TransactionPayload())
        assert qty == 42


class TestExtractOrderIdFromResult:
    """Tests for _extract_order_id_from_result."""

    def test_extracts_order_id(self) -> None:
        result = "Order ID: 99001\nStatus: FILLED"
        assert _extract_order_id_from_result(result) == "99001"

    def test_returns_none_when_missing(self) -> None:
        result = "Error: Order could not be placed"
        assert _extract_order_id_from_result(result) is None

    def test_extracts_order_id_alternative_format(self) -> None:
        result = "order_id: 55555"
        assert _extract_order_id_from_result(result) == "55555"


# ---------------------------------------------------------------------------
# Integration tests for handle_entry_fill
# ---------------------------------------------------------------------------


class TestHandleEntryFillFirstFill:
    """First entry fill: places both protective orders (STP_LMT + LMT)."""

    async def test_first_fill_places_both_protective_orders(self) -> None:
        """Entry fill with PENDING protective orders places STP_LMT and LMT."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(SAMPLE_PLAN_XML)

        # Set up distinct order IDs for SL and TP
        mcp.place_order.side_effect = [
            "Order ID: 99001\nStatus: SUBMITTED",  # stop-loss
            "Order ID: 99002\nStatus: SUBMITTED",  # take-profit
        ]

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")

        event = TransactionPayload(
            order_id="12345", symbol="AAPL", filled_quantity=50,
        )

        await handle_entry_fill(
            event=event,
            plan_id="plan-001",
            mcp=mcp,
            index=index,
            order_delay_ms=0,
        )

        # Verify two place_order calls
        assert mcp.place_order.call_count == 2

        # First call: stop-loss STP_LMT
        sl_call = mcp.place_order.call_args_list[0]
        assert sl_call.kwargs["symbol"] == "AAPL"
        assert sl_call.kwargs["action"] == "SELL"
        assert sl_call.kwargs["quantity"] == 50
        assert sl_call.kwargs["order_type"] == "STP_LMT"
        assert sl_call.kwargs["limit_price"] == 179.50
        assert sl_call.kwargs["stop_price"] == 179.50

        # Second call: take-profit LMT
        tp_call = mcp.place_order.call_args_list[1]
        assert tp_call.kwargs["symbol"] == "AAPL"
        assert tp_call.kwargs["action"] == "SELL"
        assert tp_call.kwargs["quantity"] == 50
        assert tp_call.kwargs["order_type"] == "LMT"
        assert tp_call.kwargs["limit_price"] == 194.50

    async def test_plan_xml_updated_with_order_ids(self) -> None:
        """After placing protective orders, plan XML is updated with new IDs."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(SAMPLE_PLAN_XML)
        mcp.place_order.side_effect = [
            "Order ID: 99001\nStatus: SUBMITTED",
            "Order ID: 99002\nStatus: SUBMITTED",
        ]

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")

        event = TransactionPayload(
            order_id="12345", symbol="AAPL", filled_quantity=50,
        )

        await handle_entry_fill(
            event=event,
            plan_id="plan-001",
            mcp=mcp,
            index=index,
            order_delay_ms=0,
        )

        # Verify update_trade_plan was called
        mcp.update_trade_plan.assert_called_once()
        call_args = mcp.update_trade_plan.call_args
        updated_xml = call_args.args[1] if call_args.args else call_args.kwargs["xml"]

        # Parse updated XML and verify order IDs
        root = ET.fromstring(updated_xml)
        sl_id = root.find("exit/stop-loss/limit-order/order_id")
        tp_id = root.find("exit/take-profit/limit-order/order_id")
        assert sl_id is not None and sl_id.text == "99001"
        assert tp_id is not None and tp_id.text == "99002"

    async def test_index_updated_with_new_order_ids(self) -> None:
        """After placing protective orders, PlanIndex has new entries."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(SAMPLE_PLAN_XML)
        mcp.place_order.side_effect = [
            "Order ID: 99001\nStatus: SUBMITTED",
            "Order ID: 99002\nStatus: SUBMITTED",
        ]

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")

        event = TransactionPayload(
            order_id="12345", symbol="AAPL", filled_quantity=50,
        )

        await handle_entry_fill(
            event=event,
            plan_id="plan-001",
            mcp=mcp,
            index=index,
            order_delay_ms=0,
        )

        assert index.lookup(99001) == ("plan-001", "stop_loss")
        assert index.lookup(99002) == ("plan-001", "take_profit")


class TestHandleEntryFillSubsequent:
    """Subsequent fill: modifies existing protective orders."""

    async def test_subsequent_fill_modifies_protective_orders(self) -> None:
        """When protective orders already exist with numeric IDs, modify quantity."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(
            PLAN_WITH_EXISTING_ORDERS_XML
        )

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")
        index.add(12346, "plan-001", "stop_loss")
        index.add(12347, "plan-001", "take_profit")

        event = TransactionPayload(
            order_id="12345", symbol="AAPL", filled_quantity=50,
        )

        await handle_entry_fill(
            event=event,
            plan_id="plan-001",
            mcp=mcp,
            index=index,
            order_delay_ms=0,
        )

        # No place_order calls -- only modify
        mcp.place_order.assert_not_called()

        # Two modify_order calls (SL + TP)
        assert mcp.modify_order.call_count == 2

        sl_modify = mcp.modify_order.call_args_list[0]
        assert sl_modify.kwargs["order_id"] == 12346
        assert sl_modify.kwargs["quantity"] == 50

        tp_modify = mcp.modify_order.call_args_list[1]
        assert tp_modify.kwargs["order_id"] == 12347
        assert tp_modify.kwargs["quantity"] == 50

    async def test_idempotent_no_duplicate_orders(self) -> None:
        """Re-processing same fill with existing orders modifies, does not create new."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(
            PLAN_WITH_EXISTING_ORDERS_XML
        )

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")
        index.add(12346, "plan-001", "stop_loss")
        index.add(12347, "plan-001", "take_profit")

        event = TransactionPayload(
            order_id="12345", symbol="AAPL", filled_quantity=50,
        )

        # Process the same fill twice
        await handle_entry_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index, order_delay_ms=0,
        )
        await handle_entry_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index, order_delay_ms=0,
        )

        # Should never call place_order -- always modify
        mcp.place_order.assert_not_called()
        # 4 modify calls total (2 per fill x 2 fills)
        assert mcp.modify_order.call_count == 4


PLAN_MISSING_SL_ELEMENT_XML = '''<trade-plan ticker="AAPL">
  <summary><side>BUY</side><ticker>AAPL</ticker><quantity>50</quantity></summary>
  <entry>
    <strategy>support_bounce</strategy>
    <limit-order>
      <order_id>12345</order_id><type>LIMIT</type><side>BUY</side>
      <ticker>AAPL</ticker><quantity>50</quantity>
      <limit_price>184.00</limit_price><time_in_force>DAY</time_in_force>
    </limit-order>
  </entry>
  <exit>
    <take-profit>
      <limit-order>
        <order_id>PENDING</order_id><type>LIMIT</type><side>SELL</side>
        <ticker>AAPL</ticker><quantity>50</quantity>
        <limit_price>194.50</limit_price><time_in_force>DAY</time_in_force>
      </limit-order>
    </take-profit>
  </exit>
</trade-plan>'''

PLAN_MISSING_TP_ELEMENT_XML = '''<trade-plan ticker="AAPL">
  <summary><side>BUY</side><ticker>AAPL</ticker><quantity>50</quantity></summary>
  <entry>
    <strategy>support_bounce</strategy>
    <limit-order>
      <order_id>12345</order_id><type>LIMIT</type><side>BUY</side>
      <ticker>AAPL</ticker><quantity>50</quantity>
      <limit_price>184.00</limit_price><time_in_force>DAY</time_in_force>
    </limit-order>
  </entry>
  <exit>
    <stop-loss>
      <limit-order>
        <order_id>PENDING</order_id><type>STOP_LIMIT</type><side>SELL</side>
        <ticker>AAPL</ticker><quantity>50</quantity>
        <limit_price>179.50</limit_price><time_in_force>DAY</time_in_force>
      </limit-order>
    </stop-loss>
  </exit>
</trade-plan>'''


class TestHandleEntryFillMissingExitParams:
    """Tests for missing stop-loss or take-profit XML elements."""

    async def test_missing_stop_loss_element_returns_early(self) -> None:
        """Plan without <stop-loss> logs error and returns."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(
            PLAN_MISSING_SL_ELEMENT_XML,
        )

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")

        event = TransactionPayload(
            order_id="12345", symbol="AAPL", filled_quantity=50,
        )

        await handle_entry_fill(
            event=event,
            plan_id="plan-001",
            mcp=mcp,
            index=index,
            order_delay_ms=0,
        )

        # Should NOT place any orders
        mcp.place_order.assert_not_called()
        mcp.modify_order.assert_not_called()
        mcp.update_trade_plan.assert_not_called()

    async def test_missing_take_profit_element_returns_early(self) -> None:
        """Plan without <take-profit> logs error and returns."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(
            PLAN_MISSING_TP_ELEMENT_XML,
        )

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")

        event = TransactionPayload(
            order_id="12345", symbol="AAPL", filled_quantity=50,
        )

        await handle_entry_fill(
            event=event,
            plan_id="plan-001",
            mcp=mcp,
            index=index,
            order_delay_ms=0,
        )

        # Should NOT place any orders
        mcp.place_order.assert_not_called()
        mcp.modify_order.assert_not_called()
        mcp.update_trade_plan.assert_not_called()


class TestHandleEntryFillPartialFailure:
    """Tests for partial failure during protective order placement."""

    async def test_tp_failure_still_persists_sl_order_id(self) -> None:
        """If TP placement fails, SL order ID is still persisted."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(SAMPLE_PLAN_XML)
        mcp.place_order.side_effect = [
            "Order ID: 99001\nStatus: SUBMITTED",  # SL succeeds
            RuntimeError("TP placement failed"),     # TP fails
        ]

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")

        event = TransactionPayload(
            order_id="12345", symbol="AAPL", filled_quantity=50,
        )

        with pytest.raises(RuntimeError, match="TP placement failed"):
            await handle_entry_fill(
                event=event,
                plan_id="plan-001",
                mcp=mcp,
                index=index,
                order_delay_ms=0,
            )

        # update_trade_plan MUST have been called to persist SL order ID
        mcp.update_trade_plan.assert_called_once()
        call_args = mcp.update_trade_plan.call_args
        updated_xml = (
            call_args.args[1]
            if call_args.args
            else call_args.kwargs["xml"]
        )

        # Verify SL order ID is persisted in the XML
        root = ET.fromstring(updated_xml)
        sl_id = root.find("exit/stop-loss/limit-order/order_id")
        assert sl_id is not None
        assert sl_id.text == "99001"


class TestHandleEntryFillEdgeCases:
    """Edge cases for handle_entry_fill."""

    async def test_zero_filled_quantity_skipped(self) -> None:
        """filledQuantity=0 results in no orders placed or modified."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(SAMPLE_PLAN_XML)
        mcp.get_order_detail.return_value = "Filled Qty: 0\nStatus: CANCELLED"

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")

        event = TransactionPayload(
            order_id="12345", symbol="AAPL", filled_quantity=0,
        )

        await handle_entry_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index, order_delay_ms=0,
        )

        mcp.place_order.assert_not_called()
        mcp.modify_order.assert_not_called()
        mcp.update_trade_plan.assert_not_called()

    async def test_empty_plan_xml_returns_early(self) -> None:
        """Empty plan XML returns early without placing orders."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = orjson.dumps({"xml": ""}).decode()

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")

        event = TransactionPayload(
            order_id="12345", symbol="AAPL", filled_quantity=50,
        )

        await handle_entry_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index, order_delay_ms=0,
        )

        mcp.place_order.assert_not_called()
        mcp.modify_order.assert_not_called()

    async def test_quantities_updated_in_plan_xml(self) -> None:
        """The protective order quantities in the XML match the filled quantity."""
        mcp = _make_mcp_mock()
        mcp.get_trade_plan.return_value = _make_plan_json(SAMPLE_PLAN_XML)
        mcp.get_order_detail.return_value = "Filled Qty: 25\nAvg Price: 184.00"
        mcp.place_order.side_effect = [
            "Order ID: 99001\nStatus: SUBMITTED",
            "Order ID: 99002\nStatus: SUBMITTED",
        ]

        index = PlanIndex()
        index.add(12345, "plan-001", "entry")

        event = TransactionPayload(
            order_id="12345", symbol="AAPL", filled_quantity=25,
        )

        await handle_entry_fill(
            event=event, plan_id="plan-001", mcp=mcp, index=index, order_delay_ms=0,
        )

        # Verify quantities in the updated XML
        call_args = mcp.update_trade_plan.call_args
        updated_xml = call_args.args[1] if call_args.args else call_args.kwargs["xml"]
        root = ET.fromstring(updated_xml)

        sl_qty = root.find("exit/stop-loss/limit-order/quantity")
        tp_qty = root.find("exit/take-profit/limit-order/quantity")
        assert sl_qty is not None and sl_qty.text == "25"
        assert tp_qty is not None and tp_qty.text == "25"
