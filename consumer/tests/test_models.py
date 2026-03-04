"""Tests for Pydantic event models."""

from __future__ import annotations

import orjson

from zaza_consumer.models import (
    OrderEvent,
    OrderStatusPayload,
    TransactionEvent,
    TransactionPayload,
)

# ---------------------------------------------------------------------------
# TransactionPayload
# ---------------------------------------------------------------------------


class TestTransactionPayload:
    """Tests for TransactionPayload model."""

    def test_construct_with_snake_case(self) -> None:
        """Can construct using snake_case field names."""
        p = TransactionPayload(
            order_id="12345",
            symbol="AAPL",
            filled_quantity=50,
            filled_price=184.00,
        )
        assert p.order_id == "12345"
        assert p.symbol == "AAPL"
        assert p.filled_quantity == 50
        assert p.filled_price == 184.00

    def test_validate_from_camel_case_json(self) -> None:
        """Can deserialize from camelCase JSON (broker format)."""
        raw = b'{"orderId": "12345", "symbol": "AAPL", "filledQuantity": 50}'
        p = TransactionPayload.model_validate_json(raw)
        assert p.order_id == "12345"
        assert p.symbol == "AAPL"
        assert p.filled_quantity == 50

    def test_all_fields_optional(self) -> None:
        """All fields default to None — empty payload is valid."""
        p = TransactionPayload()
        assert p.order_id is None
        assert p.symbol is None
        assert p.filled_quantity is None

    def test_populate_by_name_allows_both_conventions(self) -> None:
        """populate_by_name=True allows both alias and field name."""
        # snake_case
        p1 = TransactionPayload(order_id="1", filled_quantity=10)
        assert p1.order_id == "1"
        assert p1.filled_quantity == 10

        # camelCase via model_validate (dict with alias keys)
        p2 = TransactionPayload.model_validate(
            {"orderId": "2", "filledQuantity": 20}
        )
        assert p2.order_id == "2"
        assert p2.filled_quantity == 20

    def test_order_id_is_string(self) -> None:
        """orderId is a string (matches broker protobuf format)."""
        p = TransactionPayload(order_id="12345")
        assert isinstance(p.order_id, str)

    def test_all_alias_fields_present(self) -> None:
        """Ensure all aliased fields round-trip correctly."""
        data = {
            "orderId": "1",
            "segType": "SEC",
            "secType": "STK",
            "filledPrice": 100.5,
            "filledQuantity": 10,
            "createTime": 1000,
            "updateTime": 2000,
            "transactTime": 3000,
        }
        p = TransactionPayload.model_validate(data)
        assert p.seg_type == "SEC"
        assert p.sec_type == "STK"
        assert p.filled_price == 100.5
        assert p.create_time == 1000
        assert p.update_time == 2000
        assert p.transact_time == 3000


# ---------------------------------------------------------------------------
# OrderStatusPayload
# ---------------------------------------------------------------------------


class TestOrderStatusPayload:
    """Tests for OrderStatusPayload model."""

    def test_construct_with_snake_case(self) -> None:
        p = OrderStatusPayload(
            symbol="AAPL",
            order_type="LMT",
            total_quantity=100,
            filled_quantity=50,
            status="FILLED",
        )
        assert p.symbol == "AAPL"
        assert p.order_type == "LMT"
        assert p.total_quantity == 100
        assert p.filled_quantity == 50
        assert p.status == "FILLED"

    def test_validate_from_camel_case_json(self) -> None:
        raw = b'{"symbol": "TSLA", "orderType": "LMT", "totalQuantity": 10}'
        p = OrderStatusPayload.model_validate_json(raw)
        assert p.symbol == "TSLA"
        assert p.order_type == "LMT"
        assert p.total_quantity == 10

    def test_all_fields_optional(self) -> None:
        p = OrderStatusPayload()
        assert p.symbol is None
        assert p.order_type is None
        assert p.status is None

    def test_boolean_fields(self) -> None:
        p = OrderStatusPayload(
            is_long=True,
            outside_rth=False,
            can_modify=True,
            can_cancel=False,
            liquidation=True,
        )
        assert p.is_long is True
        assert p.outside_rth is False
        assert p.can_modify is True
        assert p.can_cancel is False
        assert p.liquidation is True


