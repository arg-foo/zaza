"""Tests for Redis stream consumer."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import orjson
import pytest

from zaza_consumer.config import ConsumerSettings
from zaza_consumer.models import TransactionPayload
from zaza_consumer.stream import _read_and_process


@pytest.fixture
def settings():
    return ConsumerSettings(
        redis_url="redis://localhost:6379/0",
        tiger_mcp_url="http://localhost:8000/mcp",
        zaza_mcp_url="http://localhost:8100/mcp",
    )


def _make_envelope(payload_dict: dict) -> dict[bytes, bytes]:
    """Build a Redis stream fields dict matching the publisher's envelope format."""
    return {
        b"account": b"DU12345",
        b"received_at": b"2026-01-01T00:00:00Z",
        b"payload": orjson.dumps(payload_dict),
    }


class TestReadAndProcess:
    """Test _read_and_process with mocked Redis."""

    async def test_processes_message_and_acks(self, settings: ConsumerSettings) -> None:
        """Should deserialize message, call handler, and XACK."""
        handler = AsyncMock()
        redis = AsyncMock()
        event_data = {"orderId": "123", "symbol": "AAPL", "filledQuantity": 50}

        msg_id = b"1234567890-0"
        fields = _make_envelope(event_data)

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

        handler.assert_called_once()
        payload = handler.call_args[0][0]
        assert isinstance(payload, TransactionPayload)
        assert payload.order_id == "123"
        assert payload.symbol == "AAPL"
        assert payload.filled_quantity == 50
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
        fields = _make_envelope({"orderId": "1"})

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

        msg_id_1 = b"1000-0"
        msg_id_2 = b"1001-0"

        redis.xreadgroup = AsyncMock(side_effect=[
            [(b"stream", [
                (msg_id_1, _make_envelope({"orderId": "1", "symbol": "AAPL"})),
                (msg_id_2, _make_envelope({"orderId": "2", "symbol": "MSFT"})),
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
        p1 = handler.call_args_list[0][0][0]
        p2 = handler.call_args_list[1][0][0]
        assert isinstance(p1, TransactionPayload)
        assert isinstance(p2, TransactionPayload)
        assert p1.order_id == "1"
        assert p2.order_id == "2"
        assert redis.xack.call_count == 2

    async def test_missing_payload_field(
        self, settings: ConsumerSettings
    ) -> None:
        """If message has no 'payload' field, handler receives empty TransactionPayload."""
        handler = AsyncMock()
        redis = AsyncMock()

        msg_id = b"1234567890-0"
        # Fields exist but no b"payload" key
        fields = {b"account": b"DU12345", b"received_at": b"2026-01-01T00:00:00Z"}

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

        handler.assert_called_once()
        payload = handler.call_args[0][0]
        assert isinstance(payload, TransactionPayload)
        assert payload.order_id is None
        redis.xack.assert_called_once()

    async def test_full_envelope_format_unwrapped(
        self, settings: ConsumerSettings
    ) -> None:
        """Contract test: envelope is unwrapped and only payload reaches handler."""
        handler = AsyncMock()
        redis = AsyncMock()

        msg_id = b"1234567890-0"
        fields = {
            b"account": b"DU12345",
            b"timestamp": b"1709000000000",
            b"received_at": b"2026-01-01T00:00:00Z",
            b"payload": orjson.dumps({
                "orderId": "100",
                "symbol": "TSLA",
                "filledQuantity": 25,
                "filledPrice": 250.0,
            }),
        }

        redis.xreadgroup = AsyncMock(side_effect=[
            [(b"stream", [(msg_id, fields)])],
            [],
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

        handler.assert_called_once()
        payload = handler.call_args[0][0]
        assert isinstance(payload, TransactionPayload)
        assert payload.order_id == "100"
        assert payload.symbol == "TSLA"
        assert payload.filled_quantity == 25
        assert payload.filled_price == 250.0

    async def test_malformed_payload_json_acks_and_skips(
        self, settings: ConsumerSettings
    ) -> None:
        """Malformed payload JSON should ACK (prevent redelivery) and skip handler."""
        handler = AsyncMock()
        redis = AsyncMock()

        msg_id = b"1234567890-0"
        # Invalid JSON in payload field
        fields = {
            b"account": b"DU12345",
            b"received_at": b"2026-01-01T00:00:00Z",
            b"payload": b"not-valid-json{{{",
        }

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

        # Handler must NOT be called (deserialization failed)
        handler.assert_not_called()
        # Message MUST be ACKed to prevent infinite redelivery
        redis.xack.assert_called_once_with(
            "tiger:events:transaction", "trade-executor", msg_id
        )
