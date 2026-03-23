"""Tests for order_sync.worker — orchestration with mocked MCP interactions."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from order_sync.executor import OrderResult
from order_sync.parsers import TradePlan


def _make_mcp_response(text: str) -> MagicMock:
    """Create a mock MCP CallToolResult with text content."""
    content_item = MagicMock()
    content_item.text = text
    resp = MagicMock()
    resp.content = [content_item]
    return resp


SAMPLE_PLAN_XML = """\
<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC">
  <summary>
    <side>BUY</side>
    <ticker>AAPL</ticker>
    <quantity>50</quantity>
    <conviction>HIGH</conviction>
    <expected_value>+3.8%</expected_value>
    <risk_reward_ratio>1:2.5</risk_reward_ratio>
    <rationale>RSI bouncing off 38</rationale>
  </summary>
  <position>
    <status>NONE</status>
    <quantity>0</quantity>
    <avg_cost>0.0</avg_cost>
  </position>
  <order>
    <order_id>BUY-AAPL-20260224-001</order_id>
    <entry>
      <status>PENDING</status>
      <strategy>support_bounce</strategy>
      <trigger>Price holds above $183.50</trigger>
      <limit-order>
        <type>LIMIT</type>
        <side>BUY</side>
        <ticker>AAPL</ticker>
        <quantity>50</quantity>
        <limit_price>184.00</limit_price>
        <time_in_force>DAY</time_in_force>
      </limit-order>
    </entry>
    <exit>
      <stop-loss>
        <limit-order>
          <type>STOP_LIMIT</type>
          <side>SELL</side>
          <ticker>AAPL</ticker>
          <quantity>50</quantity>
          <stop_price>180.00</stop_price>
          <limit_price>179.50</limit_price>
          <time_in_force>DAY</time_in_force>
        </limit-order>
      </stop-loss>
      <take-profit>
        <limit-order>
          <type>LIMIT</type>
          <side>SELL</side>
          <ticker>AAPL</ticker>
          <quantity>50</quantity>
          <limit_price>194.50</limit_price>
          <time_in_force>DAY</time_in_force>
        </limit-order>
      </take-profit>
    </exit>
  </order>
</trade-plan>
"""


class TestFetchPlansFromSession:
    """Tests for _fetch_plans_from_session with mocked MCP session."""

    @pytest.mark.asyncio
    async def test_successful_fetch(self) -> None:
        """Fetch and parse a valid plan from Zaza MCP."""
        from order_sync.worker import _fetch_plans_from_session

        session = AsyncMock()
        session.call_tool.side_effect = [
            # list_trade_plans response
            _make_mcp_response(json.dumps({
                "status": "ok",
                "plans": [{"plan_id": "p1"}],
            })),
            # get_trade_plan response
            _make_mcp_response(json.dumps({
                "status": "ok",
                "xml": SAMPLE_PLAN_XML,
            })),
        ]

        plans = await _fetch_plans_from_session(session)
        assert len(plans) == 1
        assert plans[0].plan_id == "p1"
        assert plans[0].ticker == "AAPL"

    @pytest.mark.asyncio
    async def test_empty_plans_list(self) -> None:
        """Empty plans list returns empty."""
        from order_sync.worker import _fetch_plans_from_session

        session = AsyncMock()
        session.call_tool.return_value = _make_mcp_response(
            json.dumps({"status": "ok", "plans": []})
        )

        plans = await _fetch_plans_from_session(session)
        assert plans == []

    @pytest.mark.asyncio
    async def test_invalid_json_returns_empty(self) -> None:
        """Invalid JSON from list_trade_plans returns empty."""
        from order_sync.worker import _fetch_plans_from_session

        session = AsyncMock()
        session.call_tool.return_value = _make_mcp_response("not json")

        plans = await _fetch_plans_from_session(session)
        assert plans == []

    @pytest.mark.asyncio
    async def test_status_not_ok_returns_empty(self) -> None:
        """Non-ok status returns empty."""
        from order_sync.worker import _fetch_plans_from_session

        session = AsyncMock()
        session.call_tool.return_value = _make_mcp_response(
            json.dumps({"status": "error", "error": "something"})
        )

        plans = await _fetch_plans_from_session(session)
        assert plans == []

    @pytest.mark.asyncio
    async def test_corrupt_plan_xml_skipped(self) -> None:
        """Corrupt plan XML is skipped with warning."""
        from order_sync.worker import _fetch_plans_from_session

        session = AsyncMock()
        session.call_tool.side_effect = [
            _make_mcp_response(json.dumps({
                "status": "ok",
                "plans": [{"plan_id": "p1"}],
            })),
            _make_mcp_response(json.dumps({
                "status": "ok",
                "xml": "<broken>",
            })),
        ]

        plans = await _fetch_plans_from_session(session)
        assert plans == []

    @pytest.mark.asyncio
    async def test_plan_fetch_exception_skipped(self) -> None:
        """Exception during plan fetch is caught and skipped."""
        from order_sync.worker import _fetch_plans_from_session

        session = AsyncMock()
        session.call_tool.side_effect = [
            _make_mcp_response(json.dumps({
                "status": "ok",
                "plans": [{"plan_id": "p1"}],
            })),
            ConnectionError("lost connection"),
        ]

        plans = await _fetch_plans_from_session(session)
        assert plans == []

    @pytest.mark.asyncio
    async def test_plan_detail_status_not_ok_skipped(self) -> None:
        """Plan detail with non-ok status is skipped."""
        from order_sync.worker import _fetch_plans_from_session

        session = AsyncMock()
        session.call_tool.side_effect = [
            _make_mcp_response(json.dumps({
                "status": "ok",
                "plans": [{"plan_id": "p1"}],
            })),
            _make_mcp_response(json.dumps({
                "status": "error",
                "error": "not found",
            })),
        ]

        plans = await _fetch_plans_from_session(session)
        assert plans == []

    @pytest.mark.asyncio
    async def test_empty_plan_id_skipped(self) -> None:
        """Plan metadata with empty plan_id is skipped."""
        from order_sync.worker import _fetch_plans_from_session

        session = AsyncMock()
        session.call_tool.return_value = _make_mcp_response(
            json.dumps({
                "status": "ok",
                "plans": [{"plan_id": ""}],
            })
        )

        plans = await _fetch_plans_from_session(session)
        assert plans == []


class TestFetchTigerState:
    """Tests for _fetch_tiger_state with mocked MCP session."""

    @pytest.mark.asyncio
    async def test_successful_fetch(self) -> None:
        """Fetch and parse positions + orders from Tiger MCP."""
        from order_sync.worker import _fetch_tiger_state

        positions_text = """\
