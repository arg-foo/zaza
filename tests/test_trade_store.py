"""Tests for the TradeXmlStore persistence layer.

Tests XML validation, save/load round-trips, update, archive, and delete
operations for trade plan XML files.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import VALID_TRADE_XML


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path):
    """Create a TradeXmlStore backed by temporary directories."""
    from zaza.persistence.trade_store import TradeXmlStore

    active = tmp_path / "active"
    archive = tmp_path / "archive"
    return TradeXmlStore(active_dir=active, archive_dir=archive)


@pytest.fixture
def saved_plan(store) -> tuple[str, Path]:
    """Save a valid plan and return (plan_id, path)."""
    return store.save(VALID_TRADE_XML)


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestValidate:
    """Tests for TradeXmlStore.validate()."""

    def test_validate_valid_xml(self, store) -> None:
        """A well-formed trade plan XML passes validation with no errors."""
        errors = store.validate(VALID_TRADE_XML)
        assert errors == []

    def test_validate_missing_root_attrs(self, store) -> None:
        """Missing ticker or generated attrs on <trade-plan> produces errors."""
        xml = "<trade-plan><summary><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity></summary><order><order_id>1</order_id><entry><status>PENDING</status><strategy>s</strategy><trigger>t</trigger><limit-order><type>LIMIT</type><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>100</limit_price><time_in_force>DAY</time_in_force></limit-order></entry><exit><stop-loss><limit-order><type>STOP_LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><stop_price>91</stop_price><limit_price>90</limit_price><time_in_force>GTC</time_in_force></limit-order></stop-loss><take-profit><limit-order><type>LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>110</limit_price><time_in_force>GTC</time_in_force></limit-order></take-profit></exit></order></trade-plan>"
        errors = store.validate(xml)
        assert len(errors) > 0
        assert any("ticker" in e.lower() or "generated" in e.lower() for e in errors)

    def test_validate_missing_summary(self, store) -> None:
        """XML without <summary> element produces an error."""
        xml = '<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC"><order><order_id>1</order_id><entry><status>PENDING</status><strategy>s</strategy><trigger>t</trigger><limit-order><type>LIMIT</type><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>100</limit_price><time_in_force>DAY</time_in_force></limit-order></entry><exit><stop-loss><limit-order><type>STOP_LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><stop_price>91</stop_price><limit_price>90</limit_price><time_in_force>GTC</time_in_force></limit-order></stop-loss><take-profit><limit-order><type>LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>110</limit_price><time_in_force>GTC</time_in_force></limit-order></take-profit></exit></order></trade-plan>'
        errors = store.validate(xml)
        assert len(errors) > 0
        assert any("summary" in e.lower() for e in errors)

    def test_validate_missing_entry(self, store) -> None:
        """XML without <entry> element produces an error."""
        xml = '<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC"><summary><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity></summary><order><order_id>1</order_id><exit><stop-loss><limit-order><type>STOP_LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><stop_price>91</stop_price><limit_price>90</limit_price><time_in_force>GTC</time_in_force></limit-order></stop-loss><take-profit><limit-order><type>LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>110</limit_price><time_in_force>GTC</time_in_force></limit-order></take-profit></exit></order></trade-plan>'
        errors = store.validate(xml)
        assert len(errors) > 0
        assert any("entry" in e.lower() for e in errors)

    def test_validate_missing_exit(self, store) -> None:
        """XML without <exit> element produces an error."""
        xml = '<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC"><summary><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity></summary><order><order_id>1</order_id><entry><status>PENDING</status><strategy>s</strategy><trigger>t</trigger><limit-order><type>LIMIT</type><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>100</limit_price><time_in_force>DAY</time_in_force></limit-order></entry></order></trade-plan>'
        errors = store.validate(xml)
        assert len(errors) > 0
        assert any("exit" in e.lower() for e in errors)

    def test_validate_malformed_xml(self, store) -> None:
        """Completely malformed XML produces a parse error."""
        errors = store.validate("this is not xml at all <></>")
        assert len(errors) > 0

    def test_validate_rejects_doctype(self, store) -> None:
        """XML with DOCTYPE declaration is rejected (CR-01)."""
        xml = '<!DOCTYPE foo [<!ENTITY xxe "test">]><trade-plan ticker="AAPL" generated="now"></trade-plan>'
        errors = store.validate(xml)
        assert len(errors) > 0
        assert any("DTD" in e or "entity" in e.lower() for e in errors)

    def test_validate_rejects_entity(self, store) -> None:
        """XML with ENTITY declaration is rejected (CR-01)."""
        xml = '<!ENTITY xxe "test"><trade-plan ticker="AAPL" generated="now"></trade-plan>'
        errors = store.validate(xml)
        assert len(errors) > 0

    def test_validate_missing_order_wrapper(self, store) -> None:
        """XML with <entry>/<exit> at root level (no <order> wrapper) produces an error."""
        xml = '<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC"><summary><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity></summary><entry><status>PENDING</status><strategy>s</strategy><trigger>t</trigger><limit-order><type>LIMIT</type><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>100</limit_price><time_in_force>DAY</time_in_force></limit-order></entry><exit><stop-loss><limit-order><type>STOP_LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><stop_price>91</stop_price><limit_price>90</limit_price><time_in_force>GTC</time_in_force></limit-order></stop-loss><take-profit><limit-order><type>LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>110</limit_price><time_in_force>GTC</time_in_force></limit-order></take-profit></exit></trade-plan>'
        errors = store.validate(xml)
        assert len(errors) > 0
        assert any("order" in e.lower() for e in errors)

    def test_validate_missing_order_id_in_order(self, store) -> None:
        """XML without <order_id> inside <order> produces an error."""
        xml = '<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC"><summary><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity></summary><order><entry><status>PENDING</status><strategy>s</strategy><trigger>t</trigger><limit-order><type>LIMIT</type><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>100</limit_price><time_in_force>DAY</time_in_force></limit-order></entry><exit><stop-loss><limit-order><type>STOP_LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><stop_price>91</stop_price><limit_price>90</limit_price><time_in_force>GTC</time_in_force></limit-order></stop-loss><take-profit><limit-order><type>LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>110</limit_price><time_in_force>GTC</time_in_force></limit-order></take-profit></exit></order></trade-plan>'
        errors = store.validate(xml)
        assert len(errors) > 0
        assert any("order_id" in e for e in errors)

    def test_validate_missing_status_in_entry(self, store) -> None:
        """XML without <status> inside <entry> produces an error."""
        xml = '<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC"><summary><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity></summary><order><order_id>1</order_id><entry><strategy>s</strategy><trigger>t</trigger><limit-order><type>LIMIT</type><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>100</limit_price><time_in_force>DAY</time_in_force></limit-order></entry><exit><stop-loss><limit-order><type>STOP_LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><stop_price>91</stop_price><limit_price>90</limit_price><time_in_force>GTC</time_in_force></limit-order></stop-loss><take-profit><limit-order><type>LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>110</limit_price><time_in_force>GTC</time_in_force></limit-order></take-profit></exit></order></trade-plan>'
        errors = store.validate(xml)
        assert len(errors) > 0
        assert any("status" in e.lower() for e in errors)

    def test_validate_missing_stop_price_for_stop_limit(self, store) -> None:
        """STOP_LIMIT limit-order without <stop_price> produces an error."""
        xml = '<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC"><summary><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity></summary><order><order_id>1</order_id><entry><status>PENDING</status><strategy>s</strategy><trigger>t</trigger><limit-order><type>LIMIT</type><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>100</limit_price><time_in_force>DAY</time_in_force></limit-order></entry><exit><stop-loss><limit-order><type>STOP_LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>90</limit_price><time_in_force>GTC</time_in_force></limit-order></stop-loss><take-profit><limit-order><type>LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>110</limit_price><time_in_force>GTC</time_in_force></limit-order></take-profit></exit></order></trade-plan>'
        errors = store.validate(xml)
        assert len(errors) > 0
        assert any("stop_price" in e for e in errors)

    def test_validate_stop_price_not_required_for_limit(self, store) -> None:
        """LIMIT type limit-order does NOT require <stop_price>."""
        errors = store.validate(VALID_TRADE_XML)
        # The valid XML has a LIMIT entry order without stop_price - should pass
        assert errors == []

    def test_validate_empty_limit_order_fields(self, store) -> None:
        """Empty text in limit-order fields produces validation errors (CR-07)."""
        xml = '<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC"><summary><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity></summary><order><order_id>1</order_id><entry><status>PENDING</status><strategy>s</strategy><trigger>t</trigger><limit-order><type></type><side>BUY</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>100</limit_price><time_in_force>DAY</time_in_force></limit-order></entry><exit><stop-loss><limit-order><type>STOP_LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><stop_price>91</stop_price><limit_price>90</limit_price><time_in_force>GTC</time_in_force></limit-order></stop-loss><take-profit><limit-order><type>LIMIT</type><side>SELL</side><ticker>AAPL</ticker><quantity>10</quantity><limit_price>110</limit_price><time_in_force>GTC</time_in_force></limit-order></take-profit></exit></order></trade-plan>'
        errors = store.validate(xml)
        assert len(errors) > 0
        assert any("empty" in e.lower() and "type" in e for e in errors)


# ---------------------------------------------------------------------------
# Save / Load tests
# ---------------------------------------------------------------------------


class TestSaveAndLoad:
    """Tests for save, load, and load_all_active operations."""

    def test_save_and_load(self, store) -> None:
        """Round-trip: save then load returns identical XML."""
        plan_id, path = store.save(VALID_TRADE_XML)
        loaded = store.load(plan_id)
        assert loaded is not None
        assert loaded == VALID_TRADE_XML

    def test_save_generates_plan_id(self, store) -> None:
        """Auto-generated plan_id follows tp_YYYYMMDD_HHMMSS_ffffff format (CR-03, CR-15)."""
        plan_id, _ = store.save(VALID_TRADE_XML)
        assert plan_id.startswith("tp_")
        # CR-15: Use regex instead of fixed-length assertion
        assert re.match(r"^tp_\d{8}_\d{6}_\d+$", plan_id)

    def test_save_with_custom_plan_id(self, store) -> None:
        """Save with an explicit plan_id uses that ID."""
        plan_id, path = store.save(VALID_TRADE_XML, plan_id="custom_plan_001")
        assert plan_id == "custom_plan_001"
        assert path.name == "custom_plan_001.xml"

    def test_save_invalid_xml_raises(self, store) -> None:
        """Saving invalid XML raises ValueError."""
        with pytest.raises(ValueError):
            store.save("not valid xml")

    def test_load_nonexistent_returns_none(self, store) -> None:
        """Loading a non-existent plan_id returns None."""
        result = store.load("nonexistent_plan")
        assert result is None

    def test_load_all_active(self, store) -> None:
        """load_all_active returns all saved plans."""
        id1, _ = store.save(VALID_TRADE_XML, plan_id="plan_a")
        id2, _ = store.save(VALID_TRADE_XML, plan_id="plan_b")

        plans = store.load_all_active()
        plan_ids = [pid for pid, _ in plans]
        assert "plan_a" in plan_ids
        assert "plan_b" in plan_ids
        assert len(plans) == 2

    def test_save_creates_file_on_disk(self, store, tmp_path: Path) -> None:
        """Saved plan file exists on disk in the active directory."""
        plan_id, path = store.save(VALID_TRADE_XML)
        assert path.exists()
        assert path.suffix == ".xml"

    def test_save_duplicate_plan_id_overwrites(self, store) -> None:
        """Saving with the same plan_id overwrites the existing file (CR-16)."""
        plan_id = "dup_plan"
        store.save(VALID_TRADE_XML, plan_id=plan_id)

        updated_xml = VALID_TRADE_XML.replace(
            "<quantity>50</quantity>", "<quantity>999</quantity>"
        )
        store.save(updated_xml, plan_id=plan_id)

        loaded = store.load(plan_id)
        assert loaded is not None
        assert "<quantity>999</quantity>" in loaded

        plans = store.load_all_active()
        matching = [pid for pid, _ in plans if pid == plan_id]
        assert len(matching) == 1

    def test_save_invalid_plan_id_raises(self, store) -> None:
        """Saving with an invalid plan_id format raises ValueError (CR-02)."""
        with pytest.raises(ValueError, match="Invalid plan_id"):
            store.save(VALID_TRADE_XML, plan_id="../escape")

    def test_save_path_traversal_plan_id_raises(self, store) -> None:
        """plan_id with path separators is rejected (CR-02)."""
        with pytest.raises(ValueError, match="Invalid plan_id"):
            store.save(VALID_TRADE_XML, plan_id="../../etc/passwd")


# ---------------------------------------------------------------------------
# Update tests
# ---------------------------------------------------------------------------


class TestUpdate:
    """Tests for TradeXmlStore.update()."""

    def test_update_existing(self, store) -> None:
        """Updating an existing plan overwrites the file content."""
        plan_id, _ = store.save(VALID_TRADE_XML, plan_id="plan_update")

        # Create a slightly different XML (change quantity)
        updated_xml = VALID_TRADE_XML.replace(
            "<quantity>50</quantity>", "<quantity>100</quantity>"
        )
        path = store.update("plan_update", updated_xml)
        assert path.exists()

        loaded = store.load("plan_update")
        assert loaded is not None
        assert "<quantity>100</quantity>" in loaded

    def test_update_nonexistent_raises(self, store) -> None:
        """Updating a non-existent plan raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            store.update("nonexistent", VALID_TRADE_XML)

    def test_update_invalid_xml_raises(self, store) -> None:
        """Updating with invalid XML raises ValueError."""
        store.save(VALID_TRADE_XML, plan_id="plan_bad_update")
        with pytest.raises(ValueError):
            store.update("plan_bad_update", "not valid xml")

    def test_update_invalid_plan_id_raises(self, store) -> None:
        """Updating with invalid plan_id raises ValueError (CR-02)."""
        with pytest.raises(ValueError, match="Invalid plan_id"):
            store.update("../escape", VALID_TRADE_XML)


