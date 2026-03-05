"""Tests for McpClients — MCP client session manager for Tiger and Zaza."""

from __future__ import annotations

from contextlib import AsyncExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zaza_consumer.mcp_clients import McpClients

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_call_result(text: str) -> MagicMock:
    """Build a mock call_tool result with a single TextContent item."""
    content_item = MagicMock()
    content_item.text = text
    content_item.type = "text"
    result = MagicMock()
    result.content = [content_item]
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mcp_clients() -> McpClients:
    """McpClients with mocked sessions (bypass connect())."""
    clients = McpClients(
        tiger_url="http://tiger:8000/mcp",
        zaza_url="http://zaza:8100/mcp",
    )
    clients._tiger_session = AsyncMock()
    clients._zaza_session = AsyncMock()
    clients._connected = True
    return clients


# ---------------------------------------------------------------------------
# Tiger wrapper tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_place_order_buy_limit(mcp_clients: McpClients) -> None:
    """place_order builds correct arguments and calls the right Tiger tool."""
    mcp_clients._tiger_session.call_tool.return_value = _mock_call_result(
        "Order placed: BUY 10 AAPL @ 150.00"
    )

    result = await mcp_clients.place_order(
        symbol="AAPL",
        action="BUY",
        quantity=10,
        order_type="LMT",
        limit_price=150.00,
    )

    assert result == "Order placed: BUY 10 AAPL @ 150.00"
    mcp_clients._tiger_session.call_tool.assert_awaited_once_with(
        "place_stock_order",
        {
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 10,
            "order_type": "LMT",
            "limit_price": 150.00,
        },
    )


@pytest.mark.asyncio
async def test_place_order_with_stop_price(mcp_clients: McpClients) -> None:
    """place_order includes stop_price when provided."""
    mcp_clients._tiger_session.call_tool.return_value = _mock_call_result(
        "Order placed: BUY 5 TSLA STP_LMT"
    )

    result = await mcp_clients.place_order(
        symbol="TSLA",
        action="BUY",
        quantity=5,
        order_type="STP_LMT",
        limit_price=200.00,
        stop_price=195.00,
    )

    assert result == "Order placed: BUY 5 TSLA STP_LMT"
    mcp_clients._tiger_session.call_tool.assert_awaited_once_with(
        "place_stock_order",
        {
            "symbol": "TSLA",
            "action": "BUY",
            "quantity": 5,
            "order_type": "STP_LMT",
            "limit_price": 200.00,
            "stop_price": 195.00,
        },
    )


@pytest.mark.asyncio
async def test_place_order_omits_none_prices(mcp_clients: McpClients) -> None:
    """place_order does NOT include limit_price or stop_price when None."""
    mcp_clients._tiger_session.call_tool.return_value = _mock_call_result(
        "Order placed"
    )

    await mcp_clients.place_order(
        symbol="GOOG",
        action="SELL",
        quantity=1,
        order_type="LMT",
        limit_price=None,
        stop_price=None,
    )

    expected_args = {
        "symbol": "GOOG",
        "action": "SELL",
        "quantity": 1,
        "order_type": "LMT",
    }
    mcp_clients._tiger_session.call_tool.assert_awaited_once_with(
        "place_stock_order", expected_args
    )


@pytest.mark.asyncio
async def test_cancel_order(mcp_clients: McpClients) -> None:
    """cancel_order passes order_id to Tiger cancel_order tool."""
    mcp_clients._tiger_session.call_tool.return_value = _mock_call_result(
        "Order 12345 cancelled"
    )

    result = await mcp_clients.cancel_order(order_id=12345)

    assert result == "Order 12345 cancelled"
    mcp_clients._tiger_session.call_tool.assert_awaited_once_with(
        "cancel_order", {"order_id": 12345}
    )


@pytest.mark.asyncio
async def test_modify_order(mcp_clients: McpClients) -> None:
    """modify_order passes order_id plus optional fields."""
    mcp_clients._tiger_session.call_tool.return_value = _mock_call_result(
        "Order 999 modified"
    )

    result = await mcp_clients.modify_order(
        order_id=999, quantity=20, limit_price=155.50
    )

    assert result == "Order 999 modified"
    mcp_clients._tiger_session.call_tool.assert_awaited_once_with(
        "modify_order",
        {"order_id": 999, "quantity": 20, "limit_price": 155.50},
    )


