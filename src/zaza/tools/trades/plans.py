"""Trade plan XML MCP tools.

Tools:
  - save_trade_plan: Validate and persist a new trade plan XML.
  - get_trade_plan: Retrieve a trade plan by ID.
  - list_trade_plans: List all trade plans with metadata.
  - update_trade_plan: Update an existing trade plan.
  - close_trade_plan: Archive a trade plan.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.config import TRADES_ACTIVE_DIR, TRADES_ARCHIVE_DIR
from zaza.persistence.trade_store import TradeXmlStore

logger = structlog.get_logger(__name__)


def _extract_metadata(plan_id: str, xml_string: str, status: str = "active") -> dict:
    """Extract ticker, side, and generated timestamp from trade plan XML.

    Returns a dict with 'corrupt': True when parsing fails (CR-09).
    """
    meta: dict = {"plan_id": plan_id, "status": status}
    try:
        root = ET.fromstring(xml_string)
        meta["ticker"] = root.get("ticker", "")
        meta["created"] = root.get("generated", "")
        summary = root.find("summary")
        if summary is not None:
            side_elem = summary.find("side")
            meta["side"] = side_elem.text if side_elem is not None else ""
        else:
            meta["side"] = ""
    except ET.ParseError:
        meta["ticker"] = ""
        meta["side"] = ""
        meta["created"] = ""
        meta["corrupt"] = True
    return meta


def register(mcp: FastMCP) -> None:
    """Register trade plan tools with the MCP server."""
    store = TradeXmlStore(
        active_dir=TRADES_ACTIVE_DIR,
        archive_dir=TRADES_ARCHIVE_DIR,
    )

    @mcp.tool()
    async def save_trade_plan(xml: str) -> str:
        """Save a new trade plan. Validates XML structure and persists to disk.

        Returns JSON with plan_id, path, status.
        """
        try:
            plan_id, path = store.save(xml)
            return json.dumps({
                "status": "ok",
                "plan_id": plan_id,
                "path": str(path),
            })
        except Exception as exc:
            logger.error("save_trade_plan_error", error=str(exc))
            return json.dumps({"status": "error", "error": str(exc)})

    @mcp.tool()
    async def get_trade_plan(plan_id: str) -> str:
        """Retrieve a trade plan by ID. Returns the raw XML string."""
        try:
            xml_string = store.load(plan_id)
            if xml_string is None:
                return json.dumps({
                    "status": "error",
                    "error": f"Trade plan '{plan_id}' not found",
                })
            return json.dumps({"status": "ok", "plan_id": plan_id, "xml": xml_string})
        except Exception as exc:
            logger.error("get_trade_plan_error", plan_id=plan_id, error=str(exc))
            return json.dumps({"status": "error", "error": str(exc)})

    @mcp.tool()
    async def list_trade_plans(include_archived: bool = False) -> str:
        """List all trade plans. Returns JSON array with plan_id, ticker, side, status, created.

        Extract ticker/side/created from the XML content.
        """
        try:
            plans: list[dict] = []

            # Active plans
            for plan_id, xml_string in store.load_all_active():
                plans.append(_extract_metadata(plan_id, xml_string, status="active"))

            # Archived plans (CR-05: use public load_all_archived)
            if include_archived:
                for plan_id, xml_string in store.load_all_archived():
                    plans.append(
                        _extract_metadata(plan_id, xml_string, status="archived")
                    )

            return json.dumps({"status": "ok", "plans": plans})
        except Exception as exc:
            logger.error("list_trade_plans_error", error=str(exc))
            return json.dumps({"status": "error", "error": str(exc)})

    @mcp.tool()
    async def update_trade_plan(plan_id: str, xml: str) -> str:
        """Update an existing trade plan with new XML. Validates and overwrites.

        Returns JSON with plan_id, path, status.
        """
        try:
            path = store.update(plan_id, xml)
            return json.dumps({
                "status": "ok",
                "plan_id": plan_id,
                "path": str(path),
            })
        except Exception as exc:
            logger.error("update_trade_plan_error", plan_id=plan_id, error=str(exc))
            return json.dumps({"status": "error", "error": str(exc)})

    @mcp.tool()
    async def close_trade_plan(plan_id: str, reason: str = "") -> str:
        """Archive a trade plan (move from active to archive).

        Persists closure reason and timestamp into the XML before archiving (CR-11).

        Returns JSON with plan_id, archived_path, reason, status.
        """
        try:
            # CR-11: Persist close reason into XML before archiving
            xml_string = store.load(plan_id)
            if xml_string is None:
                return json.dumps({
                    "status": "error",
                    "error": f"Trade plan '{plan_id}' not found",
                })

            # Add <closure> element with reason and timestamp
            root = ET.fromstring(xml_string)
            closure = ET.SubElement(root, "closure")
            reason_elem = ET.SubElement(closure, "reason")
            reason_elem.text = reason
            closed_at_elem = ET.SubElement(closure, "closed_at")
            closed_at_elem.text = datetime.now(tz=timezone.utc).isoformat()
            updated_xml = ET.tostring(root, encoding="unicode")

            # Write the updated XML back before archiving
            store.update(plan_id, updated_xml)

            archived_path = store.archive(plan_id)
            if archived_path is None:
                return json.dumps({
                    "status": "error",
                    "error": f"Trade plan '{plan_id}' not found",
                })
            return json.dumps({
                "status": "ok",
                "plan_id": plan_id,
                "archived_path": str(archived_path),
                "reason": reason,
            })
        except Exception as exc:
            logger.error("close_trade_plan_error", plan_id=plan_id, error=str(exc))
            return json.dumps({"status": "error", "error": str(exc)})
