"""One-time migration script for trade plan XML schema.

Migrates trade plan XML files from the old flat schema to the new
<order>-wrapped schema:

1. Wraps <entry> and <exit> in an <order> element.
2. Moves <order_id> from entry's <limit-order> to <order> level.
3. Adds <status>PENDING</status> to <entry>.
4. Adds <stop_price> to stop-loss <limit-order> with type=STOP_LIMIT
   (defaults to same value as <limit_price> if not present).
5. Removes <order_id> from ALL <limit-order> elements.

Usage:
    uv run python scripts/migrate_trade_plans.py
    uv run python scripts/migrate_trade_plans.py --dry-run
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

# Default trade plan directories
DEFAULT_ACTIVE_DIR = Path.home() / ".zaza" / "trades" / "active"
DEFAULT_ARCHIVE_DIR = Path.home() / ".zaza" / "trades" / "archive"


def migrate_xml(xml_string: str) -> tuple[str, list[str]]:
    """Migrate a single trade plan XML string to the new schema.

    Args:
        xml_string: The original XML content.

    Returns:
        Tuple of (migrated_xml_string, list_of_changes).
        If already migrated or unparseable, returns (original, []).
    """
    changes: list[str] = []

    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as exc:
        return xml_string, [f"SKIP: XML parse error: {exc}"]

    if root.tag != "trade-plan":
        return xml_string, ["SKIP: Root is not <trade-plan>"]

    # Check if already migrated (has <order> wrapper)
    if root.find("order") is not None:
        return xml_string, ["SKIP: Already migrated (has <order> element)"]

    entry = root.find("entry")
    exit_elem = root.find("exit")

    if entry is None and exit_elem is None:
        return xml_string, ["SKIP: No <entry> or <exit> to migrate"]

    # Extract order_id from entry's limit-order before removing
    order_id_text = ""
    if entry is not None:
        entry_lo = entry.find("limit-order")
        if entry_lo is not None:
            oid_elem = entry_lo.find("order_id")
            if oid_elem is not None and oid_elem.text:
                order_id_text = oid_elem.text.strip()

    # Create <order> element
    order = ET.SubElement(root, "order")

    # Add <order_id>
    if order_id_text:
        oid = ET.SubElement(order, "order_id")
        oid.text = order_id_text
        changes.append(f"Moved order_id '{order_id_text}' to <order>")
    else:
        oid = ET.SubElement(order, "order_id")
        oid.text = "MIGRATED-UNKNOWN"
        changes.append("Added placeholder order_id 'MIGRATED-UNKNOWN'")

    # Move <entry> into <order>
    if entry is not None:
        root.remove(entry)
        order.append(entry)

        # Add <status>PENDING</status> to <entry>
        if entry.find("status") is None:
            status = ET.Element("status")
            status.text = "PENDING"
            entry.insert(0, status)
            changes.append("Added <status>PENDING</status> to <entry>")

        # Remove <order_id> from entry's limit-order
        entry_lo = entry.find("limit-order")
        if entry_lo is not None:
            oid_elem = entry_lo.find("order_id")
            if oid_elem is not None:
                entry_lo.remove(oid_elem)
                changes.append("Removed <order_id> from entry <limit-order>")

    # Move <exit> into <order>
    if exit_elem is not None:
        root.remove(exit_elem)
        order.append(exit_elem)

        # Process stop-loss: add <stop_price> for STOP_LIMIT orders
        stop_loss = exit_elem.find("stop-loss")
        if stop_loss is not None:
            sl_lo = stop_loss.find("limit-order")
            if sl_lo is not None:
                # Remove <order_id>
                sl_oid = sl_lo.find("order_id")
                if sl_oid is not None:
                    sl_lo.remove(sl_oid)
                    changes.append("Removed <order_id> from stop-loss <limit-order>")

                # Add <stop_price> for STOP_LIMIT if missing
                type_elem = sl_lo.find("type")
                if (
                    type_elem is not None
                    and type_elem.text
                    and type_elem.text.strip() == "STOP_LIMIT"
                ):
                    if sl_lo.find("stop_price") is None:
                        limit_price_elem = sl_lo.find("limit_price")
                        default_stop = (
                            limit_price_elem.text
                            if limit_price_elem is not None and limit_price_elem.text
                            else "0.00"
                        )
                        stop_price = ET.Element("stop_price")
                        stop_price.text = default_stop
                        # Insert before limit_price
                        if limit_price_elem is not None:
                            idx = list(sl_lo).index(limit_price_elem)
                            sl_lo.insert(idx, stop_price)
                        else:
                            sl_lo.append(stop_price)
                        changes.append(
                            f"Added <stop_price>{default_stop}</stop_price> to stop-loss"
                        )

        # Process take-profit: remove <order_id>
        take_profit = exit_elem.find("take-profit")
        if take_profit is not None:
            tp_lo = take_profit.find("limit-order")
            if tp_lo is not None:
                tp_oid = tp_lo.find("order_id")
                if tp_oid is not None:
                    tp_lo.remove(tp_oid)
                    changes.append("Removed <order_id> from take-profit <limit-order>")

    # Serialize back
    ET.indent(root, space="  ")
    migrated = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return migrated, changes


def _atomic_write(path: Path, content: str) -> None:
    """Write content atomically using temp file + rename."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=path.parent,
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    ) as fd:
        tmp_path = Path(fd.name)
        fd.write(content)

    try:
        tmp_path.rename(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def migrate_directory(directory: Path, *, dry_run: bool = False) -> list[dict]:
    """Migrate all XML files in a directory.

    Args:
        directory: Path to the directory containing XML files.
        dry_run: If True, report changes without writing.

    Returns:
        List of dicts with 'file', 'changes', 'status' keys.
    """
    results: list[dict] = []

    if not directory.exists():
        return results

    for xml_file in sorted(directory.glob("*.xml")):
        original = xml_file.read_text(encoding="utf-8")
        migrated, changes = migrate_xml(original)

        if not changes:
            results.append(
                {"file": str(xml_file), "changes": [], "status": "no_changes"}
            )
            continue

        # Check if all changes are SKIPs
        if all(c.startswith("SKIP:") for c in changes):
            results.append(
                {"file": str(xml_file), "changes": changes, "status": "skipped"}
            )
            continue

        if dry_run:
            results.append(
                {"file": str(xml_file), "changes": changes, "status": "dry_run"}
            )
        else:
            # Backup original
            backup_path = xml_file.with_suffix(".xml.bak")
            shutil.copy2(str(xml_file), str(backup_path))

            # Write migrated
            _atomic_write(xml_file, migrated)
            results.append(
                {"file": str(xml_file), "changes": changes, "status": "migrated"}
            )

    return results


def main() -> None:
    """Run the migration."""
    parser = argparse.ArgumentParser(
        description="Migrate trade plan XML files to the new <order>-wrapped schema."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes without writing files.",
    )
    parser.add_argument(
        "--active-dir",
        type=Path,
        default=DEFAULT_ACTIVE_DIR,
        help=f"Active trades directory (default: {DEFAULT_ACTIVE_DIR})",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=DEFAULT_ARCHIVE_DIR,
        help=f"Archive trades directory (default: {DEFAULT_ARCHIVE_DIR})",
    )
    args = parser.parse_args()

    total_migrated = 0
    total_skipped = 0

    for label, directory in [("active", args.active_dir), ("archive", args.archive_dir)]:
        print(f"\n--- Migrating {label}: {directory} ---")

        if not directory.exists():
            print(f"  Directory does not exist, skipping.")
            continue

        results = migrate_directory(directory, dry_run=args.dry_run)

        if not results:
            print(f"  No XML files found.")
            continue

        for r in results:
            status = r["status"]
            fname = Path(r["file"]).name
            if status == "migrated":
                print(f"  MIGRATED: {fname}")
                for c in r["changes"]:
                    print(f"    - {c}")
                total_migrated += 1
            elif status == "dry_run":
                print(f"  WOULD MIGRATE: {fname}")
                for c in r["changes"]:
                    print(f"    - {c}")
                total_migrated += 1
            elif status == "skipped":
                print(f"  SKIPPED: {fname} ({r['changes'][0]})")
                total_skipped += 1
            else:
                print(f"  NO CHANGES: {fname}")
                total_skipped += 1

    print(f"\nDone. Migrated: {total_migrated}, Skipped: {total_skipped}")
    if args.dry_run:
        print("(Dry run - no files were modified)")


if __name__ == "__main__":
    main()
