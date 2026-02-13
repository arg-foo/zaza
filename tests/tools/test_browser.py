"""Tests for browser tools (TASK-024).

Tests Playwright-based browser automation with fully mocked Playwright.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_mock_page() -> AsyncMock:
    """Create a mock Playwright page with common methods."""
    page = AsyncMock()
    page.title = AsyncMock(return_value="Test Page")
    page.url = "https://example.com"
    page.goto = AsyncMock()
    page.content = AsyncMock(return_value="<html><body>Hello</body></html>")
    page.evaluate = AsyncMock(return_value="Hello page text content")
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.press = AsyncMock()
    page.keyboard = AsyncMock()
    page.keyboard.press = AsyncMock()
    page.mouse = AsyncMock()
    page.mouse.wheel = AsyncMock()

    # Accessibility tree mock
    snapshot = {
        "role": "WebArea",
        "name": "Test Page",
        "children": [
            {"role": "heading", "name": "Welcome", "level": 1},
            {"role": "link", "name": "Click me", "url": "https://example.com/link"},
            {"role": "textbox", "name": "Search", "value": ""},
            {"role": "button", "name": "Submit"},
        ],
    }
    page.accessibility = AsyncMock()
    page.accessibility.snapshot = AsyncMock(return_value=snapshot)

    # Locator mock
    locator = AsyncMock()
    locator.click = AsyncMock()
    locator.fill = AsyncMock()
    page.locator = MagicMock(return_value=locator)

    return page


def _make_mock_browser() -> AsyncMock:
    """Create a mock Playwright browser."""
    browser = AsyncMock()
    page = _make_mock_page()
    browser.new_page = AsyncMock(return_value=page)
    browser.close = AsyncMock()
    return browser


# ---------------------------------------------------------------------------
# TASK-024a: browser_navigate
# ---------------------------------------------------------------------------

class TestBrowserNavigate:
    """Tests for the browser_navigate tool."""

    @pytest.mark.asyncio
    async def test_navigate_valid_url(self) -> None:
        """Navigate to a valid HTTP URL."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.browser.actions import register
        from zaza.tools.browser.session import BrowserSession

        mcp = FastMCP("test")
        mock_page = _make_mock_page()

        session = BrowserSession()
        with patch.object(session, "ensure_browser", return_value=mock_page):
            register(mcp, session=session)

            tool = mcp._tool_manager.get_tool("browser_navigate")
            result_str = await tool.run(
                arguments={"url": "https://example.com"}
            )
            result = json.loads(result_str)

        assert "error" not in result
        assert "title" in result
        assert "url" in result

    @pytest.mark.asyncio
    async def test_navigate_invalid_protocol(self) -> None:
        """Reject non-http/https URLs."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.browser.actions import register
        from zaza.tools.browser.session import BrowserSession

        mcp = FastMCP("test")
        session = BrowserSession()

        register(mcp, session=session)

        tool = mcp._tool_manager.get_tool("browser_navigate")
        result_str = await tool.run(
            arguments={"url": "file:///etc/passwd"}
        )
        result = json.loads(result_str)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_navigate_javascript_url_rejected(self) -> None:
        """Reject javascript: URLs."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.browser.actions import register
        from zaza.tools.browser.session import BrowserSession

        mcp = FastMCP("test")
        session = BrowserSession()
        register(mcp, session=session)

        tool = mcp._tool_manager.get_tool("browser_navigate")
        result_str = await tool.run(
            arguments={"url": "javascript:alert(1)"}
        )
        result = json.loads(result_str)

        assert "error" in result


# ---------------------------------------------------------------------------
# TASK-024b: browser_snapshot
# ---------------------------------------------------------------------------

class TestBrowserSnapshot:
    """Tests for the browser_snapshot tool."""

    @pytest.mark.asyncio
    async def test_snapshot_returns_tree(self) -> None:
        """Snapshot returns accessibility tree with element refs."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.browser.actions import register
        from zaza.tools.browser.session import BrowserSession

        mcp = FastMCP("test")
        mock_page = _make_mock_page()

        session = BrowserSession()
        session._page = mock_page
        with patch.object(session, "ensure_browser", return_value=mock_page):
            register(mcp, session=session)

            tool = mcp._tool_manager.get_tool("browser_snapshot")
            result_str = await tool.run(arguments={})
            result = json.loads(result_str)

        assert "error" not in result
        assert "elements" in result or "tree" in result

    @pytest.mark.asyncio
    async def test_snapshot_no_browser(self) -> None:
        """Snapshot when no page is open returns error."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.browser.actions import register
        from zaza.tools.browser.session import BrowserSession

        mcp = FastMCP("test")
        session = BrowserSession()
        register(mcp, session=session)

        tool = mcp._tool_manager.get_tool("browser_snapshot")
        result_str = await tool.run(arguments={})
        result = json.loads(result_str)

        assert "error" in result


# ---------------------------------------------------------------------------
# TASK-024c: browser_act
# ---------------------------------------------------------------------------

