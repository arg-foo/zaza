"""Tests for order_sync.planner — pure order intent computation logic."""

from __future__ import annotations

import pytest

from order_sync.parsers import TradePlan
from order_sync.planner import OrderIntent, compute_order_intents


def _make_plan(
    *,
    plan_id: str = "plan-1",
    ticker: str = "AAPL",
    side: str = "BUY",
    quantity: int = 50,
    order_id: str = "BUY-AAPL-001",
    entry_status: str = "PENDING",
    entry_limit_price: float = 184.00,
    sl_stop_price: float = 180.00,
    sl_limit_price: float = 179.50,
    tp_limit_price: float = 194.50,
) -> TradePlan:
    return TradePlan(
        plan_id=plan_id,
        ticker=ticker,
        side=side,
        quantity=quantity,
        order_id=order_id,
        entry_status=entry_status,
        entry_limit_price=entry_limit_price,
        sl_stop_price=sl_stop_price,
        sl_limit_price=sl_limit_price,
        tp_limit_price=tp_limit_price,
    )


class TestComputeOrderIntents:
    """Tests for compute_order_intents classification logic."""

    def test_pending_no_orders_no_position_yields_bracket(self) -> None:
        """PENDING entry, no position, no orders -> BRACKET."""
        plan = _make_plan(entry_status="PENDING")
        intents = compute_order_intents([plan], positions=[], open_orders=[])

        assert len(intents) == 1
        intent = intents[0]
        assert intent.action == "BRACKET"
        assert intent.plan_id == "plan-1"
        assert intent.ticker == "AAPL"
        assert intent.entry_limit_price == 184.00
        assert intent.quantity == 50
        assert "no existing BUY order" in intent.reason

    def test_pending_with_existing_buy_order_yields_skip(self) -> None:
        """PENDING entry with existing BUY order -> SKIP."""
        plan = _make_plan(entry_status="PENDING")
        buy_order = {
            "order_id": "99999",
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 50,
        }
        intents = compute_order_intents([plan], positions=[], open_orders=[buy_order])

        assert len(intents) == 1
        assert intents[0].action == "SKIP"
        assert "Existing BUY order" in intents[0].reason

    def test_completed_with_position_no_sell_orders_yields_oca(self) -> None:
        """COMPLETED entry, position held, no SELL orders -> OCA."""
        plan = _make_plan(entry_status="COMPLETED")
        position = {"symbol": "AAPL", "quantity": 50}
        intents = compute_order_intents([plan], positions=[position], open_orders=[])

        assert len(intents) == 1
        intent = intents[0]
        assert intent.action == "OCA"
        assert intent.quantity == 50
        assert "no existing SELL orders" in intent.reason

    def test_completed_with_position_existing_sell_orders_yields_skip(self) -> None:
        """COMPLETED entry, position held, existing SELL orders -> SKIP."""
        plan = _make_plan(entry_status="COMPLETED")
        position = {"symbol": "AAPL", "quantity": 50}
        sell_order = {
            "order_id": "88888",
            "symbol": "AAPL",
            "action": "SELL",
            "quantity": 50,
        }
        intents = compute_order_intents(
            [plan], positions=[position], open_orders=[sell_order]
        )

        assert len(intents) == 1
        assert intents[0].action == "SKIP"
        assert "Existing SELL orders" in intents[0].reason

    def test_completed_no_position_yields_skip_with_error(self) -> None:
        """COMPLETED entry, no position held -> SKIP with error message."""
        plan = _make_plan(entry_status="COMPLETED")
        intents = compute_order_intents([plan], positions=[], open_orders=[])

        assert len(intents) == 1
        assert intents[0].action == "SKIP"
        assert "no position held" in intents[0].reason

    def test_oca_uses_min_of_plan_qty_and_held_qty(self) -> None:
        """OCA quantity should be min(plan.quantity, held_qty)."""
        plan = _make_plan(entry_status="COMPLETED", quantity=50)
        # Only 30 shares held (partial fill)
        position = {"symbol": "AAPL", "quantity": 30}
        intents = compute_order_intents([plan], positions=[position], open_orders=[])

        assert len(intents) == 1
        assert intents[0].action == "OCA"
        assert intents[0].quantity == 30  # min(50, 30)

    def test_oca_uses_plan_qty_when_held_exceeds(self) -> None:
        """OCA quantity should be plan.quantity when held > plan qty."""
        plan = _make_plan(entry_status="COMPLETED", quantity=50)
        position = {"symbol": "AAPL", "quantity": 100}
        intents = compute_order_intents([plan], positions=[position], open_orders=[])

        assert len(intents) == 1
        assert intents[0].action == "OCA"
        assert intents[0].quantity == 50  # min(50, 100)

    def test_unknown_entry_status_yields_skip(self) -> None:
        """Unknown entry status -> SKIP."""
        plan = _make_plan(entry_status="UNKNOWN_STATUS")
        intents = compute_order_intents([plan], positions=[], open_orders=[])

        assert len(intents) == 1
        assert intents[0].action == "SKIP"
        assert "Unknown entry status" in intents[0].reason

    def test_multiple_plans_mixed(self) -> None:
        """Multiple plans produce correct intents for each."""
        plans = [
            _make_plan(plan_id="p1", ticker="AAPL", entry_status="PENDING"),
            _make_plan(plan_id="p2", ticker="MSFT", entry_status="COMPLETED", quantity=30),
        ]
        positions = [{"symbol": "MSFT", "quantity": 30}]
        open_orders: list[dict] = []

        intents = compute_order_intents(plans, positions, open_orders)
        assert len(intents) == 2
        assert intents[0].action == "BRACKET"
        assert intents[0].plan_id == "p1"
        assert intents[1].action == "OCA"
        assert intents[1].plan_id == "p2"

    def test_empty_plans_returns_empty(self) -> None:
        """No plans -> no intents."""
        intents = compute_order_intents([], positions=[], open_orders=[])
        assert intents == []

    def test_zero_entry_price_bracket_yields_skip(self) -> None:
        """BRACKET with zero entry_limit_price -> SKIP."""
        plan = _make_plan(entry_status="PENDING", entry_limit_price=0.0)
        intents = compute_order_intents([plan], positions=[], open_orders=[])

        assert len(intents) == 1
        assert intents[0].action == "SKIP"
        assert "Zero or negative price" in intents[0].reason
        assert "entry_limit_price" in intents[0].reason

    def test_zero_sl_price_oca_yields_skip(self) -> None:
        """OCA with zero sl_stop_price -> SKIP."""
        plan = _make_plan(entry_status="COMPLETED", sl_stop_price=0.0)
        position = {"symbol": "AAPL", "quantity": 50}
        intents = compute_order_intents([plan], positions=[position], open_orders=[])

        assert len(intents) == 1
        assert intents[0].action == "SKIP"
        assert "Zero or negative price" in intents[0].reason
        assert "sl_stop_price" in intents[0].reason

    def test_negative_price_bracket_yields_skip(self) -> None:
        """BRACKET with negative tp_limit_price -> SKIP."""
        plan = _make_plan(entry_status="PENDING", tp_limit_price=-10.0)
        intents = compute_order_intents([plan], positions=[], open_orders=[])

        assert len(intents) == 1
        assert intents[0].action == "SKIP"
        assert "Zero or negative price" in intents[0].reason

    def test_pending_with_position_yields_oca(self) -> None:
        """PENDING entry but position already held -> OCA (entry likely filled)."""
        plan = _make_plan(entry_status="PENDING")
        position = {"symbol": "AAPL", "quantity": 50}
        intents = compute_order_intents([plan], positions=[position], open_orders=[])

        assert len(intents) == 1
        assert intents[0].action == "OCA"
        assert "position already held" in intents[0].reason.lower()

    def test_pending_with_position_uses_min_qty(self) -> None:
        """PENDING+position OCA uses min(plan.quantity, held_qty)."""
        plan = _make_plan(entry_status="PENDING", quantity=50)
        position = {"symbol": "AAPL", "quantity": 30}
        intents = compute_order_intents([plan], positions=[position], open_orders=[])

        assert len(intents) == 1
        assert intents[0].action == "OCA"
        assert intents[0].quantity == 30

    def test_pending_with_position_and_sell_orders_yields_skip(self) -> None:
        """PENDING+position with existing SELL orders -> SKIP."""
        plan = _make_plan(entry_status="PENDING")
        position = {"symbol": "AAPL", "quantity": 50}
        sell_order = {"order_id": "88888", "symbol": "AAPL", "action": "SELL", "quantity": 50}
        intents = compute_order_intents([plan], positions=[position], open_orders=[sell_order])

        assert len(intents) == 1
        assert intents[0].action == "SKIP"

    def test_different_ticker_orders_dont_match(self) -> None:
        """Orders for different tickers should not cause SKIP."""
        plan = _make_plan(entry_status="PENDING", ticker="AAPL")
        # BUY order exists but for GOOG, not AAPL
        other_order = {
            "order_id": "77777",
            "symbol": "GOOG",
            "action": "BUY",
            "quantity": 10,
        }
        intents = compute_order_intents([plan], positions=[], open_orders=[other_order])

        assert len(intents) == 1
        assert intents[0].action == "BRACKET"
