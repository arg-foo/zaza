"""Tests for Redis stream consumer."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import orjson
import pytest

from zaza_consumer.config import ConsumerSettings
from zaza_consumer.stream import _read_and_process


@pytest.fixture
def settings():
    return ConsumerSettings(
        redis_url="redis://localhost:6379/0",
        tiger_mcp_url="http://localhost:8000/mcp",
        zaza_mcp_url="http://localhost:8100/mcp",
    )


class TestReadAndProcess:
    """Test _read_and_process with mocked Redis."""

    async def test_processes_message_and_acks(self, settings: ConsumerSettings) -> None:
        """Should deserialize message, call handler, and XACK."""
        handler = AsyncMock()
        redis = AsyncMock()
        event_data = {"orderId": 123, "symbol": "AAPL", "filledQuantity": 50}

        msg_id = b"1234567890-0"
        fields = {b"data": orjson.dumps(event_data)}

        # First call returns messages, second call returns empty (to end pending phase)
        redis.xreadgroup = AsyncMock(side_effect=[
            [(b"stream", [(msg_id, fields)])],
            [],  # No more messages
        ])
        redis.xack = AsyncMock()

        shutdown = asyncio.Event()

        await _read_and_process(
            redis=redis,
            stream_key="tiger:events:transaction",
            group="trade-executor",
            consumer="executor-1",
            settings=settings,
            handler=handler,
            read_id="0",
            shutdown=shutdown,
        )

        handler.assert_called_once_with(event_data)
        redis.xack.assert_called_once_with(
            "tiger:events:transaction", "trade-executor", msg_id
        )

    async def test_stops_on_shutdown(self, settings: ConsumerSettings) -> None:
        """Should stop when shutdown event is set."""
        handler = AsyncMock()
        redis = AsyncMock()

        shutdown = asyncio.Event()
        shutdown.set()  # Pre-set shutdown

        redis.xreadgroup = AsyncMock(return_value=[])

        await _read_and_process(
            redis=redis,
            stream_key="tiger:events:transaction",
            group="trade-executor",
            consumer="executor-1",
            settings=settings,
            handler=handler,
            read_id=">",
            shutdown=shutdown,
        )

        handler.assert_not_called()

    async def test_handler_error_does_not_ack(self, settings: ConsumerSettings) -> None:
        """If handler raises, message should NOT be ACKed."""
        handler = AsyncMock(side_effect=RuntimeError("boom"))
        redis = AsyncMock()

        msg_id = b"1234567890-0"
        fields = {b"data": orjson.dumps({"orderId": 1})}

        redis.xreadgroup = AsyncMock(side_effect=[
            [(b"stream", [(msg_id, fields)])],
            [],  # End pending phase
        ])
        redis.xack = AsyncMock()

        shutdown = asyncio.Event()

        await _read_and_process(
            redis=redis,
            stream_key="tiger:events:transaction",
            group="trade-executor",
            consumer="executor-1",
            settings=settings,
            handler=handler,
            read_id="0",
            shutdown=shutdown,
        )

        redis.xack.assert_not_called()

    async def test_pending_phase_returns_on_empty_fields(
        self, settings: ConsumerSettings
    ) -> None:
        """Pending messages with empty fields should end the pending phase."""
        handler = AsyncMock()
        redis = AsyncMock()

        msg_id = b"1234567890-0"
        redis.xreadgroup = AsyncMock(return_value=[
            (b"stream", [(msg_id, {})])
        ])

        shutdown = asyncio.Event()

        await _read_and_process(
            redis=redis,
            stream_key="tiger:events:transaction",
            group="trade-executor",
            consumer="executor-1",
            settings=settings,
            handler=handler,
            read_id="0",
            shutdown=shutdown,
        )

        handler.assert_not_called()

    async def test_xreadgroup_error_retries_after_sleep(
        self, settings: ConsumerSettings
    ) -> None:
        """If xreadgroup raises, should log error and retry (then stop via shutdown)."""
        handler = AsyncMock()
        redis = AsyncMock()

        shutdown = asyncio.Event()

        call_count = 0

        async def xreadgroup_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Redis down")
            # On second call, set shutdown to stop the loop
            shutdown.set()
            return []

        redis.xreadgroup = AsyncMock(side_effect=xreadgroup_side_effect)

        await _read_and_process(
            redis=redis,
            stream_key="tiger:events:transaction",
            group="trade-executor",
            consumer="executor-1",
            settings=settings,
            handler=handler,
            read_id=">",
            shutdown=shutdown,
        )

        handler.assert_not_called()
        # Should have been called twice: once error, once success
        assert redis.xreadgroup.call_count == 2

    async def test_multiple_messages_processed_in_order(
        self, settings: ConsumerSettings
    ) -> None:
        """Multiple messages in a single XREADGROUP response should all be processed."""
        handler = AsyncMock()
        redis = AsyncMock()

        event_1 = {"orderId": 1, "symbol": "AAPL"}
        event_2 = {"orderId": 2, "symbol": "MSFT"}

        msg_id_1 = b"1000-0"
        msg_id_2 = b"1001-0"

        redis.xreadgroup = AsyncMock(side_effect=[
            [(b"stream", [
                (msg_id_1, {b"data": orjson.dumps(event_1)}),
                (msg_id_2, {b"data": orjson.dumps(event_2)}),
            ])],
            [],  # End pending phase
        ])
        redis.xack = AsyncMock()

        shutdown = asyncio.Event()

        await _read_and_process(
            redis=redis,
            stream_key="tiger:events:transaction",
            group="trade-executor",
            consumer="executor-1",
            settings=settings,
            handler=handler,
            read_id="0",
            shutdown=shutdown,
        )

        assert handler.call_count == 2
        handler.assert_any_call(event_1)
        handler.assert_any_call(event_2)
        assert redis.xack.call_count == 2

    async def test_missing_data_field_uses_empty_dict(
        self, settings: ConsumerSettings
    ) -> None:
        """If message has no 'data' field, handler receives empty dict."""
        handler = AsyncMock()
        redis = AsyncMock()

        msg_id = b"1234567890-0"
        # Fields exist but no b"data" key -- some other field present
        fields = {b"other_field": b"value"}

        redis.xreadgroup = AsyncMock(side_effect=[
            [(b"stream", [(msg_id, fields)])],
            [],  # End pending phase
        ])
        redis.xack = AsyncMock()

        shutdown = asyncio.Event()

        await _read_and_process(
            redis=redis,
            stream_key="tiger:events:transaction",
            group="trade-executor",
            consumer="executor-1",
            settings=settings,
            handler=handler,
            read_id="0",
            shutdown=shutdown,
        )

        handler.assert_called_once_with({})
        redis.xack.assert_called_once()