class TestBrowserAct:
    """Tests for the browser_act tool."""

    @pytest.mark.asyncio
    async def test_act_click(self) -> None:
        """Click action on a valid element ref."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.browser.actions import register
        from zaza.tools.browser.session import BrowserSession

        mcp = FastMCP("test")
        mock_page = _make_mock_page()

        session = BrowserSession()
        session._page = mock_page
        session._element_map = {"e1": "[role='link'][name='Click me']"}

        with patch.object(session, "ensure_browser", return_value=mock_page):
            register(mcp, session=session)

            tool = mcp._tool_manager.get_tool("browser_act")
            result_str = await tool.run(
                arguments={"kind": "click", "ref": "e1"}
            )
            result = json.loads(result_str)

        assert "error" not in result

    @pytest.mark.asyncio
    async def test_act_type(self) -> None:
        """Type action fills text in an element."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.browser.actions import register
        from zaza.tools.browser.session import BrowserSession

        mcp = FastMCP("test")
        mock_page = _make_mock_page()

        session = BrowserSession()
        session._page = mock_page
        session._element_map = {"e3": "[role='textbox'][name='Search']"}

        with patch.object(session, "ensure_browser", return_value=mock_page):
            register(mcp, session=session)

            tool = mcp._tool_manager.get_tool("browser_act")
            result_str = await tool.run(
                arguments={"kind": "type", "ref": "e3", "text": "hello world"}
            )
            result = json.loads(result_str)

        assert "error" not in result

    @pytest.mark.asyncio
    async def test_act_invalid_kind(self) -> None:
        """Invalid action kind returns error."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.browser.actions import register
        from zaza.tools.browser.session import BrowserSession

        mcp = FastMCP("test")
        session = BrowserSession()
        session._page = _make_mock_page()
        register(mcp, session=session)

        tool = mcp._tool_manager.get_tool("browser_act")
        result_str = await tool.run(
            arguments={"kind": "destroy"}
        )
        result = json.loads(result_str)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_act_no_page(self) -> None:
        """Action when no page is open returns error."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.browser.actions import register
        from zaza.tools.browser.session import BrowserSession

        mcp = FastMCP("test")
        session = BrowserSession()
        register(mcp, session=session)

        tool = mcp._tool_manager.get_tool("browser_act")
        result_str = await tool.run(
            arguments={"kind": "click", "ref": "e1"}
        )
        result = json.loads(result_str)

        assert "error" in result


# ---------------------------------------------------------------------------
# TASK-024d: browser_read
# ---------------------------------------------------------------------------

class TestBrowserRead:
    """Tests for the browser_read tool."""

    @pytest.mark.asyncio
    async def test_read_returns_text(self) -> None:
        """Read returns page text content."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.browser.actions import register
        from zaza.tools.browser.session import BrowserSession

        mcp = FastMCP("test")
        mock_page = _make_mock_page()

        session = BrowserSession()
        session._page = mock_page
        with patch.object(session, "ensure_browser", return_value=mock_page):
            register(mcp, session=session)

            tool = mcp._tool_manager.get_tool("browser_read")
            result_str = await tool.run(arguments={})
            result = json.loads(result_str)

        assert "error" not in result
        assert "text" in result

    @pytest.mark.asyncio
    async def test_read_no_page(self) -> None:
        """Read when no page is open returns error."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.browser.actions import register
        from zaza.tools.browser.session import BrowserSession

        mcp = FastMCP("test")
        session = BrowserSession()
        register(mcp, session=session)

        tool = mcp._tool_manager.get_tool("browser_read")
        result_str = await tool.run(arguments={})
        result = json.loads(result_str)

        assert "error" in result


# ---------------------------------------------------------------------------
# TASK-024e: browser_close
# ---------------------------------------------------------------------------

class TestBrowserClose:
    """Tests for the browser_close tool."""

    @pytest.mark.asyncio
    async def test_close_browser(self) -> None:
        """Close cleans up resources and confirms."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.browser.actions import register
        from zaza.tools.browser.session import BrowserSession

        mcp = FastMCP("test")
        mock_browser = _make_mock_browser()

        session = BrowserSession()
        session._browser = mock_browser
        session._page = _make_mock_page()

        register(mcp, session=session)

        tool = mcp._tool_manager.get_tool("browser_close")
        result_str = await tool.run(arguments={})
        result = json.loads(result_str)

        assert "error" not in result
        assert result.get("status") == "closed"

    @pytest.mark.asyncio
    async def test_close_no_browser(self) -> None:
        """Close when no browser is open still succeeds."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.browser.actions import register
        from zaza.tools.browser.session import BrowserSession

        mcp = FastMCP("test")
        session = BrowserSession()
        register(mcp, session=session)

        tool = mcp._tool_manager.get_tool("browser_close")
        result_str = await tool.run(arguments={})
        result = json.loads(result_str)

        assert result.get("status") == "closed"


# ---------------------------------------------------------------------------
# Session lifecycle tests
# ---------------------------------------------------------------------------

class TestBrowserSession:
    """Tests for the BrowserSession helper."""

    def test_initial_state(self) -> None:
        """New session has no browser/page."""
        from zaza.tools.browser.session import BrowserSession

        session = BrowserSession()
        assert session._browser is None
        assert session._page is None
        assert session._element_map == {}

    @pytest.mark.asyncio
    async def test_close_resets_state(self) -> None:
        """Close resets all state."""
        from zaza.tools.browser.session import BrowserSession

        session = BrowserSession()
        session._browser = _make_mock_browser()
        session._page = _make_mock_page()
        session._element_map = {"e1": "something"}

        await session.close()

        assert session._browser is None
        assert session._page is None
        assert session._element_map == {}