@pytest.mark.asyncio
async def test_modify_order_omits_none_fields(mcp_clients: McpClients) -> None:
    """modify_order does NOT include optional fields when None."""
    mcp_clients._tiger_session.call_tool.return_value = _mock_call_result(
        "Order 888 modified"
    )

    await mcp_clients.modify_order(order_id=888, stop_price=100.0)

    mcp_clients._tiger_session.call_tool.assert_awaited_once_with(
        "modify_order",
        {"order_id": 888, "stop_price": 100.0},
    )


@pytest.mark.asyncio
async def test_get_open_orders(mcp_clients: McpClients) -> None:
    """get_open_orders defaults to empty symbol."""
    mcp_clients._tiger_session.call_tool.return_value = _mock_call_result(
        "No open orders."
    )

    result = await mcp_clients.get_open_orders()

    assert result == "No open orders."
    mcp_clients._tiger_session.call_tool.assert_awaited_once_with(
        "get_open_orders", {"symbol": ""}
    )


@pytest.mark.asyncio
async def test_get_open_orders_with_symbol(mcp_clients: McpClients) -> None:
    """get_open_orders passes symbol filter."""
    mcp_clients._tiger_session.call_tool.return_value = _mock_call_result(
        "1 open order for AAPL"
    )

    result = await mcp_clients.get_open_orders(symbol="AAPL")

    assert result == "1 open order for AAPL"
    mcp_clients._tiger_session.call_tool.assert_awaited_once_with(
        "get_open_orders", {"symbol": "AAPL"}
    )


@pytest.mark.asyncio
async def test_get_order_detail(mcp_clients: McpClients) -> None:
    """get_order_detail passes order_id."""
    mcp_clients._tiger_session.call_tool.return_value = _mock_call_result(
        "Order 42 details"
    )

    result = await mcp_clients.get_order_detail(order_id=42)

    assert result == "Order 42 details"
    mcp_clients._tiger_session.call_tool.assert_awaited_once_with(
        "get_order_detail", {"order_id": 42}
    )


@pytest.mark.asyncio
async def test_get_filled_orders(mcp_clients: McpClients) -> None:
    """get_filled_orders calls transaction_history with symbol filter."""
    mcp_clients._tiger_session.call_tool.return_value = _mock_call_result(
        "3 transactions"
    )

    result = await mcp_clients.get_filled_orders(symbol="MSFT", limit=10)

    assert result == "3 transactions"
    mcp_clients._tiger_session.call_tool.assert_awaited_once_with(
        "get_transaction_history", {"limit": 10, "symbol": "MSFT"}
    )


@pytest.mark.asyncio
async def test_get_filled_orders_no_symbol(mcp_clients: McpClients) -> None:
    """get_filled_orders omits symbol when None."""
    mcp_clients._tiger_session.call_tool.return_value = _mock_call_result(
        "All transactions"
    )

    await mcp_clients.get_filled_orders()

    mcp_clients._tiger_session.call_tool.assert_awaited_once_with(
        "get_transaction_history", {"limit": 50}
    )


# ---------------------------------------------------------------------------
# Zaza wrapper tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_trade_plans(mcp_clients: McpClients) -> None:
    """list_trade_plans calls zaza list_trade_plans."""
    mcp_clients._zaza_session.call_tool.return_value = _mock_call_result(
        '[{"plan_id": "abc"}]'
    )

    result = await mcp_clients.list_trade_plans()

    assert result == '[{"plan_id": "abc"}]'
    mcp_clients._zaza_session.call_tool.assert_awaited_once_with(
        "list_trade_plans", {"include_archived": False}
    )


@pytest.mark.asyncio
async def test_list_trade_plans_archived(mcp_clients: McpClients) -> None:
    """list_trade_plans passes include_archived flag."""
    mcp_clients._zaza_session.call_tool.return_value = _mock_call_result("[]")

    await mcp_clients.list_trade_plans(include_archived=True)

    mcp_clients._zaza_session.call_tool.assert_awaited_once_with(
        "list_trade_plans", {"include_archived": True}
    )


