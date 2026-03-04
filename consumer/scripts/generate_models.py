#!/usr/bin/env python3
"""Generate Pydantic v2 models from Tiger broker event JSON schemas.

Usage::

    cd consumer
    uv run python scripts/generate_models.py

Reads the **full envelope** JSON schemas (transaction, order) from
``tiger-brokers-cash-mcp/schemas/events/`` and generates
``src/zaza_consumer/models.py`` with all four models:

- TransactionPayload, TransactionEvent  (from transaction.json)
- OrderStatusPayload, OrderStatusEvent  (from order.json)

Requires ``datamodel-code-generator`` (dev dependency).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from datamodel_code_generator import DataModelType, PythonVersion, generate
from datamodel_code_generator.enums import InputFileType

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # zaza/
SCHEMAS_DIR = REPO_ROOT / "tiger-brokers-cash-mcp" / "schemas" / "events"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "src" / "zaza_consumer" / "models.py"


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


def _generate_model_code(schema: dict) -> str:
    """Generate Pydantic v2 model code from a full envelope JSON schema.

    Uses datamodel-code-generator with:
    - snake_case field names with camelCase aliases
    - Union operator (``X | Y``) syntax for Python 3.12+
    - ``populate_by_name=True`` in ConfigDict
    - Schema titles as class names
    - Collapsed root models (no RootModel wrappers)
    """
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
        out_path = Path(tmp.name)

    try:
        generate(
            input_=json.dumps(schema),
            input_file_type=InputFileType.JsonSchema,
            output=out_path,
            output_model_type=DataModelType.PydanticV2BaseModel,
            target_python_version=PythonVersion.PY_312,
            snake_case_field=True,
            use_union_operator=True,
            use_title_as_name=True,
            allow_population_by_field_name=True,
            disable_timestamp=True,
            collapse_root_models=True,
        )
        return out_path.read_text()
    finally:
        out_path.unlink(missing_ok=True)


def _extract_imports(code: str) -> set[str]:
    """Extract all import lines from generated code."""
    imports: set[str] = set()
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            imports.add(stripped)
    return imports


def _extract_classes(code: str) -> str:
    """Extract everything after the import block (class definitions)."""
    lines = code.splitlines()
    # Find the first non-import, non-blank, non-comment line
    class_start = 0
    in_imports = True
    for i, line in enumerate(lines):
        stripped = line.strip()
        if in_imports:
            if stripped.startswith(("import ", "from ", "#")) or stripped == "":
                continue
            else:
                class_start = i
                in_imports = False
                break

    return "\n".join(lines[class_start:])


def _strip_field_titles(code: str) -> str:
    """Remove ``title='...'`` parameters from Field() calls.

    The codegen adds title= to every field which is noisy and unnecessary
    for our use case. This strips them while preserving other Field parameters.
    """
    # Remove ", title='...'" when it appears before the closing paren
    code = re.sub(r",\s*title='[^']*'\s*\)", ")", code)
    # Remove "title='...', " when it appears at the start/middle of Field args
    code = re.sub(r"title='[^']*',\s*", "", code)
    # Remove standalone "title='...'" (only arg in Field)
    code = re.sub(r"\(\s*title='[^']*'\s*\)", "()", code)
    return code


def _clean_empty_fields(code: str) -> str:
    """Replace ``Field()`` (empty) with bare default or remove entirely.

    After stripping titles, some Field() calls may become ``= Field(None)``
    which is equivalent to ``= None``, or ``= Field(...)`` which can stay.
    """
    # Field(None) -> None  (for optional fields with no other args)
    code = re.sub(r"= Field\(None\)", "= None", code)
    return code


def _strip_codegen_header(code: str) -> str:
    """Remove the ``# generated by datamodel-codegen:`` header block."""
    lines = code.splitlines()
    filtered = []
    skip = False
    for line in lines:
        if line.startswith("# generated by datamodel-codegen"):
            skip = True
            continue
        if skip and line.startswith("#   "):
            continue
        skip = False
        filtered.append(line)
    return "\n".join(filtered)


def _merge_outputs(tx_code: str, order_code: str) -> str:
    """Merge two codegen outputs with import deduplication.

    Returns a single module string with:
    - Docstring header
    - Deduplicated imports
    - Transaction models (TransactionPayload, TransactionEvent)
    - Order models (OrderStatusPayload, OrderStatusEvent)
    """
    # Strip codegen headers
    tx_code = _strip_codegen_header(tx_code)
    order_code = _strip_codegen_header(order_code)

    # Strip title= noise and clean up empty Field() calls
    tx_code = _clean_empty_fields(_strip_field_titles(tx_code))
    order_code = _clean_empty_fields(_strip_field_titles(order_code))

    # Collect and deduplicate imports
    tx_imports = _extract_imports(tx_code)
    order_imports = _extract_imports(order_code)
    all_imports = tx_imports | order_imports

    # Remove __future__ imports -- we add our own header
    all_imports = {i for i in all_imports if "from __future__" not in i}

    # Sort imports: stdlib first, then third-party
    sorted_imports = sorted(all_imports)

    # Extract class bodies
    tx_classes = _extract_classes(tx_code).strip()
    order_classes = _extract_classes(order_code).strip()

    # Build the module
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

    imports_block = "\n".join(sorted_imports)

    return (
        header
        + imports_block
        + "\n\n\n"
        + tx_classes
        + "\n\n\n"
        + order_classes
        + "\n"
    )


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

    # Load schemas and preprocess (strip format: date-time from received_at)
    tx_schema = _load_and_prepare_schema(tx_schema_path)
    order_schema = _load_and_prepare_schema(order_schema_path)

    # Generate model code from full envelope schemas
    tx_code = _generate_model_code(tx_schema)
    order_code = _generate_model_code(order_schema)

    # Merge outputs with deduplication and post-processing
    combined = _merge_outputs(tx_code, order_code)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(combined)

    # Format with ruff for consistent style
    subprocess.run(
        ["ruff", "format", str(OUTPUT_FILE)],
        check=False,
        capture_output=True,
    )

    print(f"Generated: {OUTPUT_FILE}")
    print(f"  TransactionPayload + TransactionEvent from {tx_schema_path.name}")
    print(f"  OrderStatusPayload + OrderStatusEvent from {order_schema_path.name}")


if __name__ == "__main__":
    main()
