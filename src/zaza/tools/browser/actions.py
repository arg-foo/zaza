"""Browser automation MCP tools -- navigate, snapshot, act, read, close.

Validates URLs (http/https only). No caching (stateful).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import structlog
from mcp.server.fastmcp import FastMCP

from zaza.tools.browser.session import BrowserSession, _default_session

logger = structlog.get_logger(__name__)

VALID_ACTIONS = {"click", "type", "press", "scroll"}


def _validate_url(url: str) -> str | None:
    """Validate URL is http or https. Returns error message or None."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return f"Invalid URL scheme '{parsed.scheme}'. Only http and https are allowed."
        if not parsed.netloc:
            return "Invalid URL: no host specified."
        return None
    except Exception:
        return f"Invalid URL: '{url}'"


def _build_element_map(tree: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Walk accessibility tree and assign element refs (e1, e2, ...).

    Returns:
        Tuple of (flat element list with refs, element map of ref -> selector).
    """
    elements: list[dict[str, Any]] = []
    element_map: dict[str, str] = {}
    counter = [0]

    def _walk(node: dict[str, Any]) -> None:
        role = node.get("role", "")
        name = node.get("name", "")

        # Only assign refs to interactive elements
        if role in (
            "link",
            "button",
            "textbox",
            "checkbox",
            "radio",
            "combobox",
            "menuitem",
            "tab",
            "option",
            "searchbox",
        ):
            counter[0] += 1
            ref = f"e{counter[0]}"
            # Build a selector from role and name
            selector = f"[role='{role}']"
            if name:
                selector = f"[role='{role}'][name='{name}']"
            element_map[ref] = selector
            elements.append({
                "ref": ref,
                "role": role,
                "name": name,
            })

        for child in node.get("children", []):
            _walk(child)

    _walk(tree)
    return elements, element_map


def register(mcp: FastMCP, session: BrowserSession | None = None) -> None:
    """Register browser automation tools."""
    sess = session or _default_session

    @mcp.tool()
    async def browser_navigate(url: str) -> str:
        """Navigate to a URL and return the page title and URL.

        Args:
            url: The URL to navigate to. Must be http or https.

        Returns:
            JSON with title and current URL.
        """
        try:
            error = _validate_url(url)
            if error:
                return json.dumps({"error": error}, default=str)

            page = await sess.ensure_browser()
            await page.goto(url)
            title = await page.title()

            return json.dumps(
                {"title": title, "url": page.url},
                default=str,
            )

        except Exception as e:
            logger.warning("browser_navigate_error", url=url, error=str(e))
            return json.dumps({"error": str(e)}, default=str)

    @mcp.tool()
    async def browser_snapshot() -> str:
        """Get the accessibility tree of the current page.

        Returns element references (e1, e2, ...) that can be used with browser_act.

        Returns:
            JSON with page title, URL, and list of interactive elements with refs.
        """
        try:
            if sess._page is None:
                return json.dumps(
                    {"error": "No page is open. Use browser_navigate first."},
                    default=str,
                )

            page = await sess.ensure_browser()
            tree = await page.accessibility.snapshot()

            if not tree:
                return json.dumps(
                    {"error": "Could not get accessibility tree."},
                    default=str,
                )

            elements, element_map = _build_element_map(tree)
            sess._element_map = element_map

            title = await page.title()
            return json.dumps(
                {
                    "title": title,
                    "url": page.url,
                    "elements": elements,
                    "total_elements": len(elements),
                },
                default=str,
            )

        except Exception as e:
            logger.warning("browser_snapshot_error", error=str(e))
            return json.dumps({"error": str(e)}, default=str)

    @mcp.tool()
    async def browser_act(
        kind: str,
        ref: str | None = None,
        text: str | None = None,
        key: str | None = None,
    ) -> str:
        """Perform an action on the current page.

        Args:
            kind: Action type. One of: click, type, press, scroll.
            ref: Element reference from browser_snapshot (e.g., "e1").
                 Required for click and type.
            text: Text to type (required for kind="type").
            key: Key to press (required for kind="press", e.g., "Enter").

        Returns:
            JSON confirming the action.
        """
        try:
            if kind not in VALID_ACTIONS:
                return json.dumps(
                    {
                        "error": f"Invalid action '{kind}'. "
                        f"Supported: {sorted(VALID_ACTIONS)}"
                    },
                    default=str,
                )

            if sess._page is None:
                return json.dumps(
                    {"error": "No page is open. Use browser_navigate first."},
                    default=str,
                )

            page = sess._page

            if kind == "click":
                if not ref:
                    return json.dumps(
                        {"error": "ref is required for click action"},
                        default=str,
                    )
                selector = sess._element_map.get(ref)
                if not selector:
                    return json.dumps(
                        {"error": f"Unknown ref '{ref}'. Run browser_snapshot first."},
                        default=str,
                    )
                await page.locator(selector).click()
                return json.dumps(
                    {"status": "clicked", "ref": ref},
                    default=str,
                )

            elif kind == "type":
                if not ref:
                    return json.dumps(
                        {"error": "ref is required for type action"},
                        default=str,
                    )
                if text is None:
                    return json.dumps(
                        {"error": "text is required for type action"},
                        default=str,
                    )
                selector = sess._element_map.get(ref)
                if not selector:
                    return json.dumps(
                        {"error": f"Unknown ref '{ref}'. Run browser_snapshot first."},
                        default=str,
                    )
                await page.locator(selector).fill(text)
                return json.dumps(
                    {"status": "typed", "ref": ref, "text": text},
                    default=str,
                )

            elif kind == "press":
                key_to_press = key or text or "Enter"
                await page.keyboard.press(key_to_press)
                return json.dumps(
                    {"status": "pressed", "key": key_to_press},
                    default=str,
                )

            elif kind == "scroll":
                # Scroll direction based on text param or default down
                direction = (text or "down").lower()
                delta = -500 if direction == "up" else 500
                await page.mouse.wheel(0, delta)
                return json.dumps(
                    {"status": "scrolled", "direction": direction},
                    default=str,
                )

            return json.dumps({"error": "Unhandled action"}, default=str)

        except Exception as e:
            logger.warning("browser_act_error", kind=kind, error=str(e))
            return json.dumps({"error": str(e)}, default=str)

    @mcp.tool()
    async def browser_read() -> str:
        """Read the full page text content.

        Returns:
            JSON with the page text via innerText.
        """
        try:
            if sess._page is None:
                return json.dumps(
                    {"error": "No page is open. Use browser_navigate first."},
                    default=str,
                )

            page = sess._page
            text = await page.evaluate("() => document.body.innerText")
            title = await page.title()

            return json.dumps(
                {"title": title, "url": page.url, "text": text},
                default=str,
            )

        except Exception as e:
            logger.warning("browser_read_error", error=str(e))
            return json.dumps({"error": str(e)}, default=str)

    @mcp.tool()
    async def browser_close() -> str:
        """Close the browser and free resources.

        Returns:
            JSON confirming the browser was closed.
        """
        try:
            await sess.close()
            return json.dumps({"status": "closed"}, default=str)

        except Exception as e:
            logger.warning("browser_close_error", error=str(e))
            return json.dumps({"error": str(e)}, default=str)