@pytest.mark.asyncio
async def test_get_trade_plan(mcp_clients: McpClients) -> None:
    """get_trade_plan passes plan_id to zaza."""
    mcp_clients._zaza_session.call_tool.return_value = _mock_call_result(
        "<trade-plan>...</trade-plan>"
    )

    result = await mcp_clients.get_trade_plan(plan_id="plan-123")

    assert result == "<trade-plan>...</trade-plan>"
    mcp_clients._zaza_session.call_tool.assert_awaited_once_with(
        "get_trade_plan", {"plan_id": "plan-123"}
    )


@pytest.mark.asyncio
async def test_update_trade_plan(mcp_clients: McpClients) -> None:
    """update_trade_plan passes plan_id and xml to zaza."""
    mcp_clients._zaza_session.call_tool.return_value = _mock_call_result(
        "Plan updated"
    )

    result = await mcp_clients.update_trade_plan(
        plan_id="plan-123", xml="<trade-plan>new</trade-plan>"
    )

    assert result == "Plan updated"
    mcp_clients._zaza_session.call_tool.assert_awaited_once_with(
        "update_trade_plan",
        {"plan_id": "plan-123", "xml": "<trade-plan>new</trade-plan>"},
    )


@pytest.mark.asyncio
async def test_close_trade_plan(mcp_clients: McpClients) -> None:
    """close_trade_plan passes plan_id and reason to zaza."""
    mcp_clients._zaza_session.call_tool.return_value = _mock_call_result(
        "Plan archived"
    )

    result = await mcp_clients.close_trade_plan(
        plan_id="plan-123", reason="Target hit"
    )

    assert result == "Plan archived"
    mcp_clients._zaza_session.call_tool.assert_awaited_once_with(
        "close_trade_plan",
        {"plan_id": "plan-123", "reason": "Target hit"},
    )


@pytest.mark.asyncio
async def test_close_trade_plan_default_reason(mcp_clients: McpClients) -> None:
    """close_trade_plan defaults reason to empty string."""
    mcp_clients._zaza_session.call_tool.return_value = _mock_call_result(
        "Plan archived"
    )

    await mcp_clients.close_trade_plan(plan_id="plan-456")

    mcp_clients._zaza_session.call_tool.assert_awaited_once_with(
        "close_trade_plan",
        {"plan_id": "plan-456", "reason": ""},
    )


# ---------------------------------------------------------------------------
# Connection guard tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_not_connected_raises_on_tiger_call() -> None:
    """Calling a Tiger method when not connected raises RuntimeError."""
    clients = McpClients(
        tiger_url="http://tiger:8000/mcp",
        zaza_url="http://zaza:8100/mcp",
    )
    assert clients._connected is False

    with pytest.raises(RuntimeError, match="Not connected"):
        await clients.place_order(
            symbol="AAPL", action="BUY", quantity=1, order_type="LMT"
        )


@pytest.mark.asyncio
async def test_not_connected_raises_on_zaza_call() -> None:
    """Calling a Zaza method when not connected raises RuntimeError."""
    clients = McpClients(
        tiger_url="http://tiger:8000/mcp",
        zaza_url="http://zaza:8100/mcp",
    )

    with pytest.raises(RuntimeError, match="Not connected"):
        await clients.list_trade_plans()


# ---------------------------------------------------------------------------
# Close / lifecycle tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_resets_state(mcp_clients: McpClients) -> None:
    """close() sets sessions to None and connected to False."""
    mock_stack = AsyncMock()
    mcp_clients._exit_stack = mock_stack

    await mcp_clients.close()

    assert mcp_clients._tiger_session is None
    assert mcp_clients._zaza_session is None
    assert mcp_clients._connected is False
    assert mcp_clients._exit_stack is None
    mock_stack.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_without_exit_stack(mcp_clients: McpClients) -> None:
    """close() works even if _exit_stack is None."""
    mcp_clients._exit_stack = None

    await mcp_clients.close()

    assert mcp_clients._tiger_session is None
    assert mcp_clients._connected is False


# ---------------------------------------------------------------------------
# Error propagation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tiger_call_propagates_exception(mcp_clients: McpClients) -> None:
    """Exceptions from Tiger session.call_tool are re-raised."""
    mcp_clients._tiger_session.call_tool.side_effect = ConnectionError(
        "connection lost"
    )

    with pytest.raises(ConnectionError, match="connection lost"):
        await mcp_clients.cancel_order(order_id=1)


