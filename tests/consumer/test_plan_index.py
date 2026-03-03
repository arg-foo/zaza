"""Tests for PlanIndex and PlanLocks."""

from __future__ import annotations

import asyncio

from zaza.consumer.plan_index import PlanIndex, PlanLocks

PLAN_XML_WITH_NUMERIC_IDS = '''
<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC">
  <summary><side>BUY</side><ticker>AAPL</ticker><quantity>50</quantity></summary>
  <entry>
    <strategy>support_bounce</strategy>
    <trigger>Price holds above $183.50</trigger>
    <limit-order>
      <order_id>12345</order_id>
      <type>LIMIT</type><side>BUY</side><ticker>AAPL</ticker>
      <quantity>50</quantity><limit_price>184.00</limit_price>
      <time_in_force>DAY</time_in_force>
    </limit-order>
  </entry>
  <exit>
    <stop-loss>
      <limit-order>
        <order_id>12346</order_id>
        <type>STOP_LIMIT</type><side>SELL</side><ticker>AAPL</ticker>
        <quantity>50</quantity><limit_price>179.50</limit_price>
        <time_in_force>DAY</time_in_force>
      </limit-order>
    </stop-loss>
    <take-profit>
      <limit-order>
        <order_id>12347</order_id>
        <type>LIMIT</type><side>SELL</side><ticker>AAPL</ticker>
        <quantity>50</quantity><limit_price>194.50</limit_price>
        <time_in_force>DAY</time_in_force>
      </limit-order>
    </take-profit>
  </exit>
</trade-plan>
'''

PLAN_XML_WITH_PLACEHOLDER_IDS = '''
<trade-plan ticker="MSFT" generated="2026-02-25 10:00 UTC">
  <summary><side>BUY</side><ticker>MSFT</ticker><quantity>30</quantity></summary>
  <entry>
    <strategy>breakout</strategy>
    <trigger>Price breaks $400</trigger>
    <limit-order>
      <order_id>BUY-MSFT-001</order_id>
      <type>LIMIT</type><side>BUY</side><ticker>MSFT</ticker>
      <quantity>30</quantity><limit_price>400.00</limit_price>
      <time_in_force>DAY</time_in_force>
    </limit-order>
  </entry>
  <exit>
    <stop-loss>
      <limit-order>
        <order_id>SOME_ORDER_ID</order_id>
        <type>STOP_LIMIT</type><side>SELL</side><ticker>MSFT</ticker>
        <quantity>30</quantity><limit_price>395.00</limit_price>
        <time_in_force>DAY</time_in_force>
      </limit-order>
    </stop-loss>
    <take-profit>
      <limit-order>
        <order_id>SOME_ORDER_ID</order_id>
        <type>LIMIT</type><side>SELL</side><ticker>MSFT</ticker>
        <quantity>30</quantity><limit_price>410.00</limit_price>
        <time_in_force>DAY</time_in_force>
      </limit-order>
    </take-profit>
  </exit>
</trade-plan>
'''


class TestRebuild:
    """Tests for PlanIndex.rebuild()."""

    def test_rebuild_with_numeric_ids(self) -> None:
        """Rebuild with numeric IDs indexes all 3 order roles."""
        idx = PlanIndex()
        idx.rebuild([("plan-001", PLAN_XML_WITH_NUMERIC_IDS)])

        assert len(idx) == 3
        assert idx.lookup(12345) == ("plan-001", "entry")
        assert idx.lookup(12346) == ("plan-001", "stop_loss")
        assert idx.lookup(12347) == ("plan-001", "take_profit")

    def test_rebuild_with_placeholder_ids(self) -> None:
        """Rebuild with non-numeric IDs indexes 0 entries."""
        idx = PlanIndex()
        idx.rebuild([("plan-002", PLAN_XML_WITH_PLACEHOLDER_IDS)])

        assert len(idx) == 0

    def test_rebuild_mixed_plans(self) -> None:
        """Rebuild with mixed plans indexes only numeric order_ids."""
        idx = PlanIndex()
        idx.rebuild([
            ("plan-001", PLAN_XML_WITH_NUMERIC_IDS),
            ("plan-002", PLAN_XML_WITH_PLACEHOLDER_IDS),
        ])

        assert len(idx) == 3
        assert idx.lookup(12345) == ("plan-001", "entry")
        assert idx.lookup(12346) == ("plan-001", "stop_loss")
        assert idx.lookup(12347) == ("plan-001", "take_profit")

    def test_rebuild_clears_previous(self) -> None:
        """Calling rebuild again clears old entries before re-indexing."""
        idx = PlanIndex()
        idx.rebuild([("plan-001", PLAN_XML_WITH_NUMERIC_IDS)])
        assert len(idx) == 3

        # Rebuild with only placeholder IDs -- old entries must be gone.
        idx.rebuild([("plan-002", PLAN_XML_WITH_PLACEHOLDER_IDS)])
        assert len(idx) == 0
        assert idx.lookup(12345) is None


