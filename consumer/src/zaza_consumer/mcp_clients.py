"""MCP client session manager for Tiger and Zaza servers.

Manages two long-lived MCP client connections over streamable-HTTP,
providing typed wrapper methods for Tiger broker operations and
Zaza trade-plan management.
"""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import Any

import httpx
import structlog
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

log = structlog.get_logger()


class McpClients:
    """Manages long-lived MCP client sessions to Tiger and Zaza servers."""

    def __init__(self, tiger_url: str, zaza_url: str) -> None:
        self._tiger_url = tiger_url
        self._zaza_url = zaza_url
        self._tiger_session: ClientSession | None = None
        self._zaza_session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._connected: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(
        self, *, max_retries: int = 5, base_delay: float = 1.0
    ) -> None:
        """Open MCP connections to both Tiger and Zaza servers.

        Retries on connection errors with exponential backoff.
        """
        _retryable = (httpx.ConnectError, OSError, ConnectionError)

        for attempt in range(1, max_retries + 1):
            stack = AsyncExitStack()
            try:
                self._exit_stack = await stack.__aenter__()

                # Tiger
                tiger_read, tiger_write, _ = (
                    await self._exit_stack.enter_async_context(
                        streamablehttp_client(self._tiger_url)
                    )
                )
                tiger_session = await self._exit_stack.enter_async_context(
                    ClientSession(tiger_read, tiger_write)
                )
                await tiger_session.initialize()
                self._tiger_session = tiger_session
                log.info(
                    "mcp_client.connected", server="tiger", url=self._tiger_url
                )

                # Zaza
                zaza_read, zaza_write, _ = (
                    await self._exit_stack.enter_async_context(
                        streamablehttp_client(self._zaza_url)
                    )
                )
                zaza_session = await self._exit_stack.enter_async_context(
                    ClientSession(zaza_read, zaza_write)
                )
                await zaza_session.initialize()
                self._zaza_session = zaza_session
                log.info(
                    "mcp_client.connected", server="zaza", url=self._zaza_url
                )

                self._connected = True
                return

            except _retryable as exc:
                # Clean up partial connections before retry
                await stack.aclose()
                self._exit_stack = None
                self._tiger_session = None
                self._zaza_session = None

                if attempt == max_retries:
                    log.error(
                        "mcp_client.connect_failed",
                        tiger_url=self._tiger_url,
                        zaza_url=self._zaza_url,
                        attempts=attempt,
                    )
                    raise

                delay = base_delay * (2 ** (attempt - 1))
                log.warning(
                    "mcp_client.connect_retry",
                    attempt=attempt,
                    max_retries=max_retries,
                    delay=delay,
                    error=str(exc),
                )
                await asyncio.sleep(delay)

            except Exception:
                log.error(
                    "mcp_client.connect_failed",
                    tiger_url=self._tiger_url,
                    zaza_url=self._zaza_url,
                )
                await stack.aclose()
                raise

    async def close(self) -> None:
        """Close all MCP connections and reset state."""
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
        self._tiger_session = None
        self._zaza_session = None
        self._exit_stack = None
        self._connected = False
        log.info("mcp_client.closed")

    # ------------------------------------------------------------------
    # Internal call helpers
    # ------------------------------------------------------------------

    async def _call_tiger(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on the Tiger MCP server and return the text result."""
        if not self._connected:
            raise RuntimeError("Not connected")
        try:
            result = await self._tiger_session.call_tool(tool_name, arguments)  # type: ignore[union-attr]
            return result.content[0].text
        except Exception:
            log.error(
                "mcp_client.tiger_call_failed",
                tool=tool_name,
                arguments=arguments,
            )
            raise

    async def _call_zaza(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on the Zaza MCP server and return the text result."""
        if not self._connected:
            raise RuntimeError("Not connected")
        try:
            result = await self._zaza_session.call_tool(tool_name, arguments)  # type: ignore[union-attr]
            return result.content[0].text
        except Exception:
            log.error(
                "mcp_client.zaza_call_failed",
                tool=tool_name,
                arguments=arguments,
            )
            raise

    # ------------------------------------------------------------------
    # Tiger MCP wrappers
    # ------------------------------------------------------------------

    async def place_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> str:
        """Place a stock order via Tiger MCP."""
        arguments: dict[str, Any] = {
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "order_type": order_type,
        }
        if limit_price is not None:
            arguments["limit_price"] = limit_price
        if stop_price is not None:
            arguments["stop_price"] = stop_price
        return await self._call_tiger("place_stock_order", arguments)

    async def cancel_order(self, order_id: int) -> str:
        """Cancel an order via Tiger MCP."""
        return await self._call_tiger("cancel_order", {"order_id": order_id})

    async def modify_order(
        self,
        order_id: int,
        quantity: int | None = None,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> str:
        """Modify an existing order via Tiger MCP."""
        arguments: dict[str, Any] = {"order_id": order_id}
        if quantity is not None:
            arguments["quantity"] = quantity
        if limit_price is not None:
            arguments["limit_price"] = limit_price
        if stop_price is not None:
            arguments["stop_price"] = stop_price
        return await self._call_tiger("modify_order", arguments)

    async def get_open_orders(self, symbol: str = "") -> str:
        """List open orders via Tiger MCP."""
        return await self._call_tiger("get_open_orders", {"symbol": symbol})

    async def get_order_detail(self, order_id: int) -> str:
        """Get details for a single order via Tiger MCP."""
        return await self._call_tiger("get_order_detail", {"order_id": order_id})

    async def get_filled_orders(
        self,
        symbol: str | None = None,
        limit: int = 50,
    ) -> str:
        """Get execution history via Tiger MCP."""
        arguments: dict[str, Any] = {"limit": limit}
        if symbol is not None:
            arguments["symbol"] = symbol
        return await self._call_tiger("get_transaction_history", arguments)

    # ------------------------------------------------------------------
    # Zaza MCP wrappers
    # ------------------------------------------------------------------

    async def list_trade_plans(self, include_archived: bool = False) -> str:
        """List trade plans via Zaza MCP."""
        return await self._call_zaza(
            "list_trade_plans", {"include_archived": include_archived}
        )

    async def get_trade_plan(self, plan_id: str) -> str:
        """Get a trade plan by ID via Zaza MCP."""
        return await self._call_zaza("get_trade_plan", {"plan_id": plan_id})

    async def update_trade_plan(self, plan_id: str, xml: str) -> str:
        """Update a trade plan via Zaza MCP."""
        return await self._call_zaza(
            "update_trade_plan", {"plan_id": plan_id, "xml": xml}
        )

    async def close_trade_plan(self, plan_id: str, reason: str = "") -> str:
        """Archive a trade plan via Zaza MCP."""
        return await self._call_zaza(
            "close_trade_plan", {"plan_id": plan_id, "reason": reason}
        )