# ---------------------------------------------------------------------------
# Archive tests
# ---------------------------------------------------------------------------


class TestArchive:
    """Tests for TradeXmlStore.archive()."""

    def test_archive(self, store, tmp_path: Path) -> None:
        """Archive moves file from active/ to archive/ directory."""
        plan_id, active_path = store.save(VALID_TRADE_XML, plan_id="plan_arch")
        assert active_path.exists()

        archived_path = store.archive("plan_arch")
        assert archived_path is not None
        assert archived_path.exists()
        assert not active_path.exists()
        assert "archive" in str(archived_path)

    def test_archive_nonexistent(self, store) -> None:
        """Archiving a non-existent plan returns None."""
        result = store.archive("nonexistent_plan")
        assert result is None

    def test_archive_file_collision(self, store) -> None:
        """Archiving when destination already exists appends suffix (CR-06)."""
        # Save and archive a plan
        store.save(VALID_TRADE_XML, plan_id="plan_collision")
        first_archived = store.archive("plan_collision")
        assert first_archived is not None
        assert first_archived.exists()

        # Save another plan with the same id and archive it
        store.save(VALID_TRADE_XML, plan_id="plan_collision")
        second_archived = store.archive("plan_collision")
        assert second_archived is not None
        assert second_archived.exists()
        assert first_archived.exists()  # Original still there
        assert second_archived != first_archived
        assert "_1" in second_archived.stem

    def test_archive_invalid_plan_id_raises(self, store) -> None:
        """Archiving with invalid plan_id raises ValueError (CR-02)."""
        with pytest.raises(ValueError, match="Invalid plan_id"):
            store.archive("../escape")


