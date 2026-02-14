# TASK-024: Browser Automation Tools

## Task ID
TASK-024

## Status
COMPLETED

## Title
Implement Browser Automation Tools (5 Tools)

## Description
Implement 5 browser MCP tools using Playwright (async Python): `browser_navigate`, `browser_snapshot`, `browser_act`, `browser_read`, and `browser_close`. A single browser instance persists across calls within a session. These are used by the Browser Research sub-agent for JS-rendered pages.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/tools/browser/actions.py`:
  - `browser_navigate(url)` — navigates to URL, returns title and URL (no content)
  - `browser_snapshot()` — returns accessibility tree with element refs (e1, e2, ...)
  - `browser_act(kind, ref=None, text=None, key=None)` — performs action:
    - `kind="click"`: click element by ref
    - `kind="type"`: type text into element by ref
    - `kind="press"`: press keyboard key
    - `kind="scroll"`: scroll page (up/down)
  - `browser_read()` — returns full page text content
  - `browser_close()` — closes browser, frees resources
- [ ] Persistent browser instance: first call to `browser_navigate` launches Chromium; subsequent calls reuse the same instance
- [ ] Browser instance closed on `browser_close()` or MCP server shutdown
- [ ] All 5 tools registered via `register_browser_tools(app)`
- [ ] No caching (browser interactions are inherently stateful)

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with mocked Playwright; test lifecycle (navigate -> snapshot -> act -> read -> close)
- [ ] **Reliability**: Handle browser crashes gracefully; auto-relaunch if needed
- [ ] **Performance**: Navigation timeout of 30 seconds; snapshot should complete in < 5 seconds
- [ ] **Security**: Only allow navigation to http/https URLs

## Dependencies
- TASK-001: Project scaffolding
- TASK-006: MCP server entry point

## Technical Notes

### Browser Session Management
```python
from playwright.async_api import async_playwright

class BrowserSession:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None

    async def ensure_browser(self):
        if not self._browser:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._page = await self._browser.new_page()
        return self._page

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._page = None

# Global session instance
_session = BrowserSession()
```

### Accessibility Tree Snapshot
```python
async def snapshot():
    page = await _session.ensure_browser()
    tree = await page.accessibility.snapshot()
    # Assign ref IDs (e1, e2, ...) to interactive elements
    # Return structured tree with refs for use with browser_act
```

### Implementation Hints
1. Playwright must be installed first: `uv run playwright install chromium`
2. Use `headless=True` for the MCP server context
3. Element refs (e1, e2) need a mapping from ref -> Playwright locator
4. The accessibility tree provides a structured view of the page without full HTML
5. `browser_read` should extract `.innerText()` from the page body
6. Consider adding a navigation timeout parameter (default 30s)

## Estimated Complexity
**Medium** (6-8 hours)

## References
- ZAZA_ARCHITECTURE.md Section 10 (Browser Tool)
- Playwright Python: https://playwright.dev/python/