Current Positions
=================

AAPL
  Quantity: 50
  Avg Cost: $184.00
  Market Value: $9,500.00
  Unrealized P&L: $300.00 (3.26%)
"""
        orders_text = """\
Open Orders
===========
Order 12345: AAPL BUY 50 (filled 0) | type=LIMIT limit=184.00 status=SUBMITTED
"""

        session = AsyncMock()
        session.call_tool.side_effect = [
            _make_mcp_response(positions_text),
            _make_mcp_response(orders_text),
        ]

        positions, open_orders = await _fetch_tiger_state(session)
        assert len(positions) == 1
        assert positions[0]["symbol"] == "AAPL"
        assert len(open_orders) == 1
        assert open_orders[0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_empty_state(self) -> None:
        """No positions and no orders."""
        from order_sync.worker import _fetch_tiger_state

        session = AsyncMock()
        session.call_tool.side_effect = [
            _make_mcp_response("No positions found."),
            _make_mcp_response("No open orders."),
        ]

        positions, open_orders = await _fetch_tiger_state(session)
        assert positions == []
        assert open_orders == []


class TestWorkerRun:
    """Tests for worker.run() orchestration."""

    @pytest.mark.asyncio
    async def test_no_plans_returns_0(self) -> None:
        """When Zaza returns no active plans, return 0."""
        from order_sync.worker import run

        with (
            patch("order_sync.worker._fetch_plans") as mock_plans,
            patch("order_sync.worker.streamable_http_client", create=True),
        ):
            mock_plans.return_value = []

            exit_code = await run(dry_run=False)
            assert exit_code == 0

    @pytest.mark.asyncio
    async def test_dry_run_returns_0_no_orders_placed(self) -> None:
        """dry_run computes intents but does not place orders."""
        from order_sync.worker import run

        plan = TradePlan(
            plan_id="p1",
            ticker="AAPL",
            side="BUY",
            quantity=50,
            order_id="BUY-AAPL-001",
            entry_status="PENDING",
            entry_limit_price=184.00,
            sl_stop_price=180.00,
            sl_limit_price=179.50,
            tp_limit_price=194.50,
        )

        with (
            patch("order_sync.worker._fetch_plans") as mock_plans,
            patch("order_sync.worker._fetch_tiger_state") as mock_tiger,
            patch("order_sync.worker.streamable_http_client", create=True) as mock_http,
            patch("order_sync.worker.ClientSession", create=True) as mock_cs,
        ):
            mock_plans.return_value = [plan]
            mock_tiger.return_value = ([], [])
            # Mock the Tiger session context managers
            mock_session = AsyncMock()
            mock_cs.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cs.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.return_value.__aenter__ = AsyncMock(return_value=(None, None, None))
            mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

            exit_code = await run(dry_run=True)
            assert exit_code == 0

    @pytest.mark.asyncio
    async def test_all_orders_placed_returns_0(self) -> None:
        """All orders placed successfully -> return 0."""
        from order_sync.worker import run

        plan = TradePlan(
            plan_id="p1",
            ticker="AAPL",
            side="BUY",
            quantity=50,
            order_id="BUY-AAPL-001",
            entry_status="PENDING",
            entry_limit_price=184.00,
            sl_stop_price=180.00,
            sl_limit_price=179.50,
            tp_limit_price=194.50,
        )

        with (
            patch("order_sync.worker._fetch_plans") as mock_plans,
            patch("order_sync.worker._fetch_tiger_state") as mock_tiger,
            patch("order_sync.worker.place_orders") as mock_place,
            patch("order_sync.worker.streamable_http_client", create=True) as mock_http,
            patch("order_sync.worker.ClientSession", create=True) as mock_cs,
        ):
            mock_plans.return_value = [plan]
            mock_tiger.return_value = ([], [])
            mock_place.return_value = [
                OrderResult(
                    plan_id="p1", ticker="AAPL", action="BRACKET",
                    success=True, order_id="12345", error=None,
                )
            ]
            mock_session = AsyncMock()
            mock_cs.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cs.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.return_value.__aenter__ = AsyncMock(return_value=(None, None, None))
            mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

            exit_code = await run(dry_run=False)
            assert exit_code == 0
            mock_place.assert_called_once()

    @pytest.mark.asyncio
    async def test_oca_failure_returns_2(self) -> None:
        """OCA failure (unprotected position) -> return 2 (CRITICAL)."""
        from order_sync.worker import run

        plan = TradePlan(
            plan_id="p1",
            ticker="AAPL",
            side="BUY",
            quantity=50,
            order_id="BUY-AAPL-001",
            entry_status="COMPLETED",
            entry_limit_price=184.00,
            sl_stop_price=180.00,
            sl_limit_price=179.50,
            tp_limit_price=194.50,
        )

        with (
            patch("order_sync.worker._fetch_plans") as mock_plans,
            patch("order_sync.worker._fetch_tiger_state") as mock_tiger,
            patch("order_sync.worker.place_orders") as mock_place,
            patch("order_sync.worker.streamable_http_client", create=True) as mock_http,
            patch("order_sync.worker.ClientSession", create=True) as mock_cs,
        ):
            mock_plans.return_value = [plan]
            mock_tiger.return_value = (
                [{"symbol": "AAPL", "quantity": 50}],  # position
                [],  # no orders
            )
            mock_place.return_value = [
                OrderResult(
                    plan_id="p1", ticker="AAPL", action="OCA",
                    success=False, order_id=None, error="Timeout",
                )
            ]
            mock_session = AsyncMock()
            mock_cs.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cs.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.return_value.__aenter__ = AsyncMock(return_value=(None, None, None))
            mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

            exit_code = await run(dry_run=False)
            assert exit_code == 2

    @pytest.mark.asyncio
    async def test_bracket_failure_returns_1(self) -> None:
        """Bracket failure (no position opened) -> return 1 (WARNING)."""
        from order_sync.worker import run

        plan = TradePlan(
            plan_id="p1",
            ticker="AAPL",
            side="BUY",
            quantity=50,
            order_id="BUY-AAPL-001",
            entry_status="PENDING",
            entry_limit_price=184.00,
            sl_stop_price=180.00,
            sl_limit_price=179.50,
            tp_limit_price=194.50,
        )

        with (
            patch("order_sync.worker._fetch_plans") as mock_plans,
            patch("order_sync.worker._fetch_tiger_state") as mock_tiger,
            patch("order_sync.worker.place_orders") as mock_place,
            patch("order_sync.worker.streamable_http_client", create=True) as mock_http,
            patch("order_sync.worker.ClientSession", create=True) as mock_cs,
        ):
            mock_plans.return_value = [plan]
            mock_tiger.return_value = ([], [])
            mock_place.return_value = [
                OrderResult(
                    plan_id="p1", ticker="AAPL", action="BRACKET",
                    success=False, order_id=None, error="Timeout",
                )
            ]
            mock_session = AsyncMock()
            mock_cs.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cs.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.return_value.__aenter__ = AsyncMock(return_value=(None, None, None))
            mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

            exit_code = await run(dry_run=False)
            assert exit_code == 1

    @pytest.mark.asyncio
    async def test_all_skip_returns_0(self) -> None:
        """When all intents are SKIP, no orders placed, return 0."""
        from order_sync.worker import run

        plan = TradePlan(
            plan_id="p1",
            ticker="AAPL",
            side="BUY",
            quantity=50,
            order_id="BUY-AAPL-001",
            entry_status="PENDING",
            entry_limit_price=184.00,
            sl_stop_price=180.00,
            sl_limit_price=179.50,
            tp_limit_price=194.50,
        )
        # Existing BUY order -> SKIP
        buy_order = {
            "order_id": "99999",
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 50,
        }

        with (
            patch("order_sync.worker._fetch_plans") as mock_plans,
            patch("order_sync.worker._fetch_tiger_state") as mock_tiger,
            patch("order_sync.worker.streamable_http_client", create=True) as mock_http,
            patch("order_sync.worker.ClientSession", create=True) as mock_cs,
        ):
            mock_plans.return_value = [plan]
            mock_tiger.return_value = ([], [buy_order])
            mock_session = AsyncMock()
            mock_cs.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cs.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.return_value.__aenter__ = AsyncMock(return_value=(None, None, None))
            mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

            exit_code = await run(dry_run=False)
            assert exit_code == 0
