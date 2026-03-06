"""Tests for the trade plan XML migration script.

Tests the migrate_xml() function and migrate_directory() for the
old-to-new schema migration (flat entry/exit to <order>-wrapped).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from scripts.migrate_trade_plans import migrate_directory, migrate_xml

# Old-schema XML for testing migration
OLD_SCHEMA_XML = """\
<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC">
  <summary>
    <side>BUY</side>
    <ticker>AAPL</ticker>
    <quantity>50</quantity>
  </summary>
  <entry>
    <strategy>support_bounce</strategy>
    <trigger>Price holds above $183.50</trigger>
    <limit-order>
      <order_id>BUY-AAPL-20260224-001</order_id>
      <type>LIMIT</type>
      <side>BUY</side>
      <ticker>AAPL</ticker>
      <quantity>50</quantity>
      <limit_price>184.00</limit_price>
      <time_in_force>DAY</time_in_force>
    </limit-order>
  </entry>
  <exit>
    <stop-loss>
      <limit-order>
        <order_id>BUY-AAPL-20260224-001-SL</order_id>
        <type>STOP_LIMIT</type>
        <side>SELL</side>
        <ticker>AAPL</ticker>
        <quantity>50</quantity>
        <limit_price>179.50</limit_price>
        <time_in_force>GTC</time_in_force>
      </limit-order>
    </stop-loss>
    <take-profit>
      <limit-order>
        <order_id>BUY-AAPL-20260224-001-TP</order_id>
        <type>LIMIT</type>
        <side>SELL</side>
        <ticker>AAPL</ticker>
        <quantity>50</quantity>
        <limit_price>194.50</limit_price>
        <time_in_force>GTC</time_in_force>
      </limit-order>
    </take-profit>
  </exit>
</trade-plan>
"""

# Already-migrated XML (new schema)
NEW_SCHEMA_XML = """\
<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC">
  <summary>
    <side>BUY</side>
    <ticker>AAPL</ticker>
    <quantity>50</quantity>
  </summary>
  <order>
    <order_id>BUY-AAPL-20260224-001</order_id>
    <entry>
      <status>PENDING</status>
      <strategy>support_bounce</strategy>
      <trigger>Price holds above $183.50</trigger>
      <limit-order>
        <type>LIMIT</type>
        <side>BUY</side>
        <ticker>AAPL</ticker>
        <quantity>50</quantity>
        <limit_price>184.00</limit_price>
        <time_in_force>DAY</time_in_force>
      </limit-order>
    </entry>
    <exit>
      <stop-loss>
        <limit-order>
          <type>STOP_LIMIT</type>
          <side>SELL</side>
          <ticker>AAPL</ticker>
          <quantity>50</quantity>
          <stop_price>179.50</stop_price>
          <limit_price>179.50</limit_price>
          <time_in_force>GTC</time_in_force>
        </limit-order>
      </stop-loss>
      <take-profit>
        <limit-order>
          <type>LIMIT</type>
          <side>SELL</side>
          <ticker>AAPL</ticker>
          <quantity>50</quantity>
          <limit_price>194.50</limit_price>
          <time_in_force>GTC</time_in_force>
        </limit-order>
      </take-profit>
    </exit>
  </order>
