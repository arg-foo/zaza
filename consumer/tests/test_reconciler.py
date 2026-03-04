"""Tests for reconciler — startup reconciliation and RTH scan loop."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import orjson
import pytest

from zaza_consumer.config import ConsumerSettings
from zaza_consumer.plan_index import PlanIndex
from zaza_consumer.reconciler import reconcile_on_startup, rth_scan_loop

# ---------------------------------------------------------------------------
# Sample XML fixtures
# ---------------------------------------------------------------------------

# Plan where entry filled, protective orders PENDING (not yet placed)
PLAN_ENTRY_FILLED_NO_PROTECTIVES_XML = (
    '''<trade-plan ticker="AAPL" generated="2026-02-24">
  <summary><side>BUY</side><ticker>AAPL</ticker><quantity>50</quantity></summary>
  <entry>
    <strategy>support_bounce</strategy>
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
)

# Plan with all orders filled/placed: entry 12345, SL 12346, TP 12347
PLAN_ALL_ORDERS_XML = '''<trade-plan ticker="AAPL" generated="2026-02-24">
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

# Plan where entry is still a placeholder (not yet filled)
PLAN_ENTRY_PENDING_XML = '''<trade-plan ticker="TSLA" generated="2026-02-24">
  <summary><side>BUY</side><ticker>TSLA</ticker><quantity>10</quantity></summary>
  <entry>
    <strategy>breakout</strategy><trigger>Price breaks above $250</trigger>
    <limit-order>
      <order_id>BUY-TSLA-001</order_id><type>LIMIT</type><side>BUY</side><ticker>TSLA</ticker>
      <quantity>10</quantity><limit_price>250.00</limit_price><time_in_force>DAY</time_in_force>
    </limit-order>
  </entry>
  <exit>
    <stop-loss>
      <limit-order>
        <order_id>PENDING</order_id><type>STOP_LIMIT</type><side>SELL</side><ticker>TSLA</ticker>
        <quantity>10</quantity><limit_price>240.00</limit_price><time_in_force>DAY</time_in_force>
      </limit-order>
    </stop-loss>
    <take-profit>
      <limit-order>
        <order_id>PENDING</order_id><type>LIMIT</type><side>SELL</side><ticker>TSLA</ticker>
        <quantity>10</quantity><limit_price>270.00</limit_price><time_in_force>DAY</time_in_force>
      </limit-order>
    </take-profit>
  </exit>
</trade-plan>'''


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan_json(xml: str) -> str:
    """Wrap plan XML in the JSON structure returned by get_trade_plan."""
    return orjson.dumps({"plan_id": "plan-001", "xml": xml}).decode()


def _make_settings() -> ConsumerSettings:
    """Create a minimal ConsumerSettings for testing."""
    return ConsumerSettings(
        redis_url="redis://localhost:6379",
        tiger_mcp_url="http://localhost:8001/mcp",
        zaza_mcp_url="http://localhost:8002/mcp",
        rth_scan_interval_seconds=1,  # short for testing
        order_delay_ms=0,
    )


def _make_mcp_mock() -> AsyncMock:
    """Create a McpClients mock with sensible defaults."""
    mcp = AsyncMock()
    mcp.list_trade_plans.return_value = "[]"
    mcp.get_trade_plan.return_value = _make_plan_json(PLAN_ALL_ORDERS_XML)
    mcp.get_open_orders.return_value = "No open orders."
    mcp.get_filled_orders.return_value = "No filled orders."
    mcp.get_order_detail.return_value = "Filled Qty: 50\nAvg Price: 184.00"
    mcp.place_order.return_value = "Order ID: 99001\nStatus: SUBMITTED"
    mcp.cancel_order.return_value = "Order cancelled"
    mcp.close_trade_plan.return_value = "Plan archived"
    mcp.update_trade_plan.return_value = "Plan updated"
    return mcp


# ---------------------------------------------------------------------------
# Tests for reconcile_on_startup
# ---------------------------------------------------------------------------


class TestReconcileNoActivePlans:
    """No active plans -- rebuild with empty list, no errors."""

    async def test_no_plans_rebuilds_empty_index(self) -> None:
        mcp = _make_mcp_mock()
        mcp.list_trade_plans.return_value = "[]"
        index = PlanIndex()
        settings = _make_settings()
        await reconcile_on_startup(mcp, index, settings)
        assert len(index) == 0
        mcp.list_trade_plans.assert_called_once()

    async def test_no_plans_skips_order_checks(self) -> None:
        mcp = _make_mcp_mock()
        mcp.list_trade_plans.return_value = "[]"
        index = PlanIndex()
        settings = _make_settings()
        await reconcile_on_startup(mcp, index, settings)
        mcp.place_order.assert_not_called()
        mcp.cancel_order.assert_not_called()


class TestReconcileEntryFilledNoProtectives:
    """Plan with filled entry but PENDING protective orders."""

    async def test_places_protective_orders(self) -> None:
        mcp = _make_mcp_mock()
        plans_list = orjson.dumps([
            {"plan_id": "plan-001", "ticker": "AAPL", "side": "long",
             "status": "active", "created": "2026-01-01T00:00:00"}
        ]).decode()
        mcp.list_trade_plans.return_value = plans_list
        mcp.get_trade_plan.return_value = _make_plan_json(
            PLAN_ENTRY_FILLED_NO_PROTECTIVES_XML
        )
        mcp.get_filled_orders.return_value = (
            "Order ID: 12345\nSymbol: AAPL\nAction: BUY\n"
            "Filled Qty: 50\nAvg Price: 184.00"
        )
        mcp.get_open_orders.return_value = "No open orders."
        mcp.get_order_detail.return_value = (
            "Filled Qty: 50\nAvg Price: 184.00"
        )
        mcp.place_order.side_effect = [
            "Order ID: 99001\nStatus: SUBMITTED",
            "Order ID: 99002\nStatus: SUBMITTED",
        ]
        index = PlanIndex()
        settings = _make_settings()
        with patch(
            "zaza_consumer.reconciler.handle_entry_fill",
            new_callable=AsyncMock,
        ) as mock_fill:
            await reconcile_on_startup(mcp, index, settings)
            mock_fill.assert_called_once()
            call_args = mock_fill.call_args
            assert (
                call_args[1]["plan_id"] == "plan-001"
                or call_args[0][1] == "plan-001"
            )

    async def test_synthetic_event_has_filled_qty_from_broker(self) -> None:
        mcp = _make_mcp_mock()
        plans_list = orjson.dumps([
            {"plan_id": "plan-001", "ticker": "AAPL", "side": "long",
             "status": "active", "created": "2026-01-01T00:00:00"}
        ]).decode()
        mcp.list_trade_plans.return_value = plans_list
        mcp.get_trade_plan.return_value = _make_plan_json(
            PLAN_ENTRY_FILLED_NO_PROTECTIVES_XML
        )
        mcp.get_filled_orders.return_value = (
            "Order ID: 12345\nSymbol: AAPL\nAction: BUY\n"
            "Filled Qty: 50\nAvg Price: 184.00"
        )
        mcp.get_open_orders.return_value = "No open orders."
        mcp.get_order_detail.return_value = (
            "Order ID: 12345\nQty: 50\nFilled Qty: 50\n"
            "Avg Price: 184.00"
        )
        index = PlanIndex()
        settings = _make_settings()
        with patch(
            "zaza_consumer.reconciler.handle_entry_fill",
            new_callable=AsyncMock,
        ) as mock_fill:
            await reconcile_on_startup(mcp, index, settings)
            mock_fill.assert_called_once()
            call_kw = mock_fill.call_args[1]
            event = call_kw["event"]
            assert event["filledQuantity"] == 50


class TestReconcileStopFilled:
    """Plan where stop-loss filled but TP still open -- need OCO."""

    async def test_stop_filled_triggers_oco(self) -> None:
        mcp = _make_mcp_mock()
        plans_list = orjson.dumps([
            {"plan_id": "plan-001", "ticker": "AAPL", "side": "long",
             "status": "active", "created": "2026-01-01T00:00:00"}
        ]).decode()
        mcp.list_trade_plans.return_value = plans_list
        mcp.get_trade_plan.return_value = _make_plan_json(PLAN_ALL_ORDERS_XML)
        mcp.get_filled_orders.return_value = (
            "Order ID: 12346\nSymbol: AAPL\nAction: SELL\n"
            "Filled Qty: 50\nAvg Price: 179.50"
        )
        mcp.get_open_orders.return_value = (
            "Open Orders:\nOrder ID: 12347\nSymbol: AAPL\nAction: SELL\n"
            "Type: LMT\nLimit: 194.50\nQty: 50"
        )
        index = PlanIndex()
        settings = _make_settings()
        with patch(
            "zaza_consumer.reconciler.handle_stop_fill",
            new_callable=AsyncMock,
        ) as mock_stop:
            await reconcile_on_startup(mcp, index, settings)
            mock_stop.assert_called_once()
            call_args = mock_stop.call_args
            assert call_args[1]["plan_id"] == "plan-001" or call_args[0][1] == "plan-001"


class TestReconcileTpFilled:
    """Plan where take-profit filled but SL still open -- need OCO."""

    async def test_tp_filled_triggers_oco(self) -> None:
        mcp = _make_mcp_mock()
        plans_list = orjson.dumps([
            {"plan_id": "plan-001", "ticker": "AAPL", "side": "long",
             "status": "active", "created": "2026-01-01T00:00:00"}
        ]).decode()
        mcp.list_trade_plans.return_value = plans_list
        mcp.get_trade_plan.return_value = _make_plan_json(PLAN_ALL_ORDERS_XML)
        mcp.get_filled_orders.return_value = (
            "Order ID: 12347\nSymbol: AAPL\nAction: SELL\n"
            "Filled Qty: 50\nAvg Price: 194.50"
        )
        mcp.get_open_orders.return_value = (
            "Open Orders:\nOrder ID: 12346\nSymbol: AAPL\nAction: SELL\n"
            "Type: STP_LMT\nLimit: 179.50\nQty: 50"
        )
        index = PlanIndex()
        settings = _make_settings()
        with patch("zaza_consumer.reconciler.handle_tp_fill", new_callable=AsyncMock) as mock_tp:
            await reconcile_on_startup(mcp, index, settings)
            mock_tp.assert_called_once()
            call_args = mock_tp.call_args
            assert call_args[1]["plan_id"] == "plan-001" or call_args[0][1] == "plan-001"


class TestReconcileAllOrdersIntact:
    """Plan with all orders in expected state -- no reconciliation needed."""

    async def test_all_orders_intact_takes_no_action(self) -> None:
        mcp = _make_mcp_mock()
        plans_list = orjson.dumps([
            {"plan_id": "plan-001", "ticker": "AAPL", "side": "long",
             "status": "active", "created": "2026-01-01T00:00:00"}
        ]).decode()
        mcp.list_trade_plans.return_value = plans_list
        mcp.get_trade_plan.return_value = _make_plan_json(PLAN_ALL_ORDERS_XML)
        mcp.get_filled_orders.return_value = (
            "Order ID: 12345\nSymbol: AAPL\nAction: BUY\n"
            "Filled Qty: 50\nAvg Price: 184.00"
        )
        mcp.get_open_orders.return_value = (
            "Open Orders:\n"
            "Order ID: 12346\nSymbol: AAPL\nAction: SELL\nType: STP_LMT\n"
            "Order ID: 12347\nSymbol: AAPL\nAction: SELL\nType: LMT"
        )
        index = PlanIndex()
        settings = _make_settings()
        await reconcile_on_startup(mcp, index, settings)
        mcp.place_order.assert_not_called()
        mcp.cancel_order.assert_not_called()
        mcp.close_trade_plan.assert_not_called()

    async def test_entry_not_filled_takes_no_action(self) -> None:
        mcp = _make_mcp_mock()
        plans_list = orjson.dumps([
            {"plan_id": "plan-002", "ticker": "TSLA", "side": "long",
             "status": "active", "created": "2026-01-01T00:00:00"}
        ]).decode()
        mcp.list_trade_plans.return_value = plans_list
        mcp.get_trade_plan.return_value = orjson.dumps({
            "plan_id": "plan-002", "xml": PLAN_ENTRY_PENDING_XML
        }).decode()
        mcp.get_filled_orders.return_value = "No filled orders."
        mcp.get_open_orders.return_value = "No open orders."
        index = PlanIndex()
        settings = _make_settings()
        await reconcile_on_startup(mcp, index, settings)
        mcp.place_order.assert_not_called()
        mcp.cancel_order.assert_not_called()


class TestReconcileExpiredProtectives:
    """Plan with expired protective orders during RTH."""

    async def test_expired_protectives_during_rth_replaces_them(self) -> None:
        mcp = _make_mcp_mock()
        plans_list = orjson.dumps([
            {"plan_id": "plan-001", "ticker": "AAPL", "side": "long",
             "status": "active", "created": "2026-01-01T00:00:00"}
        ]).decode()
        mcp.list_trade_plans.return_value = plans_list
        mcp.get_trade_plan.return_value = _make_plan_json(PLAN_ALL_ORDERS_XML)
        mcp.get_filled_orders.return_value = (
            "Order ID: 12345\nSymbol: AAPL\nAction: BUY\n"
            "Filled Qty: 50\nAvg Price: 184.00"
        )
        mcp.get_open_orders.return_value = "No open orders."
        mcp.get_order_detail.return_value = (
            "Filled Qty: 50\nAvg Price: 184.00"
        )
        index = PlanIndex()
        settings = _make_settings()
        with (
            patch("zaza_consumer.reconciler.is_rth_open", return_value=True),
            patch(
                "zaza_consumer.reconciler.handle_entry_fill",
                new_callable=AsyncMock,
            ) as mock_fill,
        ):
            await reconcile_on_startup(mcp, index, settings)
            mock_fill.assert_called_once()

    async def test_is_rth_open_receives_settings_values(self) -> None:
        mcp = _make_mcp_mock()
        plans_list = orjson.dumps([
            {"plan_id": "plan-001", "ticker": "AAPL", "side": "long",
             "status": "active", "created": "2026-01-01T00:00:00"}
        ]).decode()
        mcp.list_trade_plans.return_value = plans_list
        mcp.get_trade_plan.return_value = _make_plan_json(PLAN_ALL_ORDERS_XML)
        mcp.get_filled_orders.return_value = (
            "Order ID: 12345\nSymbol: AAPL\nAction: BUY\n"
            "Filled Qty: 50\nAvg Price: 184.00"
        )
        mcp.get_open_orders.return_value = "No open orders."
        mcp.get_order_detail.return_value = (
            "Filled Qty: 50\nAvg Price: 184.00"
        )
        index = PlanIndex()
        settings = ConsumerSettings(
            redis_url="redis://localhost:6379",
            tiger_mcp_url="http://localhost:8001/mcp",
            zaza_mcp_url="http://localhost:8002/mcp",
            rth_open_hour=10, rth_open_minute=15,
            rth_close_hour=15, rth_close_minute=45,
            rth_scan_interval_seconds=1, order_delay_ms=0,
        )
        with (
            patch("zaza_consumer.reconciler.is_rth_open", return_value=True) as mock_rth,
            patch("zaza_consumer.reconciler.handle_entry_fill", new_callable=AsyncMock),
        ):
            await reconcile_on_startup(mcp, index, settings)
            mock_rth.assert_called_with(
                rth_open_hour=10, rth_open_minute=15,
                rth_close_hour=15, rth_close_minute=45,
            )


class TestReconcileIndexRebuilt:
    """Verify the plan index is correctly rebuilt during reconciliation."""

    async def test_index_rebuilt_with_plan_orders(self) -> None:
        mcp = _make_mcp_mock()
        plans_list = orjson.dumps([
            {"plan_id": "plan-001", "ticker": "AAPL", "side": "long",
             "status": "active", "created": "2026-01-01T00:00:00"}
        ]).decode()
        mcp.list_trade_plans.return_value = plans_list
        mcp.get_trade_plan.return_value = _make_plan_json(PLAN_ALL_ORDERS_XML)
        mcp.get_filled_orders.return_value = (
            "Order ID: 12345\nSymbol: AAPL\nAction: BUY\n"
            "Filled Qty: 50\nAvg Price: 184.00"
        )
        mcp.get_open_orders.return_value = (
            "Open Orders:\n"
            "Order ID: 12346\nSymbol: AAPL\nAction: SELL\nType: STP_LMT\n"
            "Order ID: 12347\nSymbol: AAPL\nAction: SELL\nType: LMT"
        )
        index = PlanIndex()
        settings = _make_settings()
        await reconcile_on_startup(mcp, index, settings)
        assert index.lookup(12345) == ("plan-001", "entry")
        assert index.lookup(12346) == ("plan-001", "stop_loss")
        assert index.lookup(12347) == ("plan-001", "take_profit")

    async def test_multiple_plans_all_indexed(self) -> None:
        mcp = _make_mcp_mock()
        plans_list = orjson.dumps([
            {"plan_id": "plan-001", "ticker": "AAPL", "side": "long",
             "status": "active", "created": "2026-01-01T00:00:00"},
            {"plan_id": "plan-002", "ticker": "TSLA", "side": "long",
             "status": "active", "created": "2026-01-02T00:00:00"},
        ]).decode()
        mcp.list_trade_plans.return_value = plans_list
        tsla_xml = '''<trade-plan ticker="TSLA" generated="2026-02-24">
  <summary><side>BUY</side><ticker>TSLA</ticker><quantity>10</quantity></summary>
  <entry>
    <limit-order>
      <order_id>22345</order_id><type>LIMIT</type><side>BUY</side><ticker>TSLA</ticker>
      <quantity>10</quantity><limit_price>250.00</limit_price><time_in_force>DAY</time_in_force>
    </limit-order>
  </entry>
  <exit>
    <stop-loss>
      <limit-order>
        <order_id>22346</order_id><type>STOP_LIMIT</type><side>SELL</side><ticker>TSLA</ticker>
        <quantity>10</quantity><limit_price>240.00</limit_price><time_in_force>DAY</time_in_force>
      </limit-order>
    </stop-loss>
    <take-profit>
      <limit-order>
        <order_id>22347</order_id><type>LIMIT</type><side>SELL</side><ticker>TSLA</ticker>
        <quantity>10</quantity><limit_price>270.00</limit_price><time_in_force>DAY</time_in_force>
      </limit-order>
    </take-profit>
  </exit>
</trade-plan>'''

        def _get_plan(plan_id: str) -> str:
            if plan_id == "plan-001":
                return _make_plan_json(PLAN_ALL_ORDERS_XML)
            return orjson.dumps({"plan_id": "plan-002", "xml": tsla_xml}).decode()

        mcp.get_trade_plan.side_effect = _get_plan
        mcp.get_filled_orders.return_value = (
            "Order ID: 12345\nSymbol: AAPL\nFilled Qty: 50\n"
            "Order ID: 22345\nSymbol: TSLA\nFilled Qty: 10"
        )
        mcp.get_open_orders.return_value = (
            "Open Orders:\n"
            "Order ID: 12346\nOrder ID: 12347\n"
            "Order ID: 22346\nOrder ID: 22347"
        )
        index = PlanIndex()
        settings = _make_settings()
        await reconcile_on_startup(mcp, index, settings)
        assert index.lookup(12345) == ("plan-001", "entry")
        assert index.lookup(22345) == ("plan-002", "entry")
        assert len(index) == 6


# ---------------------------------------------------------------------------
# Tests for rth_scan_loop
# ---------------------------------------------------------------------------


class TestRthScanLoop:
    """Tests for the RTH scan loop background task."""

    async def test_sleeps_and_checks_rth(self) -> None:
        mcp = _make_mcp_mock()
        index = PlanIndex()
        settings = _make_settings()
        iteration_count = 0
        with patch("zaza_consumer.reconciler.is_rth_open") as mock_rth:
            mock_rth.return_value = False
            original_sleep = asyncio.sleep

            async def _counting_sleep(duration: float) -> None:
                nonlocal iteration_count
                iteration_count += 1
                if iteration_count >= 2:
                    raise asyncio.CancelledError
                await original_sleep(0.01)

            with patch("asyncio.sleep", side_effect=_counting_sleep):
                with pytest.raises(asyncio.CancelledError):
                    await rth_scan_loop(mcp, index, settings)
            assert mock_rth.call_count >= 1

    async def test_scans_when_rth_open(self) -> None:
        mcp = _make_mcp_mock()
        plans_list = orjson.dumps([
            {"plan_id": "plan-001", "ticker": "AAPL", "side": "long",
             "status": "active", "created": "2026-01-01T00:00:00"}
        ]).decode()
        mcp.list_trade_plans.return_value = plans_list
        mcp.get_trade_plan.return_value = _make_plan_json(PLAN_ALL_ORDERS_XML)
        mcp.get_open_orders.return_value = (
            "Open Orders:\nOrder ID: 12346\nOrder ID: 12347"
        )
        index = PlanIndex()
        index.add(12345, "plan-001", "entry")
        index.add(12346, "plan-001", "stop_loss")
        index.add(12347, "plan-001", "take_profit")
        settings = _make_settings()
        iteration_count = 0
        with patch("zaza_consumer.reconciler.is_rth_open", return_value=True):
            original_sleep = asyncio.sleep

            async def _counting_sleep(duration: float) -> None:
                nonlocal iteration_count
                iteration_count += 1
                if iteration_count >= 2:
                    raise asyncio.CancelledError
                await original_sleep(0.01)

            with patch("asyncio.sleep", side_effect=_counting_sleep):
                with pytest.raises(asyncio.CancelledError):
                    await rth_scan_loop(mcp, index, settings)
            assert mcp.list_trade_plans.call_count >= 1

    async def test_skips_scan_when_rth_closed(self) -> None:
        mcp = _make_mcp_mock()
        index = PlanIndex()
        settings = _make_settings()
        iteration_count = 0
        with patch("zaza_consumer.reconciler.is_rth_open", return_value=False):
            original_sleep = asyncio.sleep

            async def _counting_sleep(duration: float) -> None:
                nonlocal iteration_count
                iteration_count += 1
                if iteration_count >= 2:
                    raise asyncio.CancelledError
                await original_sleep(0.01)

            with patch("asyncio.sleep", side_effect=_counting_sleep):
                with pytest.raises(asyncio.CancelledError):
                    await rth_scan_loop(mcp, index, settings)
            mcp.list_trade_plans.assert_not_called()

    async def test_rth_scan_passes_settings_to_is_rth_open(self) -> None:
        mcp = _make_mcp_mock()
        index = PlanIndex()
        settings = ConsumerSettings(
            redis_url="redis://localhost:6379",
            tiger_mcp_url="http://localhost:8001/mcp",
            zaza_mcp_url="http://localhost:8002/mcp",
            rth_open_hour=10, rth_open_minute=15,
            rth_close_hour=15, rth_close_minute=45,
            rth_scan_interval_seconds=1, order_delay_ms=0,
        )
        iteration_count = 0
        with patch("zaza_consumer.reconciler.is_rth_open", return_value=False) as mock_rth:
            original_sleep = asyncio.sleep

            async def _counting_sleep(duration: float) -> None:
                nonlocal iteration_count
                iteration_count += 1
                if iteration_count >= 2:
                    raise asyncio.CancelledError
                await original_sleep(0.01)

            with patch("asyncio.sleep", side_effect=_counting_sleep):
                with pytest.raises(asyncio.CancelledError):
                    await rth_scan_loop(mcp, index, settings)
            mock_rth.assert_called_with(
                rth_open_hour=10, rth_open_minute=15,
                rth_close_hour=15, rth_close_minute=45,
            )

    async def test_scan_replaces_expired_protective_orders(self) -> None:
        mcp = _make_mcp_mock()
        plans_list = orjson.dumps([
            {"plan_id": "plan-001", "ticker": "AAPL", "side": "long",
             "status": "active", "created": "2026-01-01T00:00:00"}
        ]).decode()
        mcp.list_trade_plans.return_value = plans_list
        mcp.get_trade_plan.return_value = _make_plan_json(PLAN_ALL_ORDERS_XML)
        mcp.get_open_orders.return_value = "No open orders."
        mcp.get_filled_orders.return_value = (
            "Order ID: 12345\nSymbol: AAPL\nFilled Qty: 50"
        )
        mcp.get_order_detail.return_value = "Filled Qty: 50\nAvg Price: 184.00"
        index = PlanIndex()
        index.add(12345, "plan-001", "entry")
        index.add(12346, "plan-001", "stop_loss")
        index.add(12347, "plan-001", "take_profit")
        settings = _make_settings()
        iteration_count = 0
        with (
            patch("zaza_consumer.reconciler.is_rth_open", return_value=True),
            patch(
                "zaza_consumer.reconciler.handle_entry_fill",
                new_callable=AsyncMock,
            ) as mock_fill,
        ):
            original_sleep = asyncio.sleep

            async def _counting_sleep(duration: float) -> None:
                nonlocal iteration_count
                iteration_count += 1
                if iteration_count >= 2:
                    raise asyncio.CancelledError
                await original_sleep(0.01)

            with patch("asyncio.sleep", side_effect=_counting_sleep):
                with pytest.raises(asyncio.CancelledError):
                    await rth_scan_loop(mcp, index, settings)
            assert mock_fill.call_count >= 1