# ---------------------------------------------------------------------------
# Delete tests
# ---------------------------------------------------------------------------


class TestDelete:
    """Tests for TradeXmlStore.delete()."""

    def test_delete(self, store) -> None:
        """Deleting an existing plan removes the file and returns True."""
        plan_id, path = store.save(VALID_TRADE_XML, plan_id="plan_del")
        assert path.exists()

        result = store.delete("plan_del")
        assert result is True
        assert not path.exists()

    def test_delete_nonexistent(self, store) -> None:
        """Deleting a non-existent plan returns False."""
        result = store.delete("nonexistent_plan")
        assert result is False

    def test_delete_invalid_plan_id_raises(self, store) -> None:
        """Deleting with invalid plan_id raises ValueError (CR-02)."""
        with pytest.raises(ValueError, match="Invalid plan_id"):
            store.delete("../escape")


# ---------------------------------------------------------------------------
# load_all_archived tests
# ---------------------------------------------------------------------------


class TestLoadAllArchived:
    """Tests for TradeXmlStore.load_all_archived()."""

    def test_load_all_archived_empty(self, store) -> None:
        """load_all_archived returns empty list when no archived plans exist."""
        assert store.load_all_archived() == []

    def test_load_all_archived_with_plans(self, store) -> None:
        """load_all_archived returns archived plans (CR-05)."""
        store.save(VALID_TRADE_XML, plan_id="plan_x")
        store.archive("plan_x")

        archived = store.load_all_archived()
        assert len(archived) == 1
        pid, xml_str = archived[0]
        assert pid == "plan_x"
        assert "<trade-plan" in xml_str


# ---------------------------------------------------------------------------
# Corrupt file handling test (CR-09)
# ---------------------------------------------------------------------------


class TestCorruptFileHandling:
    """Tests for handling corrupt XML files."""

    def test_corrupt_file_in_active_dir(self, store) -> None:
        """A corrupt XML file in active dir can still be listed via load_all_active."""
        # Write a corrupt file directly
        corrupt_path = store._active_dir / "corrupt_plan.xml"
        corrupt_path.write_text("this is not valid xml <></>", encoding="utf-8")

        plans = store.load_all_active()
        # The file is loaded as-is (it just returns raw text)
        assert len(plans) == 1
        assert plans[0][0] == "corrupt_plan"