</trade-plan>
"""


class TestMigrateXml:
    """Tests for the migrate_xml() function."""

    def test_migrate_wraps_entry_exit_in_order(self) -> None:
        """Entry and exit elements are wrapped in an <order> element."""
        migrated, changes = migrate_xml(OLD_SCHEMA_XML)
        root = ET.fromstring(migrated)
        order = root.find("order")
        assert order is not None
        assert order.find("entry") is not None
        assert order.find("exit") is not None
        # entry/exit should NOT exist at root level
        assert root.find("entry") is None
        assert root.find("exit") is None

    def test_migrate_moves_order_id_to_order(self) -> None:
        """order_id is moved from entry's limit-order to <order> level."""
        migrated, changes = migrate_xml(OLD_SCHEMA_XML)
        root = ET.fromstring(migrated)
        order = root.find("order")
        oid = order.find("order_id")
        assert oid is not None
        assert oid.text == "BUY-AAPL-20260224-001"

    def test_migrate_removes_order_id_from_limit_orders(self) -> None:
        """order_id is removed from all limit-order elements."""
        migrated, changes = migrate_xml(OLD_SCHEMA_XML)
        root = ET.fromstring(migrated)
        # Check all limit-orders have no order_id
        for lo in root.iter("limit-order"):
            assert lo.find("order_id") is None

    def test_migrate_adds_status_pending(self) -> None:
        """<status>PENDING</status> is added to <entry>."""
        migrated, changes = migrate_xml(OLD_SCHEMA_XML)
        root = ET.fromstring(migrated)
        entry = root.find("order/entry")
        status = entry.find("status")
        assert status is not None
        assert status.text == "PENDING"

    def test_migrate_adds_stop_price_for_stop_limit(self) -> None:
        """<stop_price> is added to STOP_LIMIT limit-orders."""
        migrated, changes = migrate_xml(OLD_SCHEMA_XML)
        root = ET.fromstring(migrated)
        sl_lo = root.find("order/exit/stop-loss/limit-order")
        stop_price = sl_lo.find("stop_price")
        assert stop_price is not None
        # Defaults to same as limit_price
        assert stop_price.text == "179.50"

    def test_migrate_does_not_add_stop_price_for_limit_type(self) -> None:
        """<stop_price> is NOT added to LIMIT type limit-orders."""
        migrated, changes = migrate_xml(OLD_SCHEMA_XML)
        root = ET.fromstring(migrated)
        entry_lo = root.find("order/entry/limit-order")
        assert entry_lo.find("stop_price") is None
        tp_lo = root.find("order/exit/take-profit/limit-order")
        assert tp_lo.find("stop_price") is None

    def test_migrate_reports_changes(self) -> None:
        """migrate_xml returns a non-empty changes list for old schema."""
        _, changes = migrate_xml(OLD_SCHEMA_XML)
        assert len(changes) > 0
        assert any("order_id" in c for c in changes)
        assert any("status" in c.lower() for c in changes)
        assert any("stop_price" in c for c in changes)

    def test_migrate_skips_already_migrated(self) -> None:
        """Already-migrated XML is returned unchanged."""
        migrated, changes = migrate_xml(NEW_SCHEMA_XML)
        assert len(changes) == 1
        assert "Already migrated" in changes[0]

    def test_migrate_skips_malformed_xml(self) -> None:
        """Malformed XML is returned unchanged with a SKIP message."""
        original = "this is not xml <><>"
        migrated, changes = migrate_xml(original)
        assert migrated == original
        assert len(changes) == 1
        assert "SKIP" in changes[0]

    def test_migrate_rejects_xxe_case_insensitive(self) -> None:
        """XML with mixed-case DOCTYPE/ENTITY is rejected."""
        xml = '<!doctype foo [<!entity xxe "test">]><trade-plan><entry/></trade-plan>'
        migrated, changes = migrate_xml(xml)
        assert migrated == xml
        assert len(changes) == 1
        assert "SKIP" in changes[0]
        assert "DTD" in changes[0] or "entity" in changes[0].lower()

    def test_migrate_skips_non_trade_plan_root(self) -> None:
        """XML with wrong root element is skipped."""
        xml = "<not-a-trade-plan><entry/></not-a-trade-plan>"
        migrated, changes = migrate_xml(xml)
        assert migrated == xml
        assert any("SKIP" in c for c in changes)

    def test_migrated_xml_passes_new_validation(self, tmp_path: Path) -> None:
        """Migrated XML passes the new TradeXmlStore.validate()."""
        from zaza.persistence.trade_store import TradeXmlStore

        store = TradeXmlStore(
            active_dir=tmp_path / "test_active",
            archive_dir=tmp_path / "test_archive",
        )
        migrated, changes = migrate_xml(OLD_SCHEMA_XML)
        errors = store.validate(migrated)
        assert errors == [], f"Validation errors: {errors}"


class TestMigrateDirectory:
    """Tests for migrate_directory()."""

    def test_migrate_directory_processes_files(self, tmp_path: Path) -> None:
        """migrate_directory processes all XML files in a directory."""
        xml_file = tmp_path / "plan1.xml"
        xml_file.write_text(OLD_SCHEMA_XML, encoding="utf-8")

        results = migrate_directory(tmp_path)
        assert len(results) == 1
        assert results[0]["status"] == "migrated"
        assert len(results[0]["changes"]) > 0

        # Verify the file was actually modified
        migrated_content = xml_file.read_text(encoding="utf-8")
        root = ET.fromstring(migrated_content)
        assert root.find("order") is not None

    def test_migrate_directory_creates_backup(self, tmp_path: Path) -> None:
        """migrate_directory creates .xml.bak backup files."""
        xml_file = tmp_path / "plan1.xml"
        xml_file.write_text(OLD_SCHEMA_XML, encoding="utf-8")

        migrate_directory(tmp_path)

        backup = tmp_path / "plan1.xml.bak"
        assert backup.exists()
        # Backup should contain original content
        assert "<entry>" in backup.read_text(encoding="utf-8")

    def test_migrate_directory_dry_run(self, tmp_path: Path) -> None:
        """migrate_directory with dry_run=True does not modify files."""
        xml_file = tmp_path / "plan1.xml"
        xml_file.write_text(OLD_SCHEMA_XML, encoding="utf-8")

        results = migrate_directory(tmp_path, dry_run=True)
        assert len(results) == 1
        assert results[0]["status"] == "dry_run"

        # File should NOT be modified
        content = xml_file.read_text(encoding="utf-8")
        assert "<order>" not in content
        # No backup should exist
        assert not (tmp_path / "plan1.xml.bak").exists()

    def test_migrate_directory_skips_already_migrated(self, tmp_path: Path) -> None:
        """migrate_directory skips already-migrated files."""
        xml_file = tmp_path / "plan1.xml"
        xml_file.write_text(NEW_SCHEMA_XML, encoding="utf-8")

        results = migrate_directory(tmp_path)
        assert len(results) == 1
        assert results[0]["status"] == "skipped"

    def test_migrate_directory_nonexistent(self, tmp_path: Path) -> None:
        """migrate_directory returns empty list for nonexistent directory."""
        results = migrate_directory(tmp_path / "nonexistent")
        assert results == []

    def test_migrate_directory_empty(self, tmp_path: Path) -> None:
        """migrate_directory returns empty list for directory with no XML files."""
        results = migrate_directory(tmp_path)
        assert results == []

    def test_migrate_directory_multiple_files(self, tmp_path: Path) -> None:
        """migrate_directory processes multiple XML files."""
        for i in range(3):
            f = tmp_path / f"plan_{i}.xml"
            f.write_text(OLD_SCHEMA_XML, encoding="utf-8")

        results = migrate_directory(tmp_path)
        assert len(results) == 3
        assert all(r["status"] == "migrated" for r in results)