@pytest.mark.asyncio
async def test_zaza_call_propagates_exception(mcp_clients: McpClients) -> None:
    """Exceptions from Zaza session.call_tool are re-raised."""
    mcp_clients._zaza_session.call_tool.side_effect = TimeoutError("timed out")

    with pytest.raises(TimeoutError, match="timed out"):
        await mcp_clients.get_trade_plan(plan_id="x")


# ---------------------------------------------------------------------------
# Connection leak tests (ISSUE-27)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_failure_cleans_up_partial_connections() -> None:
    """If Zaza connect fails, Tiger connection is cleaned up via aclose."""
    clients = McpClients(
        tiger_url="http://tiger:8000/mcp",
        zaza_url="http://zaza:8100/mcp",
    )

    mock_stack = AsyncMock(spec=AsyncExitStack)

    # Track whether aclose was called on failure
    calls_before_zaza: list[str] = []

    async def _mock_enter_context(cm):
        """Simulate entering contexts: Tiger works, Zaza fails."""
        nonlocal calls_before_zaza
        calls_before_zaza.append("enter")
        if len(calls_before_zaza) > 2:
            # Third enter_async_context (Zaza streamable) fails
            raise ConnectionError("Zaza server unreachable")
        # Return a mock for the first two (Tiger transport + session)
        mock = AsyncMock()
        mock.initialize = AsyncMock()
        if len(calls_before_zaza) == 1:
            # Tiger transport returns (read, write, _)
            return (AsyncMock(), AsyncMock(), None)
        # Tiger session
        return mock

    mock_stack.enter_async_context = _mock_enter_context
    mock_stack.__aenter__ = AsyncMock(return_value=mock_stack)

    with patch(
        "zaza_consumer.mcp_clients.AsyncExitStack",
        return_value=mock_stack,
    ):
        with pytest.raises(ConnectionError, match="Zaza server"):
            await clients.connect(max_retries=1)

    # Exit stack must have been closed to clean up Tiger
    mock_stack.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_connect_retries_on_connection_error() -> None:
    """connect() retries on ConnectionError and succeeds when server becomes available."""
    clients = McpClients(
        tiger_url="http://tiger:8000/mcp",
        zaza_url="http://zaza:8100/mcp",
    )

    attempt_count = 0

    async def _mock_enter_context(cm):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count <= 2:
            # First attempt: Tiger transport succeeds, Tiger session fails
            if attempt_count == 1:
                return (AsyncMock(), AsyncMock(), None)
            raise OSError("Connection refused")
        # After retry: all contexts succeed
        mock = AsyncMock()
        mock.initialize = AsyncMock()
        if attempt_count in (3, 5):
            # Transport contexts return (read, write, _)
            return (AsyncMock(), AsyncMock(), None)
        return mock

    mock_stack = AsyncMock(spec=AsyncExitStack)
    mock_stack.enter_async_context = _mock_enter_context
    mock_stack.__aenter__ = AsyncMock(return_value=mock_stack)

    with patch(
        "zaza_consumer.mcp_clients.AsyncExitStack",
        return_value=mock_stack,
    ), patch("zaza_consumer.mcp_clients.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await clients.connect(max_retries=3, base_delay=1.0)

    # Should have slept once with 1s delay (first retry)
    mock_sleep.assert_awaited_once_with(1.0)
    assert clients._connected is True


@pytest.mark.asyncio
async def test_connect_no_retry_on_non_connection_error() -> None:
    """connect() does not retry on non-connection errors (e.g. protocol errors)."""
    clients = McpClients(
        tiger_url="http://tiger:8000/mcp",
        zaza_url="http://zaza:8100/mcp",
    )

    mock_stack = AsyncMock(spec=AsyncExitStack)
    mock_stack.enter_async_context = AsyncMock(
        side_effect=ValueError("Protocol error")
    )
    mock_stack.__aenter__ = AsyncMock(return_value=mock_stack)

    with patch(
        "zaza_consumer.mcp_clients.AsyncExitStack",
        return_value=mock_stack,
    ), patch("zaza_consumer.mcp_clients.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(ValueError, match="Protocol error"):
            await clients.connect(max_retries=3)

    # Should NOT have retried
    mock_sleep.assert_not_awaited()
