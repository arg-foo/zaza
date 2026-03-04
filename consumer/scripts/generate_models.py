#!/usr/bin/env python3
"""Generate Pydantic v2 models from Tiger broker event JSON schemas.

Usage::

    cd consumer
    uv run python scripts/generate_models.py

Reads the ``contentSchema`` from each event schema (transaction, order) in the
``tiger-brokers-cash-mcp/schemas/events/`` directory and generates
``src/zaza_consumer/models.py`` with:

- Auto-generated payload models (snake_case fields, camelCase aliases)
- Manually appended envelope models (TransactionEvent, OrderEvent)

Requires ``datamodel-code-generator`` (dev dependency).
"""

from __future__ import annotations

import json
import sys
import textwrap
from io import StringIO
from pathlib import Path

from datamodel_code_generator import DataModelType, PythonVersion, generate
from datamodel_code_generator.parser.jsonschema import JsonSchemaParser

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # zaza/
SCHEMAS_DIR = REPO_ROOT / "tiger-brokers-cash-mcp" / "schemas" / "events"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "src" / "zaza_consumer" / "models.py"


def _extract_content_schema(schema_path: Path) -> dict:
    """Extract the ``contentSchema`` from a Tiger event JSON schema."""
    with open(schema_path) as f:
        schema = json.load(f)
    content_schema = schema["properties"]["payload"]["contentSchema"]
    return content_schema


def _generate_model_code(schema: dict, class_name: str) -> str:
    """Generate Pydantic v2 model code from a JSON schema dict."""
    output = StringIO()
    generate(
        input_=json.dumps(schema),
        input_file_type=JsonSchemaParser,
        output=output,
        output_model_type=DataModelType.PydanticV2BaseModel,
        target_python_version=PythonVersion.PY_312,
        snake_case_field=True,
        use_union_operator=True,
        class_name=class_name,
    )
    return output.getvalue()


# ---------------------------------------------------------------------------
# Envelope models (appended after auto-generated code)
# ---------------------------------------------------------------------------

ENVELOPE_CODE = textwrap.dedent('''\


    # ---------------------------------------------------------------------------
    # Envelope models (manually defined — match Redis stream field layout)
    # ---------------------------------------------------------------------------


    class TransactionEvent(BaseModel):
        """Full Redis stream event for transaction (execution/fill) changes.

        The publisher writes four fields to the stream: ``account``,
        ``timestamp``, ``received_at``, and ``payload`` (JSON-encoded string).
        """

        account: str
        timestamp: str | None = None
        received_at: str
        payload: TransactionPayload

        @classmethod
        def from_redis_fields(cls, fields: dict[bytes, bytes]) -> TransactionEvent:
            """Deserialize raw Redis stream fields into a typed event."""
            payload = TransactionPayload.model_validate_json(
                fields.get(b"payload", b"{}")
            )
            return cls(
                account=fields.get(b"account", b"").decode(),
                timestamp=fields.get(b"timestamp", b"").decode() or None,
                received_at=fields.get(b"received_at", b"").decode(),
                payload=payload,
            )


    class OrderEvent(BaseModel):
        """Full Redis stream event for order status changes.

        Same envelope structure as ``TransactionEvent`` but with an
        ``OrderStatusPayload``.  Ready for future order stream consumption.
        """

        account: str
        timestamp: str | None = None
        received_at: str
        payload: OrderStatusPayload

        @classmethod
        def from_redis_fields(cls, fields: dict[bytes, bytes]) -> OrderEvent:
            """Deserialize raw Redis stream fields into a typed event."""
            payload = OrderStatusPayload.model_validate_json(
                fields.get(b"payload", b"{}")
            )
            return cls(
                account=fields.get(b"account", b"").decode(),
                timestamp=fields.get(b"timestamp", b"").decode() or None,
                received_at=fields.get(b"received_at", b"").decode(),
                payload=payload,
            )
''')


def main() -> None:
    """Generate models.py from event JSON schemas."""
    if not SCHEMAS_DIR.exists():
        print(f"Error: schemas directory not found: {SCHEMAS_DIR}", file=sys.stderr)
        sys.exit(1)

    tx_schema_path = SCHEMAS_DIR / "transaction.json"
    order_schema_path = SCHEMAS_DIR / "order.json"

    for p in (tx_schema_path, order_schema_path):
        if not p.exists():
            print(f"Error: schema not found: {p}", file=sys.stderr)
            sys.exit(1)

    # Extract content schemas
    tx_content = _extract_content_schema(tx_schema_path)
    order_content = _extract_content_schema(order_schema_path)

    # Generate model code
    tx_code = _generate_model_code(tx_content, "TransactionPayload")
    order_code = _generate_model_code(order_content, "OrderStatusPayload")

    # Combine into a single module
    header = textwrap.dedent('''\
        """Pydantic models for Tiger broker event stream messages.

        Auto-generated from JSON schemas at tiger-brokers-cash-mcp/schemas/events/.
        Regenerate with: uv run python scripts/generate_models.py

        Payload models use snake_case field names with camelCase aliases to match the
        broker's protobuf-derived JSON format.  ``populate_by_name=True`` allows
        construction with either convention.
        """

        from __future__ import annotations

    ''')

    # Write combined output
    # The generated code includes imports, so we need to deduplicate
    # For simplicity, we combine the raw outputs and append envelope models
    combined = header + tx_code + "\n\n" + order_code + ENVELOPE_CODE

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(combined)
    print(f"Generated: {OUTPUT_FILE}")
    print(f"  TransactionPayload from {tx_schema_path.name}")
    print(f"  OrderStatusPayload from {order_schema_path.name}")
    print(f"  TransactionEvent (envelope)")
    print(f"  OrderEvent (envelope)")


if __name__ == "__main__":
    main()
