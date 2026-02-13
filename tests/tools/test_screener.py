"""Tests for screener tools (TASK-023).

Tests PKScreener Docker integration with mocked subprocess calls.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

_PATCH_RUN = "zaza.tools.screener.pkscreener.run_pkscreener"


# ---------------------------------------------------------------------------
# TASK-023a: screen_stocks
# ---------------------------------------------------------------------------

class TestScreenStocks:
    """Tests for the screen_stocks tool."""

    @pytest.mark.asyncio
    async def test_screen_stocks_valid_scan_type(self) -> None:
        """Valid scan type returns parsed results."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        mock_output = (
            "Stock\tConsolidating\tBreaking-Loss\tLTP\tChange\tVolume\n"
            "AAPL\tYes\tNo\t195.0\t2.5\t50000000\n"
            "MSFT\tNo\tNo\t410.0\t1.2\t30000000\n"
        )

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_output

            tool = mcp._tool_manager.get_tool("screen_stocks")
            result_str = await tool.run(
                arguments={"scan_type": "breakout"}
            )
            result = json.loads(result_str)

        assert "error" not in result
        assert "results" in result

    @pytest.mark.asyncio
    async def test_screen_stocks_invalid_scan_type(self) -> None:
        """Invalid scan type returns error without running Docker."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            tool = mcp._tool_manager.get_tool("screen_stocks")
            result_str = await tool.run(
                arguments={"scan_type": "rm -rf /; injection"}
            )
            result = json.loads(result_str)

        assert "error" in result
        mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_screen_stocks_command_injection_prevention(self) -> None:
        """Scan type with shell metacharacters is rejected."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            tool = mcp._tool_manager.get_tool("screen_stocks")
            result_str = await tool.run(
                arguments={"scan_type": "breakout; rm -rf /"}
            )
            result = json.loads(result_str)

        assert "error" in result
        mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_screen_stocks_docker_error(self) -> None:
        """Docker exec error is handled gracefully."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = RuntimeError(
                "PKScreener error: container not found"
            )

            tool = mcp._tool_manager.get_tool("screen_stocks")
            result_str = await tool.run(
                arguments={"scan_type": "breakout"}
            )
            result = json.loads(result_str)

        assert "error" in result


# ---------------------------------------------------------------------------
# TASK-023b: get_screening_strategies
# ---------------------------------------------------------------------------

class TestScreeningStrategies:
    """Tests for the get_screening_strategies tool."""

    @pytest.mark.asyncio
    async def test_returns_strategy_list(self) -> None:
        """Returns a list of available screening strategies."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        tool = mcp._tool_manager.get_tool("get_screening_strategies")
        result_str = await tool.run(arguments={})
        result = json.loads(result_str)

        assert "strategies" in result
        assert len(result["strategies"]) > 0
        for s in result["strategies"]:
            assert "name" in s
            assert "description" in s

    @pytest.mark.asyncio
    async def test_strategies_include_known_types(self) -> None:
        """Strategy list includes the main scan types."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        tool = mcp._tool_manager.get_tool("get_screening_strategies")
        result_str = await tool.run(arguments={})
        result = json.loads(result_str)

        names = [s["name"] for s in result["strategies"]]
        assert "breakout" in names
        assert "momentum" in names


# ---------------------------------------------------------------------------
# TASK-023c: get_buy_sell_levels
# ---------------------------------------------------------------------------

class TestBuySellLevels:
    """Tests for the get_buy_sell_levels tool."""

    @pytest.mark.asyncio
    async def test_buy_sell_levels_returns_data(self) -> None:
        """Returns buy/sell levels for a ticker."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        mock_output = (
            "Stock: AAPL\n"
            "Buy Level: 190.5\n"
            "Sell Level: 200.0\n"
            "Support: 188.0\n"
            "Resistance: 202.5\n"
        )

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_output

            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            result_str = await tool.run(
                arguments={"ticker": "AAPL"}
            )
            result = json.loads(result_str)

        assert "error" not in result
        assert "ticker" in result

    @pytest.mark.asyncio
    async def test_buy_sell_levels_docker_error(self) -> None:
        """Docker error handled gracefully."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = RuntimeError(
                "PKScreener error: timeout"
            )

            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            result_str = await tool.run(
                arguments={"ticker": "AAPL"}
            )
            result = json.loads(result_str)

        assert "error" in result


# ---------------------------------------------------------------------------
# Docker helper tests
# ---------------------------------------------------------------------------

class TestDockerHelper:
    """Tests for the run_pkscreener helper."""

    @pytest.mark.asyncio
    async def test_run_pkscreener_success(self) -> None:
        """Successful Docker exec returns stdout."""
        from zaza.tools.screener.docker import run_pkscreener

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"output data", b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await run_pkscreener(["--arg1", "val1"])

        assert result == "output data"

    @pytest.mark.asyncio
    async def test_run_pkscreener_failure(self) -> None:
        """Failed Docker exec raises RuntimeError."""
        from zaza.tools.screener.docker import run_pkscreener

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"some error")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="PKScreener error"):
                await run_pkscreener(["--bad-arg"])

    @pytest.mark.asyncio
    async def test_run_pkscreener_timeout(self) -> None:
        """Docker exec timeout raises TimeoutError."""
        import asyncio as aio

        from zaza.tools.screener.docker import run_pkscreener

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            side_effect=aio.TimeoutError()
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(aio.TimeoutError):
                await run_pkscreener(["--slow"], timeout=1)
