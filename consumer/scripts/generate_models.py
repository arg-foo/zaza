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

    with tempfile.TemporaryDirectory() as tmp:
        tmp_in = Path(tmp) / "in"
        tmp_out = Path(tmp) / "out"
        tmp_in.mkdir()

        # Copy schemas to temp input directory
        shutil.copy2(tx_schema_path, tmp_in / "transaction.json")
        shutil.copy2(order_schema_path, tmp_in / "order.json")

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
