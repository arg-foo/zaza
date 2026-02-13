"""Browser session management -- persistent Playwright browser instance.

One browser per session. Lazy-initialized on first use.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class BrowserSession:
    """Manages a persistent Playwright browser session."""

    def __init__(self) -> None:
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None
        self._element_map: dict[str, str] = {}

    async def ensure_browser(self) -> Any:
        """Lazily start browser and return the active page.

        Returns:
            The active Playwright page.
        """
        if not self._browser:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._page = await self._browser.new_page()
            logger.info("browser_session_started")
        return self._page

    async def close(self) -> None:
        """Close the browser and free resources."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning("browser_close_error", error=str(e))
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning("playwright_stop_error", error=str(e))
        self._browser = None
        self._page = None
        self._playwright = None
        self._element_map = {}
        logger.info("browser_session_closed")


# Module-level singleton (used when no session is injected)
_default_session = BrowserSession()
