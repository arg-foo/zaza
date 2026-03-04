"""Tests for Pydantic event models."""

from __future__ import annotations

import orjson

from zaza_consumer.models import (
    OrderStatusEvent,
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
        """All fields default to None -- empty payload is valid."""
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

    def test_extra_fields_ignored(self) -> None:
        """Unknown broker fields (future protobuf additions) are silently ignored."""
        raw = b'{"orderId": "1", "symbol": "AAPL", "unknownFutureField": 42}'
        p = TransactionPayload.model_validate_json(raw)
        assert p.order_id == "1"
        assert p.symbol == "AAPL"
        # The unknown field should not be stored on the model
        assert not hasattr(p, "unknownFutureField")
        assert not hasattr(p, "unknown_future_field")

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

    def test_extra_fields_ignored(self) -> None:
        """Unknown broker fields (future protobuf additions) are silently ignored."""
        raw = b'{"symbol": "AAPL", "orderType": "LMT", "unknownFutureField": 42}'
        p = OrderStatusPayload.model_validate_json(raw)
        assert p.symbol == "AAPL"
        assert p.order_type == "LMT"
        assert not hasattr(p, "unknownFutureField")
        assert not hasattr(p, "unknown_future_field")

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

    def test_validate_from_json(self) -> None:
        """Deserializes a well-formed event JSON (single data field from Redis)."""
        event_json = orjson.dumps(
            {
                "account": "DU12345",
                "timestamp": "1709000000000",
                "received_at": "2026-01-01T00:00:00Z",
                "payload": {
                    "orderId": "12345",
                    "symbol": "AAPL",
                    "filledQuantity": 50,
                },
            }
        )
        event = TransactionEvent.model_validate_json(event_json)
        assert event.account == "DU12345"
        assert event.timestamp == "1709000000000"
        assert event.received_at == "2026-01-01T00:00:00Z"
        assert event.payload.order_id == "12345"
        assert event.payload.symbol == "AAPL"
        assert event.payload.filled_quantity == 50

    def test_received_at_is_str(self) -> None:
        """received_at is str, not datetime (consumer receives string from Redis)."""
        event = TransactionEvent(
            account="DU12345",
            received_at="2026-01-01T00:00:00Z",
            payload=TransactionPayload(),
        )
        assert isinstance(event.received_at, str)
        assert event.received_at == "2026-01-01T00:00:00Z"

    def test_null_timestamp(self) -> None:
        """Null timestamp is allowed."""
        event_json = orjson.dumps(
            {
                "account": "DU12345",
                "timestamp": None,
                "received_at": "2026-01-01T00:00:00Z",
                "payload": {},
            }
        )
        event = TransactionEvent.model_validate_json(event_json)
        assert event.timestamp is None

    def test_missing_timestamp_defaults_to_none(self) -> None:
        """Omitted timestamp defaults to None."""
        event_json = orjson.dumps(
            {
                "account": "DU12345",
                "received_at": "2026-01-01T00:00:00Z",
                "payload": {},
            }
        )
        event = TransactionEvent.model_validate_json(event_json)
        assert event.timestamp is None

    def test_payload_is_transaction_payload_instance(self) -> None:
        """Payload is deserialized as TransactionPayload, not raw dict."""
        event_json = orjson.dumps(
            {
                "account": "DU12345",
                "received_at": "2026-01-01T00:00:00Z",
                "payload": {"orderId": "1"},
            }
        )
        event = TransactionEvent.model_validate_json(event_json)
        assert isinstance(event.payload, TransactionPayload)

    def test_empty_payload_produces_default_fields(self) -> None:
        """Empty payload dict produces TransactionPayload with all None fields."""
        event_json = orjson.dumps(
            {
                "account": "DU12345",
                "received_at": "2026-01-01T00:00:00Z",
                "payload": {},
            }
        )
        event = TransactionEvent.model_validate_json(event_json)
        assert event.payload.order_id is None
        assert event.payload.symbol is None


# ---------------------------------------------------------------------------
# OrderStatusEvent envelope
# ---------------------------------------------------------------------------


class TestOrderStatusEvent:
    """Tests for OrderStatusEvent envelope model."""

    def test_validate_from_json(self) -> None:
        """Deserializes a well-formed event JSON."""
        event_json = orjson.dumps(
            {
                "account": "DU12345",
                "timestamp": "1709000000000",
                "received_at": "2026-01-01T00:00:00Z",
                "payload": {
                    "symbol": "AAPL",
                    "orderType": "LMT",
                    "status": "FILLED",
                },
            }
        )
        event = OrderStatusEvent.model_validate_json(event_json)
        assert event.account == "DU12345"
        assert isinstance(event.payload, OrderStatusPayload)
        assert event.payload.symbol == "AAPL"
        assert event.payload.order_type == "LMT"
        assert event.payload.status == "FILLED"

    def test_received_at_is_str(self) -> None:
        """received_at is str, not datetime."""
        event = OrderStatusEvent(
            account="DU12345",
            received_at="2026-01-01T00:00:00Z",
            payload=OrderStatusPayload(),
        )
        assert isinstance(event.received_at, str)

    def test_empty_payload(self) -> None:
        """Empty payload produces OrderStatusPayload with all None fields."""
        event_json = orjson.dumps(
            {
                "account": "DU12345",
                "received_at": "2026-01-01T00:00:00Z",
                "payload": {},
            }
        )
        event = OrderStatusEvent.model_validate_json(event_json)
        assert event.payload.symbol is None

    def test_null_timestamp(self) -> None:
        """Null timestamp is allowed."""
        event_json = orjson.dumps(
            {
                "account": "DU12345",
                "timestamp": None,
                "received_at": "2026-01-01T00:00:00Z",
                "payload": {},
            }
        )
        event = OrderStatusEvent.model_validate_json(event_json)
        assert event.timestamp is None
