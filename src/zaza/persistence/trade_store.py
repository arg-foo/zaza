"""Trade plan XML persistence layer.

Provides TradeXmlStore for validating, saving, loading, updating,
archiving, and deleting trade plan XML files on disk.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Required child elements for a <limit-order>
_LIMIT_ORDER_FIELDS = (
    "type",
    "side",
    "ticker",
    "quantity",
    "limit_price",
    "time_in_force",
)

# CR-02: Allowlist regex for plan_id to prevent path traversal
_PLAN_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def _safe_parse_xml(xml_string: str) -> ET.Element:
    """Parse XML safely, rejecting DTD and entity declarations.

    Checks for DOCTYPE and ENTITY patterns before parsing to prevent
    Billion Laughs and other entity expansion attacks (CR-01).

    Args:
        xml_string: The XML string to parse.

    Returns:
        The parsed root Element.

    Raises:
        ET.ParseError: If the XML contains DTD/entity declarations or is malformed.
    """
    upper = xml_string.upper()
    if "<!DOCTYPE" in upper or "<!ENTITY" in upper:
        raise ET.ParseError("DTD and entity declarations are not allowed")
    return ET.fromstring(xml_string)


class TradeXmlStore:
    """Validate, save, load, and archive trade plan XML files."""

    def __init__(self, active_dir: Path, archive_dir: Path) -> None:
        self._active_dir = active_dir
        self._archive_dir = archive_dir
        self._active_dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Plan ID validation (CR-02)
    # ------------------------------------------------------------------

    def _validate_plan_id(self, plan_id: str) -> None:
        """Validate plan_id against allowlist to prevent path traversal.

        Args:
            plan_id: The plan identifier to validate.

        Raises:
            ValueError: If the plan_id contains invalid characters.
        """
        if not _PLAN_ID_RE.match(plan_id):
            raise ValueError(f"Invalid plan_id format: {plan_id!r}")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, xml_string: str) -> list[str]:
        """Parse XML and check required elements exist.

        Returns a list of error messages. An empty list means the XML is valid.

        Required structure checks:
        - Root is <trade-plan> with ticker and generated attrs
        - Has <summary> with <side>, <ticker>, <quantity>
        - Has <order> with <order_id>, <entry>, <exit>
        - <entry> has <status>, <strategy>, <trigger>, <limit-order>
        - <limit-order> has <type>, <side>, <ticker>,
          <quantity>, <limit_price>, <time_in_force>
        - STOP_LIMIT limit-orders must also have <stop_price>
        - <exit> has <stop-loss> and <take-profit>,
          each containing <limit-order>
        """
        errors: list[str] = []

        try:
            root = _safe_parse_xml(xml_string)
        except ET.ParseError as exc:
            return [f"XML parse error: {exc}"]

        # Root element
        if root.tag != "trade-plan":
            errors.append(f"Root element must be <trade-plan>, got <{root.tag}>")
            return errors

        if not root.get("ticker"):
            errors.append("Missing required attribute 'ticker' on <trade-plan>")
        if not root.get("generated"):
            errors.append("Missing required attribute 'generated' on <trade-plan>")

        # <summary>
        summary = root.find("summary")
        if summary is None:
            errors.append("Missing required element <summary>")
        else:
            for child_tag in ("side", "ticker", "quantity"):
                if summary.find(child_tag) is None:
                    errors.append(f"Missing <{child_tag}> in <summary>")

        # <order>
        order = root.find("order")
        if order is None:
            errors.append("Missing required element <order>")
            return errors

        # <order_id> inside <order>
        order_id_elem = order.find("order_id")
        if order_id_elem is None:
            errors.append("Missing <order_id> in <order>")
        elif not order_id_elem.text or not order_id_elem.text.strip():
            errors.append("Empty <order_id> in <order>")

        # <entry> inside <order>
        entry = order.find("entry")
        if entry is None:
            errors.append("Missing required element <entry>")
        else:
            # <status> is required in <entry>
            status_elem = entry.find("status")
            if status_elem is None:
                errors.append("Missing <status> in <entry>")
            elif not status_elem.text or not status_elem.text.strip():
                errors.append("Empty <status> in <entry>")

            for child_tag in ("strategy", "trigger"):
                if entry.find(child_tag) is None:
                    errors.append(f"Missing <{child_tag}> in <entry>")
            entry_lo = entry.find("limit-order")
            if entry_lo is None:
                errors.append("Missing <limit-order> in <entry>")
            else:
                self._validate_limit_order(entry_lo, "entry", errors)

        # <exit> inside <order>
        exit_elem = order.find("exit")
        if exit_elem is None:
            errors.append("Missing required element <exit>")
        else:
            for section_tag in ("stop-loss", "take-profit"):
                section = exit_elem.find(section_tag)
                if section is None:
                    errors.append(f"Missing <{section_tag}> in <exit>")
                else:
                    lo = section.find("limit-order")
                    if lo is None:
                        errors.append(f"Missing <limit-order> in <{section_tag}>")
                    else:
                        self._validate_limit_order(lo, section_tag, errors)

        return errors

    @staticmethod
    def _validate_limit_order(
        lo: ET.Element,
        context: str,
        errors: list[str],
    ) -> None:
        """Validate that a <limit-order> element has all required fields.

        Checks both presence and non-empty text content of critical fields (CR-07).
        Additionally, STOP_LIMIT orders must have a <stop_price> element.
        """
        for field in _LIMIT_ORDER_FIELDS:
            elem = lo.find(field)
            if elem is None:
                errors.append(f"Missing <{field}> in <limit-order> ({context})")
            elif not elem.text or not elem.text.strip():
                errors.append(
                    f"Empty <{field}> in <limit-order> ({context})"
                )

        # Conditional: STOP_LIMIT orders require <stop_price>
        type_elem = lo.find("type")
        if type_elem is not None and type_elem.text and type_elem.text.strip() == "STOP_LIMIT":
            stop_price = lo.find("stop_price")
            if stop_price is None:
                errors.append(f"Missing <stop_price> in STOP_LIMIT <limit-order> ({context})")
            elif not stop_price.text or not stop_price.text.strip():
                errors.append(f"Empty <stop_price> in STOP_LIMIT <limit-order> ({context})")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(
        self,
        xml_string: str,
        plan_id: str | None = None,
    ) -> tuple[str, Path]:
        """Validate and save XML to the active directory.

        Generates plan_id in tp_YYYYMMDD_HHMMSS_ffffff format if not provided (CR-03).

        Args:
            xml_string: The trade plan XML content.
            plan_id: Optional explicit plan identifier.

        Returns:
            Tuple of (plan_id, file_path).

        Raises:
            ValueError: If XML validation fails or plan_id format is invalid.
        """
        errors = self.validate(xml_string)
        if errors:
            raise ValueError(f"Validation failed: {'; '.join(errors)}")

        if plan_id is None:
            now = datetime.now(tz=timezone.utc)
            plan_id = now.strftime("tp_%Y%m%d_%H%M%S_%f")
        else:
            self._validate_plan_id(plan_id)

        path = self._active_dir / f"{plan_id}.xml"
        self._atomic_write(path, xml_string.encode("utf-8"))

        logger.info("trade_plan_saved", plan_id=plan_id, path=str(path))
        return plan_id, path

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(self, plan_id: str) -> str | None:
        """Load XML string by plan_id from the active directory.

        Args:
            plan_id: The plan identifier.

        Returns:
            The XML string, or None if not found.

        Raises:
            ValueError: If plan_id format is invalid.
        """
        self._validate_plan_id(plan_id)
        path = self._find_file(plan_id, self._active_dir)
        if path is None:
            return None
        return path.read_text(encoding="utf-8")

    def load_all_active(self) -> list[tuple[str, str]]:
        """Return all active plans as (plan_id, xml_string) tuples."""
        results: list[tuple[str, str]] = []
        if not self._active_dir.exists():
            return results
        for f in sorted(self._active_dir.glob("*.xml")):
            plan_id = f.stem
            try:
                xml_string = f.read_text(encoding="utf-8")
                results.append((plan_id, xml_string))
            except OSError as exc:
                logger.warning(
                    "trade_plan_load_error", file=str(f), error=str(exc)
                )
        return results

    def load_all_archived(self) -> list[tuple[str, str]]:
        """Return all archived plans as (plan_id, xml_string) tuples (CR-05)."""
        results: list[tuple[str, str]] = []
        if not self._archive_dir.exists():
            return results
        for f in sorted(self._archive_dir.glob("*.xml")):
            plan_id = f.stem
            try:
                xml_string = f.read_text(encoding="utf-8")
                results.append((plan_id, xml_string))
            except OSError as exc:
                logger.warning(
                    "trade_plan_load_error", file=str(f), error=str(exc)
                )
        return results

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, plan_id: str, xml_string: str) -> Path:
        """Validate and overwrite an existing plan.

        Args:
            plan_id: The plan identifier.
            xml_string: The new XML content.

        Returns:
            The file path of the updated plan.

        Raises:
            ValueError: If XML validation fails or plan_id format is invalid.
            FileNotFoundError: If the plan_id does not exist in the active directory.
        """
        self._validate_plan_id(plan_id)
        path = self._find_file(plan_id, self._active_dir)
        if path is None:
            raise FileNotFoundError(f"Trade plan '{plan_id}' not found in active directory")

        errors = self.validate(xml_string)
        if errors:
            raise ValueError(f"Validation failed: {'; '.join(errors)}")

        self._atomic_write(path, xml_string.encode("utf-8"))
        logger.info("trade_plan_updated", plan_id=plan_id, path=str(path))
        return path

    # ------------------------------------------------------------------
    # Archive
    # ------------------------------------------------------------------

    def archive(self, plan_id: str) -> Path | None:
        """Move a plan from active/ to archive/.

        Handles destination collisions by appending _1, _2, etc. (CR-06).

        Args:
            plan_id: The plan identifier.

        Returns:
            The new path in the archive directory, or None if not found.

        Raises:
            ValueError: If plan_id format is invalid.
        """
        self._validate_plan_id(plan_id)
        src = self._find_file(plan_id, self._active_dir)
        if src is None:
            return None

        self._archive_dir.mkdir(parents=True, exist_ok=True)
        dest = self._archive_dir / src.name

        # CR-06: Handle archive file collision
        if dest.exists():
            stem = src.stem
            suffix = 1
            while dest.exists():
                dest = self._archive_dir / f"{stem}_{suffix}.xml"
                suffix += 1

        shutil.move(str(src), str(dest))
        logger.info("trade_plan_archived", plan_id=plan_id, dest=str(dest))
        return dest

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, plan_id: str) -> bool:
        """Delete a plan file.

        Args:
            plan_id: The plan identifier.

        Returns:
            True if deleted, False if not found.

        Raises:
            ValueError: If plan_id format is invalid.
        """
        self._validate_plan_id(plan_id)
        path = self._find_file(plan_id, self._active_dir)
        if path is None:
            return False
        path.unlink()
        logger.info("trade_plan_deleted", plan_id=plan_id, path=str(path))
        return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _atomic_write(self, path: Path, content: bytes) -> None:
        """Write content to path using temp file + rename for atomicity."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = tempfile.NamedTemporaryFile(
            dir=path.parent,
            suffix=".tmp",
            delete=False,
        )
        tmp_path = Path(fd.name)
        try:
            fd.write(content)
            fd.flush()
            os.fsync(fd.fileno())
            fd.close()
            tmp_path.rename(path)
        except Exception:
            fd.close()
            tmp_path.unlink(missing_ok=True)
            raise

    def _find_file(self, plan_id: str, directory: Path) -> Path | None:
        """Find XML file by plan_id in directory.

        File naming convention: {plan_id}.xml
        """
        path = directory / f"{plan_id}.xml"
        if path.exists():
            return path
        return None
