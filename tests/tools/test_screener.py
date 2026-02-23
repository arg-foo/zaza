"""Tests for screener tools (TASK-023).

Tests PKScreener Docker integration with mocked subprocess calls.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

_PATCH_RUN = "zaza.tools.screener.pkscreener.run_pkscreener"


# ---------------------------------------------------------------------------
# ANSI stripping
# ---------------------------------------------------------------------------

class TestAnsiStripping:
    """Tests for strip_ansi utility."""

    def test_strips_color_codes(self) -> None:
        """ANSI color codes are removed."""
        from zaza.tools.screener.docker import strip_ansi

        assert strip_ansi("\x1b[32mGreen\x1b[0m") == "Green"

    def test_strips_cursor_codes(self) -> None:
        """ANSI cursor movement codes are removed."""
        from zaza.tools.screener.docker import strip_ansi

        assert strip_ansi("\x1b[2JCleared\x1b[H") == "Cleared"

    def test_strips_osc_sequences(self) -> None:
        """OSC (Operating System Command) sequences are removed."""
        from zaza.tools.screener.docker import strip_ansi

        assert strip_ansi("\x1b]0;title\x07text") == "text"

    def test_strips_private_mode_sequences(self) -> None:
        """Private mode sequences like cursor hide/show are removed."""
        from zaza.tools.screener.docker import strip_ansi
        assert strip_ansi("\x1b[?25lHidden\x1b[?25h") == "Hidden"

    def test_strips_carriage_return(self) -> None:
        """Carriage returns from progress spinners are removed."""
        from zaza.tools.screener.docker import strip_ansi
        assert strip_ansi("progress\rDone") == "progressDone"

    def test_passthrough_clean_text(self) -> None:
        """Clean text passes through unchanged."""
        from zaza.tools.screener.docker import strip_ansi

        assert strip_ansi("Hello World 123") == "Hello World 123"


# ---------------------------------------------------------------------------
# Docker helper tests
# ---------------------------------------------------------------------------

class TestDockerHelper:
    """Tests for the run_pkscreener helper."""

    @pytest.mark.asyncio
    async def test_run_pkscreener_success(self) -> None:
        """Successful Docker exec returns stdout with ANSI stripped."""
        from zaza.tools.screener.docker import run_pkscreener

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"\x1b[32moutput data\x1b[0m", b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            result = await run_pkscreener(["--arg1", "val1"])

        assert result == "output data"

    @pytest.mark.asyncio
    async def test_run_pkscreener_failure(self) -> None:
        """Failed Docker exec raises RuntimeError with ANSI stripped."""
        from zaza.tools.screener.docker import run_pkscreener

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"\x1b[31msome error\x1b[0m")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="some error"):
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

    @pytest.mark.asyncio
    async def test_runner_env_in_exec_args(self) -> None:
        """Docker exec includes -e RUNNER=1 to bypass Telegram login."""
        from zaza.tools.screener.docker import run_pkscreener

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await run_pkscreener(["-o", "X:15:0"])

        call_args = mock_exec.call_args[0]
        # Find -e RUNNER=1 in the args
        assert "-e" in call_args
        e_idx = call_args.index("-e")
        assert call_args[e_idx + 1] == "RUNNER=1"

    @pytest.mark.asyncio
    async def test_module_invocation(self) -> None:
        """Docker exec uses python3 -m pkscreener.pkscreenercli."""
        from zaza.tools.screener.docker import run_pkscreener

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await run_pkscreener(["-o", "X:15:0"])

        call_args = mock_exec.call_args[0]
        assert "python3" in call_args
        assert "-m" in call_args
        assert "pkscreener.pkscreenercli" in call_args

    @pytest.mark.asyncio
    async def test_mandatory_flags_prepended(self) -> None:
        """Mandatory flags (-t, -a, y, -e) are prepended to user args."""
        from zaza.tools.screener.docker import run_pkscreener

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await run_pkscreener(["-o", "X:15:7"])

        call_args = mock_exec.call_args[0]
        # After the python3 -m pkscreener.pkscreenercli, mandatory flags come first
        cli_idx = call_args.index("pkscreener.pkscreenercli")
        remaining = call_args[cli_idx + 1:]
        # Mandatory flags: -t, -a, y, -e must come before user args
        assert remaining[0] == "-t"
        assert remaining[1] == "-a"
        assert remaining[2] == "y"
        assert remaining[3] == "-e"
        # Then user args
        assert "-o" in remaining
        assert "X:15:7" in remaining

    @pytest.mark.asyncio
    async def test_full_exec_command_structure(self) -> None:
        """Full docker exec command has correct positional argument structure."""
        from zaza.tools.screener.docker import run_pkscreener

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await run_pkscreener(["-o", "X:15:7"])

        call_args = mock_exec.call_args[0]
        # Verify full positional structure: docker exec -e RUNNER=1 <container> python3 -m pkscreener.pkscreenercli -t -a y -e <user_args>
        assert call_args[1] == "exec"
        assert call_args[2] == "-e"
        assert call_args[3] == "RUNNER=1"
        # container name
        assert call_args[5] == "python3"
        assert call_args[6] == "-m"
        assert call_args[7] == "pkscreener.pkscreenercli"
        # mandatory flags
        assert call_args[8] == "-t"
        assert call_args[9] == "-a"
        assert call_args[10] == "y"
        assert call_args[11] == "-e"
        # user args
        assert call_args[12] == "-o"
        assert call_args[13] == "X:15:7"

    @pytest.mark.asyncio
    async def test_timeout_kills_process(self) -> None:
        """Process is killed on timeout to prevent leaks."""
        import asyncio as aio
        from zaza.tools.screener.docker import run_pkscreener

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=aio.TimeoutError())
        mock_proc.kill = AsyncMock()
        mock_proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(aio.TimeoutError):
                await run_pkscreener(["--slow"], timeout=1)

        mock_proc.kill.assert_called_once()
        mock_proc.wait.assert_called_once()


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
    async def test_screen_stocks_uses_nasdaq_index(self) -> None:
        """screen_stocks uses X:15: for NASDAQ market."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "Stock\tLTP\nAAPL\t195.0\n"

            tool = mcp._tool_manager.get_tool("screen_stocks")
            await tool.run(arguments={"scan_type": "momentum"})

        call_args = mock_run.call_args[0][0]
        # Should have -o X:15:7 (NASDAQ=15, momentum suffix=7)
        assert "-o" in call_args
        o_idx = call_args.index("-o")
        assert call_args[o_idx + 1].startswith("X:15:")

    @pytest.mark.asyncio
    async def test_screen_stocks_no_dash_e_market(self) -> None:
        """screen_stocks does NOT pass -e NASDAQ as args (old bug)."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "Stock\tLTP\nAAPL\t195.0\n"

            tool = mcp._tool_manager.get_tool("screen_stocks")
            await tool.run(arguments={"scan_type": "breakout"})

        call_args = mock_run.call_args[0][0]
        # Should NOT contain "-e" followed by "NASDAQ"
        for i, arg in enumerate(call_args):
            if arg == "-e" and i + 1 < len(call_args):
                assert call_args[i + 1] != "NASDAQ"

    @pytest.mark.asyncio
    async def test_screen_stocks_unsupported_market(self) -> None:
        """Unsupported market returns error."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            tool = mcp._tool_manager.get_tool("screen_stocks")
            result_str = await tool.run(
                arguments={"scan_type": "breakout", "market": "UNKNOWN_MKT"}
            )
            result = json.loads(result_str)

        assert "error" in result
        assert "Unsupported market" in result["error"]
        mock_run.assert_not_called()

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

    @pytest.mark.asyncio
    async def test_screen_stocks_nse_market_index(self) -> None:
        """screen_stocks uses X:12: for NSE market."""
        from mcp.server.fastmcp import FastMCP
        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "Stock\tLTP\nTCS\t3500.0\n"
            tool = mcp._tool_manager.get_tool("screen_stocks")
            await tool.run(arguments={"scan_type": "momentum", "market": "NSE"})

        call_args = mock_run.call_args[0][0]
        o_idx = call_args.index("-o")
        assert call_args[o_idx + 1].startswith("X:12:")

    @pytest.mark.asyncio
    async def test_screen_stocks_uses_scan_timeout(self) -> None:
        """screen_stocks passes PKSCREENER_SCAN_TIMEOUT (600s) to run_pkscreener."""
        from mcp.server.fastmcp import FastMCP

        from zaza.config import PKSCREENER_SCAN_TIMEOUT
        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "Stock\tLTP\nAAPL\t195.0\n"
            tool = mcp._tool_manager.get_tool("screen_stocks")
            await tool.run(arguments={"scan_type": "breakout"})

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == PKSCREENER_SCAN_TIMEOUT


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
    async def test_buy_sell_levels_uses_stocklist(self) -> None:
        """get_buy_sell_levels uses --stocklist instead of -e ticker."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "Stock: AAPL\nBuy Level: 190.5\n"

            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            await tool.run(arguments={"ticker": "AAPL"})

        call_args = mock_run.call_args[0][0]
        assert "--stocklist" in call_args
        assert "AAPL" in call_args

    @pytest.mark.asyncio
    async def test_buy_sell_levels_no_dash_e_ticker(self) -> None:
        """get_buy_sell_levels does NOT pass -e TICKER (old bug)."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "Stock: AAPL\nBuy Level: 190.5\n"

            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            await tool.run(arguments={"ticker": "AAPL"})

        call_args = mock_run.call_args[0][0]
        # Should NOT have -e followed by ticker
        for i, arg in enumerate(call_args):
            if arg == "-e" and i + 1 < len(call_args):
                assert call_args[i + 1] != "AAPL"

    @pytest.mark.asyncio
    async def test_buy_sell_levels_correct_market_index(self) -> None:
        """get_buy_sell_levels uses correct market index in -o flag."""
        from mcp.server.fastmcp import FastMCP

        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "Stock: AAPL\nBuy Level: 190.5\n"

            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            await tool.run(arguments={"ticker": "AAPL"})

        call_args = mock_run.call_args[0][0]
        assert "-o" in call_args
        o_idx = call_args.index("-o")
        # NASDAQ = index 15, levels suffix = 0
        assert call_args[o_idx + 1] == "X:15:0"

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

    @pytest.mark.asyncio
    async def test_buy_sell_levels_nse_market(self) -> None:
        """get_buy_sell_levels uses X:12:0 for NSE market."""
        from mcp.server.fastmcp import FastMCP
        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "Stock: TCS\nBuy Level: 3400.0\n"
            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            await tool.run(arguments={"ticker": "TCS", "market": "NSE"})

        call_args = mock_run.call_args[0][0]
        o_idx = call_args.index("-o")
        assert call_args[o_idx + 1] == "X:12:0"

    @pytest.mark.asyncio
    async def test_buy_sell_levels_uses_ticker_timeout(self) -> None:
        """get_buy_sell_levels passes PKSCREENER_TICKER_TIMEOUT (120s) to run_pkscreener."""
        from mcp.server.fastmcp import FastMCP

        from zaza.config import PKSCREENER_TICKER_TIMEOUT
        from zaza.tools.screener.pkscreener import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(_PATCH_RUN, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "Stock: AAPL\nBuy Level: 190.5\n"
            tool = mcp._tool_manager.get_tool("get_buy_sell_levels")
            await tool.run(arguments={"ticker": "AAPL"})

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == PKSCREENER_TICKER_TIMEOUT