class TestLookup:
    """Tests for PlanIndex.lookup()."""

    def test_lookup_found(self) -> None:
        """Lookup existing order_id returns (plan_id, role)."""
        idx = PlanIndex()
        idx.rebuild([("plan-001", PLAN_XML_WITH_NUMERIC_IDS)])

        result = idx.lookup(12345)
        assert result == ("plan-001", "entry")

    def test_lookup_not_found(self) -> None:
        """Lookup missing order_id returns None."""
        idx = PlanIndex()
        idx.rebuild([("plan-001", PLAN_XML_WITH_NUMERIC_IDS)])

        assert idx.lookup(99999) is None


class TestAdd:
    """Tests for PlanIndex.add()."""

    def test_add(self) -> None:
        """Add entry and verify lookup returns it."""
        idx = PlanIndex()
        idx.add(55555, "plan-099", "entry")

        assert len(idx) == 1
        assert idx.lookup(55555) == ("plan-099", "entry")


class TestRemove:
    """Tests for PlanIndex.remove()."""

    def test_remove(self) -> None:
        """Remove entry and verify it is gone."""
        idx = PlanIndex()
        idx.rebuild([("plan-001", PLAN_XML_WITH_NUMERIC_IDS)])
        assert idx.lookup(12345) is not None

        idx.remove(12345)
        assert idx.lookup(12345) is None
        assert len(idx) == 2  # other two remain

    def test_remove_nonexistent(self) -> None:
        """Remove nonexistent order_id is a no-op (no error)."""
        idx = PlanIndex()
        idx.remove(99999)  # should not raise
        assert len(idx) == 0


class TestRemovePlan:
    """Tests for PlanIndex.remove_plan()."""

    def test_remove_plan(self) -> None:
        """remove_plan removes ALL entries for that plan_id."""
        idx = PlanIndex()
        idx.rebuild([
            ("plan-001", PLAN_XML_WITH_NUMERIC_IDS),
        ])
        # Add an entry from a different plan to verify it survives.
        idx.add(99999, "plan-other", "entry")
        assert len(idx) == 4

        idx.remove_plan("plan-001")

        assert len(idx) == 1
        assert idx.lookup(12345) is None
        assert idx.lookup(12346) is None
        assert idx.lookup(12347) is None
        assert idx.lookup(99999) == ("plan-other", "entry")


class TestLen:
    """Tests for PlanIndex.__len__()."""

    def test_len(self) -> None:
        """__len__ returns correct count."""
        idx = PlanIndex()
        assert len(idx) == 0

        idx.rebuild([("plan-001", PLAN_XML_WITH_NUMERIC_IDS)])
        assert len(idx) == 3

        idx.add(88888, "plan-x", "stop_loss")
        assert len(idx) == 4

        idx.remove(88888)
        assert len(idx) == 3


# ---------------------------------------------------------------------------
# PlanLocks tests
# ---------------------------------------------------------------------------


class TestPlanLocks:
    """Tests for PlanLocks per-plan_id lock manager."""

    def test_get_returns_same_lock_for_same_plan(self) -> None:
        """get() returns the same lock for the same plan_id."""
        locks = PlanLocks()
        lock_a = locks.get("plan-001")
        lock_b = locks.get("plan-001")
        assert lock_a is lock_b

    def test_get_returns_different_locks_for_different_plans(self) -> None:
        """get() returns different locks for different plan_ids."""
        locks = PlanLocks()
        lock_a = locks.get("plan-001")
        lock_b = locks.get("plan-002")
        assert lock_a is not lock_b

    def test_get_returns_asyncio_lock(self) -> None:
        """get() returns an asyncio.Lock instance."""
        locks = PlanLocks()
        lock = locks.get("plan-001")
        assert isinstance(lock, asyncio.Lock)

    def test_remove_deletes_lock(self) -> None:
        """remove() deletes the lock; next get() returns a new one."""
        locks = PlanLocks()
        lock_old = locks.get("plan-001")
        locks.remove("plan-001")
        lock_new = locks.get("plan-001")
        assert lock_old is not lock_new

    def test_remove_nonexistent_is_noop(self) -> None:
        """remove() for a nonexistent plan_id is a no-op."""
        locks = PlanLocks()
        locks.remove("plan-nonexistent")  # should not raise
