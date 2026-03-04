"""Verify consumer models stay in sync with Tiger MCP JSON schemas.

Reads the JSON schemas from tiger-brokers-cash-mcp/schemas/events/ and asserts
that the consumer's Pydantic model field names match exactly.  This mirrors the
schema sync test on the Tiger MCP side.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zaza_consumer.models import (
    OrderStatusEvent,
    OrderStatusPayload,
    TransactionEvent,
    TransactionPayload,
)

SCHEMAS_DIR = (
    Path(__file__).resolve().parent.parent.parent  # zaza/
    / "tiger-brokers-cash-mcp"
    / "schemas"
    / "events"
)


def _load_schema(name: str) -> dict:
    path = SCHEMAS_DIR / name
    if not path.exists():
        pytest.skip(f"Schema not found: {path}")
    with open(path) as f:
        return json.load(f)


def _schema_payload_fields(schema: dict, def_name: str) -> set[str]:
    """Extract payload field names from the ``$defs`` section of a schema."""
    defs = schema.get("$defs", {})
    payload_def = defs.get(def_name, {})
    return set(payload_def.get("properties", {}).keys())


def _schema_envelope_fields(schema: dict) -> set[str]:
    """Extract top-level envelope field names from a schema."""
    return set(schema.get("properties", {}).keys())


def _model_fields(model_cls: type) -> set[str]:
    """Get field names from a Pydantic model, using aliases where defined."""
    fields: set[str] = set()
    for name, field_info in model_cls.model_fields.items():
        # Use alias if present (camelCase), otherwise use field name
        alias = field_info.alias
        fields.add(alias if alias else name)
    return fields


def _model_required_fields(model_cls: type) -> set[str]:
    """Get required field names from a Pydantic model, using aliases where defined."""
    fields: set[str] = set()
    for name, field_info in model_cls.model_fields.items():
        if field_info.is_required():
            alias = field_info.alias
            fields.add(alias if alias else name)
    return fields


def _schema_required_fields(schema: dict) -> set[str]:
    """Extract top-level required field names from a JSON schema."""
    return set(schema.get("required", []))


def _schema_payload_required_fields(schema: dict, def_name: str) -> set[str]:
    """Extract required field names from a ``$defs`` payload section of a schema."""
    defs = schema.get("$defs", {})
    payload_def = defs.get(def_name, {})
    return set(payload_def.get("required", []))


class TestTransactionSchemaSync:
    """Verify TransactionPayload and TransactionEvent match transaction.json."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.schema = _load_schema("transaction.json")

    def test_payload_fields_match(self) -> None:
        schema_fields = _schema_payload_fields(self.schema, "TransactionPayload")
        model_fields = _model_fields(TransactionPayload)
        assert model_fields == schema_fields, (
            f"Mismatch: model-only={model_fields - schema_fields}, "
            f"schema-only={schema_fields - model_fields}"
        )

    def test_envelope_fields_match(self) -> None:
        schema_fields = _schema_envelope_fields(self.schema)
        model_fields = _model_fields(TransactionEvent)
        assert model_fields == schema_fields, (
            f"Mismatch: model-only={model_fields - schema_fields}, "
            f"schema-only={schema_fields - model_fields}"
        )

    def test_envelope_required_fields_match(self) -> None:
        """Envelope required fields must match schema's required array."""
        schema_required = _schema_required_fields(self.schema)
        model_required = _model_required_fields(TransactionEvent)
        assert model_required == schema_required, (
            f"Required mismatch: model-only={model_required - schema_required}, "
            f"schema-only={schema_required - model_required}"
        )

    def test_payload_required_fields_match(self) -> None:
        """Payload required fields must match schema's required array."""
        schema_required = _schema_payload_required_fields(
            self.schema, "TransactionPayload"
        )
        model_required = _model_required_fields(TransactionPayload)
        assert model_required == schema_required, (
            f"Required mismatch: model-only={model_required - schema_required}, "
            f"schema-only={schema_required - model_required}"
        )


class TestOrderSchemaSync:
    """Verify OrderStatusPayload and OrderStatusEvent match order.json."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.schema = _load_schema("order.json")

    def test_payload_fields_match(self) -> None:
        schema_fields = _schema_payload_fields(self.schema, "OrderStatusPayload")
        model_fields = _model_fields(OrderStatusPayload)
        assert model_fields == schema_fields, (
            f"Mismatch: model-only={model_fields - schema_fields}, "
            f"schema-only={schema_fields - model_fields}"
        )

    def test_envelope_fields_match(self) -> None:
        schema_fields = _schema_envelope_fields(self.schema)
        model_fields = _model_fields(OrderStatusEvent)
        assert model_fields == schema_fields, (
            f"Mismatch: model-only={model_fields - schema_fields}, "
            f"schema-only={schema_fields - model_fields}"
        )

    def test_envelope_required_fields_match(self) -> None:
        """Envelope required fields must match schema's required array."""
        schema_required = _schema_required_fields(self.schema)
        model_required = _model_required_fields(OrderStatusEvent)
        assert model_required == schema_required, (
            f"Required mismatch: model-only={model_required - schema_required}, "
            f"schema-only={schema_required - model_required}"
        )

    def test_payload_required_fields_match(self) -> None:
        """Payload required fields must match schema's required array."""
        schema_required = _schema_payload_required_fields(
            self.schema, "OrderStatusPayload"
        )
        model_required = _model_required_fields(OrderStatusPayload)
        assert model_required == schema_required, (
            f"Required mismatch: model-only={model_required - schema_required}, "
            f"schema-only={schema_required - model_required}"
        )