# ---------------------------------------------------------------------------
# TransactionEvent envelope
# ---------------------------------------------------------------------------


class TestTransactionEvent:
    """Tests for TransactionEvent envelope model."""

    def test_from_redis_fields_valid(self) -> None:
        """Deserializes a well-formed Redis stream message."""
        payload_json = orjson.dumps(
            {"orderId": "12345", "symbol": "AAPL", "filledQuantity": 50}
        )
        fields: dict[bytes, bytes] = {
            b"account": b"DU12345",
            b"timestamp": b"1709000000000",
            b"received_at": b"2026-01-01T00:00:00Z",
            b"payload": payload_json,
        }
        event = TransactionEvent.from_redis_fields(fields)
        assert event.account == "DU12345"
        assert event.timestamp == "1709000000000"
        assert event.received_at == "2026-01-01T00:00:00Z"
        assert event.payload.order_id == "12345"
        assert event.payload.symbol == "AAPL"
        assert event.payload.filled_quantity == 50

    def test_from_redis_fields_missing_payload(self) -> None:
        """Missing payload field produces empty TransactionPayload."""
        fields: dict[bytes, bytes] = {
            b"account": b"DU12345",
            b"received_at": b"2026-01-01T00:00:00Z",
        }
        event = TransactionEvent.from_redis_fields(fields)
        assert event.payload.order_id is None
        assert event.payload.symbol is None

    def test_from_redis_fields_null_timestamp(self) -> None:
        """Empty timestamp bytes become None."""
        fields: dict[bytes, bytes] = {
            b"account": b"DU12345",
            b"timestamp": b"",
            b"received_at": b"2026-01-01T00:00:00Z",
            b"payload": b"{}",
        }
        event = TransactionEvent.from_redis_fields(fields)
        assert event.timestamp is None

    def test_payload_is_transaction_payload_instance(self) -> None:
        """Payload is deserialized as TransactionPayload, not raw dict."""
        fields: dict[bytes, bytes] = {
            b"account": b"DU12345",
            b"received_at": b"2026-01-01T00:00:00Z",
            b"payload": orjson.dumps({"orderId": "1"}),
        }
        event = TransactionEvent.from_redis_fields(fields)
        assert isinstance(event.payload, TransactionPayload)


# ---------------------------------------------------------------------------
# OrderEvent envelope
# ---------------------------------------------------------------------------


class TestOrderEvent:
    """Tests for OrderEvent envelope model."""

    def test_from_redis_fields_valid(self) -> None:
        payload_json = orjson.dumps(
            {"symbol": "AAPL", "orderType": "LMT", "status": "FILLED"}
        )
        fields: dict[bytes, bytes] = {
            b"account": b"DU12345",
            b"timestamp": b"1709000000000",
            b"received_at": b"2026-01-01T00:00:00Z",
            b"payload": payload_json,
        }
        event = OrderEvent.from_redis_fields(fields)
        assert event.account == "DU12345"
        assert isinstance(event.payload, OrderStatusPayload)
        assert event.payload.symbol == "AAPL"
        assert event.payload.order_type == "LMT"
        assert event.payload.status == "FILLED"

    def test_from_redis_fields_missing_payload(self) -> None:
        fields: dict[bytes, bytes] = {
            b"account": b"DU12345",
            b"received_at": b"2026-01-01T00:00:00Z",
        }
        event = OrderEvent.from_redis_fields(fields)
        assert event.payload.symbol is None

    def test_from_redis_fields_null_timestamp(self) -> None:
        fields: dict[bytes, bytes] = {
            b"account": b"DU12345",
            b"timestamp": b"",
            b"received_at": b"2026-01-01T00:00:00Z",
            b"payload": b"{}",
        }
        event = OrderEvent.from_redis_fields(fields)
        assert event.timestamp is None
