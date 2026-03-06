"""Tests for order_sync.executor — MCP order placement with mocked sessions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from order_sync.executor import OrderResult, _extract_order_id, _place_single_order, place_orders
from order_sync.planner import OrderIntent


def _make_intent(
    *,
    action: str = "BRACKET",
    plan_id: str = "plan-1",
    ticker: str = "AAPL",
    quantity: int = 50,
    entry_limit_price: float | None = 184.00,
    tp_limit_price: float = 194.50,
    sl_stop_price: float = 180.00,
    sl_limit_price: float = 179.50,
    reason: str = "test",
) -> OrderIntent:
    return OrderIntent(
        plan_id=plan_id,
        ticker=ticker,
        action=action,
        reason=reason,
        entry_limit_price=entry_limit_price,
        quantity=quantity,
        tp_limit_price=tp_limit_price,
        sl_stop_price=sl_stop_price,
        sl_limit_price=sl_limit_price,
    )


def _make_mcp_response(text: str) -> MagicMock:
    """Create a mock MCP CallToolResult with text content."""
    content_item = MagicMock()
    content_item.text = text
    resp = MagicMock()
    resp.content = [content_item]
    return resp


class TestExtractOrderId:
    """Tests for order ID extraction from Tiger response text."""

    def test_extracts_order_id(self) -> None:
        text = "Bracket order placed successfully.\nOrder ID:    12345\nParent: 12345"
        assert _extract_order_id(text) == "12345"

    def test_no_order_id_returns_none(self) -> None:
        text = "Some response without order info"
        assert _extract_order_id(text) is None

    def test_alphanumeric_order_id(self) -> None:
        text = "Order ID: ABC-123"
        assert _extract_order_id(text) == "ABC-123"


class TestPlaceSingleOrder:
    """Tests for placing a single order via mocked MCP session."""

    @pytest.mark.asyncio
    async def test_successful_bracket_order(self) -> None:
        session = AsyncMock()
        session.call_tool.return_value = _make_mcp_response(
            "Bracket order placed successfully.\nOrder ID:    12345"
        )

        intent = _make_intent(action="BRACKET")
        result = await _place_single_order(session, intent)

        assert result.success is True
        assert result.order_id == "12345"
        assert result.action == "BRACKET"
        session.call_tool.assert_called_once_with(
            "place_bracket_order",
            {
                "symbol": "AAPL",
                "quantity": 50,
                "entry_limit_price": 184.00,
                "tp_limit_price": 194.50,
                "sl_stop_price": 180.00,
                "sl_limit_price": 179.50,
            },
        )

    @pytest.mark.asyncio
    async def test_successful_oca_order(self) -> None:
        session = AsyncMock()
        session.call_tool.return_value = _make_mcp_response(
            "OCA order placed successfully.\nOrder ID:    67890"
        )

        intent = _make_intent(action="OCA", entry_limit_price=None)
        result = await _place_single_order(session, intent)

        assert result.success is True
        assert result.order_id == "67890"
        assert result.action == "OCA"
        session.call_tool.assert_called_once_with(
            "place_oca_order",
            {
                "symbol": "AAPL",
                "quantity": 50,
                "tp_limit_price": 194.50,
                "sl_stop_price": 180.00,
                "sl_limit_price": 179.50,
            },
        )

    @pytest.mark.asyncio
    async def test_error_response_returns_failure(self) -> None:
        session = AsyncMock()
        session.call_tool.return_value = _make_mcp_response(
            "Error: Insufficient funds"
        )

        intent = _make_intent(action="BRACKET")
        result = await _place_single_order(session, intent)

        assert result.success is False
        assert "Insufficient funds" in (result.error or "")

    @pytest.mark.asyncio
    async def test_blocked_response_returns_failure(self) -> None:
        session = AsyncMock()
        session.call_tool.return_value = _make_mcp_response(
            "BLOCKED: Market closed"
        )

        intent = _make_intent(action="BRACKET")
        result = await _place_single_order(session, intent)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        session = AsyncMock()
        session.call_tool.side_effect = ConnectionError("Connection lost")

        intent = _make_intent(action="BRACKET")
        result = await _place_single_order(session, intent)

        assert result.success is False
        assert "Connection lost" in (result.error or "")

    @pytest.mark.asyncio
    async def test_no_order_id_returns_failure(self) -> None:
        """Response without order ID is treated as failure."""
        session = AsyncMock()
        session.call_tool.return_value = _make_mcp_response(
            "Bracket order placed successfully."
        )

        intent = _make_intent(action="BRACKET")
        result = await _place_single_order(session, intent)

        assert result.success is False
        assert result.order_id is None
        assert "no order ID returned" in (result.error or "")

    @pytest.mark.asyncio
    async def test_unknown_action_returns_failure(self) -> None:
        session = AsyncMock()
        intent = _make_intent(action="UNKNOWN")
        result = await _place_single_order(session, intent)

        assert result.success is False
        assert "Unknown action" in (result.error or "")


class TestPlaceOrders:
    """Tests for place_orders orchestration (skip, retry)."""

    @pytest.mark.asyncio
    async def test_skip_intents_are_ignored(self) -> None:
        session = AsyncMock()
        skip_intent = _make_intent(action="SKIP")
        results = await place_orders(session, [skip_intent])
        assert results == []
        session.call_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_order_no_retry(self) -> None:
        session = AsyncMock()
        session.call_tool.return_value = _make_mcp_response(
            "Bracket order placed.\nOrder ID:    11111"
        )

        intent = _make_intent(action="BRACKET")
        results = await place_orders(session, [intent])

        assert len(results) == 1
        assert results[0].success is True
        # Should only be called once (no retry needed)
        assert session.call_tool.call_count == 1

    @pytest.mark.asyncio
    async def test_failed_order_retries_once(self) -> None:
        session = AsyncMock()
        # First call fails, second succeeds
        session.call_tool.side_effect = [
            _make_mcp_response("Error: Timeout"),
            _make_mcp_response("Bracket order placed.\nOrder ID:    22222"),
        ]

        intent = _make_intent(action="BRACKET")
        results = await place_orders(session, [intent])

        assert len(results) == 1
        assert results[0].success is True
        assert session.call_tool.call_count == 2

    @pytest.mark.asyncio
    async def test_failed_order_after_retry_records_error(self) -> None:
        session = AsyncMock()
        # Both calls fail
        session.call_tool.side_effect = [
            _make_mcp_response("Error: Timeout"),
            _make_mcp_response("Error: Still broken"),
        ]

        intent = _make_intent(action="BRACKET")
        results = await place_orders(session, [intent])

        assert len(results) == 1
        assert results[0].success is False
        assert session.call_tool.call_count == 2

    @pytest.mark.asyncio
    async def test_multiple_intents_processed(self) -> None:
        session = AsyncMock()
        session.call_tool.return_value = _make_mcp_response(
            "Order placed.\nOrder ID:    33333"
        )

        intents = [
            _make_intent(action="BRACKET", plan_id="p1", ticker="AAPL"),
            _make_intent(action="OCA", plan_id="p2", ticker="MSFT", entry_limit_price=None),
        ]
        results = await place_orders(session, intents)

        assert len(results) == 2
        assert all(r.success for r in results)
