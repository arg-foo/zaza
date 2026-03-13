"""Tests for the trade plan MCP tools.

Tests all 5 MCP tools: save_trade_plan, get_trade_plan, list_trade_plans,
update_trade_plan, close_trade_plan.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.conftest import VALID_TRADE_XML


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mcp():
    """Create a mock FastMCP that captures registered tool functions."""
    mock_mcp = MagicMock()
    registered_tools: dict[str, object] = {}

    def tool_decorator():
        def decorator(fn):
            registered_tools[fn.__name__] = fn
            return fn
        return decorator

    mock_mcp.tool = tool_decorator
    mock_mcp._registered_tools = registered_tools
    return mock_mcp


@pytest.fixture
def tools(tmp_path: Path, mcp, monkeypatch):
    """Register trade tools using tmp_path directories and return the tool functions."""
    active_dir = tmp_path / "active"
    archive_dir = tmp_path / "archive"

    monkeypatch.setattr("zaza.tools.trades.plans.TRADES_ACTIVE_DIR", active_dir)
    monkeypatch.setattr("zaza.tools.trades.plans.TRADES_ARCHIVE_DIR", archive_dir)

    from zaza.tools.trades.plans import register

    register(mcp)
    return mcp._registered_tools


# ---------------------------------------------------------------------------
# save_trade_plan tests
# ---------------------------------------------------------------------------


class TestSaveTradePlan:
    """Tests for the save_trade_plan MCP tool."""

    async def test_save_valid_xml(self, tools) -> None:
        """save_trade_plan returns ok status with plan_id for valid XML."""
        result = await tools["save_trade_plan"](xml=VALID_TRADE_XML)
        parsed = json.loads(result)
        assert parsed["status"] == "ok"
        assert "plan_id" in parsed
        assert "path" in parsed

    async def test_save_invalid_xml_returns_error(self, tools) -> None:
        """save_trade_plan returns error status for invalid XML."""
        result = await tools["save_trade_plan"](xml="not valid xml")
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "error" in parsed


# ---------------------------------------------------------------------------
# get_trade_plan tests
# ---------------------------------------------------------------------------


class TestGetTradePlan:
    """Tests for the get_trade_plan MCP tool."""

    async def test_get_existing_plan(self, tools) -> None:
        """get_trade_plan returns the XML for an existing plan."""
        save_result = json.loads(
            await tools["save_trade_plan"](xml=VALID_TRADE_XML)
        )
        plan_id = save_result["plan_id"]

        result = await tools["get_trade_plan"](plan_id=plan_id)
        parsed = json.loads(result)
        assert parsed["status"] == "ok"
        assert "<trade-plan" in parsed["xml"]

    async def test_get_nonexistent_plan(self, tools) -> None:
        """get_trade_plan returns error for a non-existent plan_id."""
        result = await tools["get_trade_plan"](plan_id="nonexistent")
        parsed = json.loads(result)
        assert parsed["status"] == "error"


# ---------------------------------------------------------------------------
# list_trade_plans tests
# ---------------------------------------------------------------------------


class TestListTradePlans:
    """Tests for the list_trade_plans MCP tool."""

    async def test_list_empty(self, tools) -> None:
        """list_trade_plans returns empty list when no plans saved."""
        result = await tools["list_trade_plans"]()
        parsed = json.loads(result)
        assert parsed["status"] == "ok"
        assert parsed["plans"] == []

    async def test_list_with_plans(self, tools) -> None:
        """list_trade_plans returns plan metadata after saving."""
        await tools["save_trade_plan"](xml=VALID_TRADE_XML)

        result = await tools["list_trade_plans"]()
        parsed = json.loads(result)
        assert parsed["status"] == "ok"
        assert len(parsed["plans"]) == 1
        plan = parsed["plans"][0]
        assert "plan_id" in plan
        assert plan["ticker"] == "AAPL"
        assert plan["side"] == "BUY"
        assert plan["position_status"] == "NONE"

    async def test_list_includes_archived(self, tools) -> None:
        """list_trade_plans with include_archived=True shows archived plans."""
        save_result = json.loads(
            await tools["save_trade_plan"](xml=VALID_TRADE_XML)
        )
        plan_id = save_result["plan_id"]
        await tools["close_trade_plan"](plan_id=plan_id, reason="test")

        # Without archived flag, list should be empty
        result_no_arch = json.loads(await tools["list_trade_plans"]())
        assert len(result_no_arch["plans"]) == 0

        # With archived flag, plan should appear
        result_with_arch = json.loads(
            await tools["list_trade_plans"](include_archived=True)
        )
        assert len(result_with_arch["plans"]) == 1
        assert result_with_arch["plans"][0]["status"] == "archived"

    async def test_list_mixed_active_and_archived(self, tools) -> None:
        """list_trade_plans shows both active and archived plans when flag set (CR-18)."""
        # Save two plans
        save1 = json.loads(await tools["save_trade_plan"](xml=VALID_TRADE_XML))
        plan_id_1 = save1["plan_id"]

        # Save second plan (slightly later)
        import time
        time.sleep(0.01)
        save2 = json.loads(await tools["save_trade_plan"](xml=VALID_TRADE_XML))
        plan_id_2 = save2["plan_id"]

        # Archive the first plan
        await tools["close_trade_plan"](plan_id=plan_id_1, reason="target hit")

        # Without archived flag: only active plan
        result = json.loads(await tools["list_trade_plans"]())
        assert len(result["plans"]) == 1
        assert result["plans"][0]["status"] == "active"

        # With archived flag: both plans
        result_all = json.loads(
            await tools["list_trade_plans"](include_archived=True)
        )
        assert len(result_all["plans"]) == 2
        statuses = {p["status"] for p in result_all["plans"]}
        assert statuses == {"active", "archived"}

    async def test_list_corrupt_file_has_corrupt_flag(self, tools, tmp_path) -> None:
        """Corrupt XML files in active dir show corrupt: True in listing (CR-09)."""
        # Write a corrupt XML file directly
        active_dir = tmp_path / "active"
        active_dir.mkdir(parents=True, exist_ok=True)
        corrupt_path = active_dir / "bad_plan.xml"
        corrupt_path.write_text("<<<not valid xml>>>", encoding="utf-8")

        result = json.loads(await tools["list_trade_plans"]())
        assert result["status"] == "ok"
        corrupt_plans = [p for p in result["plans"] if p.get("corrupt")]
        assert len(corrupt_plans) == 1
        assert corrupt_plans[0]["plan_id"] == "bad_plan"


# ---------------------------------------------------------------------------
# update_trade_plan tests
# ---------------------------------------------------------------------------


class TestUpdateTradePlan:
    """Tests for the update_trade_plan MCP tool."""

    async def test_update_existing(self, tools) -> None:
        """update_trade_plan returns ok status when updating an existing plan."""
        save_result = json.loads(
            await tools["save_trade_plan"](xml=VALID_TRADE_XML)
        )
        plan_id = save_result["plan_id"]

        updated_xml = VALID_TRADE_XML.replace(
            "<quantity>50</quantity>", "<quantity>100</quantity>"
        )
        result = await tools["update_trade_plan"](
            plan_id=plan_id, xml=updated_xml
        )
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

    async def test_update_nonexistent(self, tools) -> None:
        """update_trade_plan returns error for a non-existent plan_id."""
        result = await tools["update_trade_plan"](
            plan_id="nonexistent", xml=VALID_TRADE_XML
        )
        parsed = json.loads(result)
        assert parsed["status"] == "error"

    async def test_update_invalid_xml(self, tools) -> None:
        """update_trade_plan returns error for invalid XML."""
        save_result = json.loads(
            await tools["save_trade_plan"](xml=VALID_TRADE_XML)
        )
        plan_id = save_result["plan_id"]

        result = await tools["update_trade_plan"](
            plan_id=plan_id, xml="not valid xml"
        )
        parsed = json.loads(result)
        assert parsed["status"] == "error"


# ---------------------------------------------------------------------------
# close_trade_plan tests
# ---------------------------------------------------------------------------


class TestCloseTradePlan:
    """Tests for the close_trade_plan MCP tool."""

    async def test_close_existing(self, tools) -> None:
        """close_trade_plan archives the plan and returns ok status."""
        save_result = json.loads(
            await tools["save_trade_plan"](xml=VALID_TRADE_XML)
        )
        plan_id = save_result["plan_id"]

        result = await tools["close_trade_plan"](
            plan_id=plan_id, reason="Target hit"
        )
        parsed = json.loads(result)
        assert parsed["status"] == "ok"
        assert "archived_path" in parsed
        assert parsed["reason"] == "Target hit"

    async def test_close_nonexistent(self, tools) -> None:
        """close_trade_plan returns error for a non-existent plan_id."""
        result = await tools["close_trade_plan"](
            plan_id="nonexistent", reason="test"
        )
        parsed = json.loads(result)
        assert parsed["status"] == "error"

    async def test_close_persists_reason_in_xml(self, tools, tmp_path) -> None:
        """close_trade_plan writes closure element into XML before archiving (CR-11)."""
        save_result = json.loads(
            await tools["save_trade_plan"](xml=VALID_TRADE_XML)
        )
        plan_id = save_result["plan_id"]

        close_result = json.loads(
            await tools["close_trade_plan"](
                plan_id=plan_id, reason="Stop loss hit"
            )
        )
        assert close_result["status"] == "ok"

        # Read the archived file and check for <closure> element
        archived_path = Path(close_result["archived_path"])
        archived_xml = archived_path.read_text(encoding="utf-8")
        root = ET.fromstring(archived_xml)
        closure = root.find("closure")
        assert closure is not None
        reason_elem = closure.find("reason")
        assert reason_elem is not None
        assert reason_elem.text == "Stop loss hit"
        closed_at_elem = closure.find("closed_at")
        assert closed_at_elem is not None
        assert closed_at_elem.text  # Non-empty ISO timestamp

    async def test_close_empty_reason(self, tools, tmp_path) -> None:
        """close_trade_plan with empty reason still persists closure element (CR-17)."""
        save_result = json.loads(
            await tools["save_trade_plan"](xml=VALID_TRADE_XML)
        )
        plan_id = save_result["plan_id"]

        close_result = json.loads(
            await tools["close_trade_plan"](plan_id=plan_id, reason="")
        )
        assert close_result["status"] == "ok"

        # Read the archived file and verify closure element exists
        archived_path = Path(close_result["archived_path"])
        archived_xml = archived_path.read_text(encoding="utf-8")
        root = ET.fromstring(archived_xml)
        closure = root.find("closure")
        assert closure is not None
        reason_elem = closure.find("reason")
        assert reason_elem is not None
        # Empty reason is allowed
        closed_at_elem = closure.find("closed_at")
        assert closed_at_elem is not None


# ---------------------------------------------------------------------------
# Registration test
# ---------------------------------------------------------------------------


class TestTradesRegister:
    """Tests for the trades tools registration."""

    def test_register_creates_all_tools(self, tools) -> None:
        """register creates all 5 MCP trade tools."""
        expected_tools = {
            "save_trade_plan",
            "get_trade_plan",
            "list_trade_plans",
            "update_trade_plan",
            "close_trade_plan",
        }
        assert set(tools.keys()) == expected_tools
