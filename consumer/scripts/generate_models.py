#!/usr/bin/env python3
"""Generate Pydantic v2 models from Tiger broker event JSON schemas.

Usage::

    cd consumer
    uv run python scripts/generate_models.py

Reads the **full envelope** JSON schemas (transaction, order) from
``tiger-brokers-cash-mcp/schemas/events/`` and runs ``datamodel-codegen``
CLI in directory mode to produce per-schema model files under
``src/zaza_consumer/models/``.

- TransactionPayload, TransactionEvent  (from transaction.json)
- OrderStatusPayload, OrderStatusEvent  (from order.json)

Requires ``datamodel-code-generator`` (dev dependency).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # zaza/
SCHEMAS_DIR = REPO_ROOT / "tiger-brokers-cash-mcp" / "schemas" / "events"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "src" / "zaza_consumer" / "models"

INIT_CONTENT = '''\
"""Pydantic models for Tiger broker event stream messages.

Auto-generated from JSON schemas at tiger-brokers-cash-mcp/schemas/events/.
Regenerate with: uv run python scripts/generate_models.py
"""

from zaza_consumer.models.order import OrderStatusEvent, OrderStatusPayload
from zaza_consumer.models.transaction import TransactionEvent, TransactionPayload

__all__ = [
    "OrderStatusEvent",
    "OrderStatusPayload",
    "TransactionEvent",
    "TransactionPayload",
]
'''


def _load_and_prepare_schema(schema_path: Path) -> dict:
    """Load a JSON schema and strip ``format: date-time`` from ``received_at``.

    The ``received_at`` field has ``"format": "date-time"`` in the schema which
    causes datamodel-code-generator to produce ``AwareDatetime`` instead of ``str``.
    Since the consumer receives this as a plain string from Redis JSON, we want ``str``.
    """
    with open(schema_path) as f:
        schema = json.load(f)

    # Strip format from received_at to keep it as str
    props = schema.get("properties", {})
    if "received_at" in props:
        props["received_at"].pop("format", None)

    return schema


def main() -> None:
    """Generate models/ package from event JSON schemas."""
    if not SCHEMAS_DIR.exists():
        print(f"Error: schemas directory not found: {SCHEMAS_DIR}", file=sys.stderr)
        sys.exit(1)

    tx_schema_path = SCHEMAS_DIR / "transaction.json"
    order_schema_path = SCHEMAS_DIR / "order.json"

    for p in (tx_schema_path, order_schema_path):
        if not p.exists():
            print(f"Error: schema not found: {p}", file=sys.stderr)
            sys.exit(1)

    # Load schemas and preprocess (strip format: date-time from received_at)
    tx_schema = _load_and_prepare_schema(tx_schema_path)
    order_schema = _load_and_prepare_schema(order_schema_path)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_in = Path(tmp) / "in"
        tmp_out = Path(tmp) / "out"
        tmp_in.mkdir()

        # Write prepared schemas to temp input directory
        (tmp_in / "transaction.json").write_text(json.dumps(tx_schema, indent=2))
        (tmp_in / "order.json").write_text(json.dumps(order_schema, indent=2))

        # Run datamodel-codegen CLI in directory mode
        result = subprocess.run(
            [
                "datamodel-codegen",
                "--input", str(tmp_in),
                "--output", str(tmp_out),
                "--output-model-type", "pydantic_v2.BaseModel",
                "--target-python-version", "3.12",
                "--snake-case-field",
                "--use-union-operator",
                "--use-title-as-name",
                "--allow-population-by-field-name",
                "--extra-fields", "ignore",
                "--disable-timestamp",
                "--collapse-root-models",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"Error: datamodel-codegen failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)

        # Copy generated files to output directory
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        for name in ("transaction.py", "order.py"):
            src = tmp_out / name
            if not src.exists():
                print(f"Error: expected output file not found: {src}", file=sys.stderr)
                sys.exit(1)
            shutil.copy2(src, OUTPUT_DIR / name)

    # Write barrel __init__.py
    (OUTPUT_DIR / "__init__.py").write_text(INIT_CONTENT)

    # Format with ruff for consistent style
    fmt_result = subprocess.run(
        ["ruff", "format", str(OUTPUT_DIR)],
        check=False,
        capture_output=True,
        text=True,
    )
    if fmt_result.returncode != 0:
        print(
            f"Warning: ruff format failed (exit {fmt_result.returncode}):\n{fmt_result.stderr}",
            file=sys.stderr,
        )

    print(f"Generated: {OUTPUT_DIR}/")
    print(f"  transaction.py  (TransactionPayload, TransactionEvent)")
    print(f"  order.py        (OrderStatusPayload, OrderStatusEvent)")
    print(f"  __init__.py     (barrel re-exports)")


if __name__ == "__main__":
    main()
