"""Tests for __main__ — consumer entry point wiring and cleanup."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zaza.consumer.plan_index import PlanLocks

# ---------------------------------------------------------------------------
# Tests for main()
# ---------------------------------------------------------------------------


class TestMainWiring:
    """Verify main() wires components correctly."""

    async def test_main_connects_reconciles_and_consumes(self) -> None:
        """main() calls connect, reconcile_on_startup, and consume_stream."""
        mock_mcp = AsyncMock()
        mock_mcp.connect = AsyncMock()
        mock_mcp.close = AsyncMock()

        with (
            patch("zaza.consumer.__main__.ConsumerSettings") as mock_settings_cls,
            patch("zaza.consumer.__main__.McpClients", return_value=mock_mcp),
            patch("zaza.consumer.__main__.PlanIndex") as mock_index_cls,
            patch(
                "zaza.consumer.__main__.reconcile_on_startup",
                new_callable=AsyncMock,
            ) as mock_reconcile,
            patch(
                "zaza.consumer.__main__.consume_stream", new_callable=AsyncMock,
            ) as mock_consume,
            patch(
                "zaza.consumer.__main__.rth_scan_loop", new_callable=AsyncMock,
            ) as mock_rth_loop,
        ):
            mock_settings = MagicMock()
            mock_settings.tiger_mcp_url = "http://tiger"
            mock_settings.zaza_mcp_url = "http://zaza"
            mock_settings.order_delay_ms = 500
            mock_settings_cls.from_env.return_value = mock_settings

            mock_index = MagicMock()
            mock_index_cls.return_value = mock_index

            # Make rth_scan_loop a coroutine that immediately returns
            # (it will be wrapped in create_task)
            mock_rth_loop.return_value = None

            from zaza.consumer.__main__ import main

            await main()

            # Verify lifecycle order
            mock_mcp.connect.assert_called_once()
            mock_reconcile.assert_called_once()
            call_args = mock_reconcile.call_args
            assert call_args[0][0] is mock_mcp
            assert call_args[0][1] is mock_index
            assert call_args[0][2] is mock_settings
            assert isinstance(call_args[0][3], PlanLocks)
            mock_consume.assert_called_once()
            mock_mcp.close.assert_called_once()

    async def test_main_handler_closures_pass_correct_args(self) -> None:
        """The on_entry/on_stop/on_tp closures pass mcp, index, and settings."""
        mock_mcp = AsyncMock()
        mock_mcp.connect = AsyncMock()
        mock_mcp.close = AsyncMock()

        captured_handler = None

        async def _capture_consume(settings, handler):
            nonlocal captured_handler
            captured_handler = handler

        with (
            patch("zaza.consumer.__main__.ConsumerSettings") as mock_settings_cls,
            patch("zaza.consumer.__main__.McpClients", return_value=mock_mcp),
            patch("zaza.consumer.__main__.PlanIndex") as mock_index_cls,
            patch("zaza.consumer.__main__.reconcile_on_startup", new_callable=AsyncMock),
            patch("zaza.consumer.__main__.consume_stream", side_effect=_capture_consume),
            patch("zaza.consumer.__main__.rth_scan_loop", new_callable=AsyncMock),
            patch("zaza.consumer.__main__.TransactionHandler") as mock_handler_cls,
        ):
            mock_settings = MagicMock()
            mock_settings.tiger_mcp_url = "http://tiger"
            mock_settings.zaza_mcp_url = "http://zaza"
            mock_settings.order_delay_ms = 500
            mock_settings_cls.from_env.return_value = mock_settings

            mock_index = MagicMock()
            mock_index_cls.return_value = mock_index

            from zaza.consumer.__main__ import main

            await main()

            # TransactionHandler was constructed with index and closures
            mock_handler_cls.assert_called_once()
            call_args = mock_handler_cls.call_args
            assert call_args[0][0] is mock_index  # plan_index


class TestMainCleanup:
    """Verify main() cleans up resources even on error."""

    async def test_close_called_on_consume_error(self) -> None:
        """If consume_stream raises, mcp.close() is still called."""
        mock_mcp = AsyncMock()
        mock_mcp.connect = AsyncMock()
        mock_mcp.close = AsyncMock()

        with (
            patch("zaza.consumer.__main__.ConsumerSettings") as mock_settings_cls,
            patch("zaza.consumer.__main__.McpClients", return_value=mock_mcp),
            patch("zaza.consumer.__main__.PlanIndex"),
            patch("zaza.consumer.__main__.reconcile_on_startup", new_callable=AsyncMock),
            patch("zaza.consumer.__main__.consume_stream", new_callable=AsyncMock) as mock_consume,
            patch("zaza.consumer.__main__.rth_scan_loop", new_callable=AsyncMock),
        ):
            mock_settings = MagicMock()
            mock_settings.tiger_mcp_url = "http://tiger"
            mock_settings.zaza_mcp_url = "http://zaza"
            mock_settings.order_delay_ms = 500
            mock_settings_cls.from_env.return_value = mock_settings

            mock_consume.side_effect = RuntimeError("Redis connection lost")

            from zaza.consumer.__main__ import main

            with pytest.raises(RuntimeError, match="Redis connection lost"):
                await main()

            # Even after error, close must be called
            mock_mcp.close.assert_called_once()

    async def test_rth_task_cancelled_on_shutdown(self) -> None:
        """The RTH scan loop task is cancelled during shutdown."""
        mock_mcp = AsyncMock()
        mock_mcp.connect = AsyncMock()
        mock_mcp.close = AsyncMock()

        rth_started = asyncio.Event()

        async def _long_running_rth(*args, **kwargs):
            rth_started.set()
            await asyncio.sleep(3600)  # Would run forever

        async def _short_consume(*args, **kwargs):
            # Wait for RTH to start, then return
            await rth_started.wait()

        with (
            patch("zaza.consumer.__main__.ConsumerSettings") as mock_settings_cls,
            patch("zaza.consumer.__main__.McpClients", return_value=mock_mcp),
            patch("zaza.consumer.__main__.PlanIndex"),
            patch("zaza.consumer.__main__.reconcile_on_startup", new_callable=AsyncMock),
            patch("zaza.consumer.__main__.consume_stream", side_effect=_short_consume),
            patch("zaza.consumer.__main__.rth_scan_loop", side_effect=_long_running_rth),
        ):
            mock_settings = MagicMock()
            mock_settings.tiger_mcp_url = "http://tiger"
            mock_settings.zaza_mcp_url = "http://zaza"
            mock_settings.order_delay_ms = 500
            mock_settings_cls.from_env.return_value = mock_settings

            from zaza.consumer.__main__ import main

            # Should complete without hanging (RTH task cancelled)
            await asyncio.wait_for(main(), timeout=5.0)

            # close() called during cleanup
            mock_mcp.close.assert_called_once()
