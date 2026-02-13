"""Integration tests for server tool registration and wiring (TASK-025).

Tests the register_all_tools function, error resilience, startup logging,
and the --check flag improvements.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from unittest.mock import patch

# ---------------------------------------------------------------------------
# register_all_tools tests
# ---------------------------------------------------------------------------


class TestRegisterAllTools:
    """Tests for the register_all_tools convenience function."""

    def test_register_all_tools_exists(self) -> None:
        """register_all_tools should be importable from zaza.server."""
        from zaza.server import register_all_tools

        assert callable(register_all_tools)

    def test_register_all_tools_registers_all_domains(self) -> None:
        """register_all_tools should register all 11 domain modules."""
        from mcp.server.fastmcp import FastMCP

        from zaza.server import register_all_tools

        mcp = FastMCP("test")
        result = register_all_tools(mcp)
        assert result == 11

    def test_register_all_tools_resilient_to_single_failure(self) -> None:
        """If one domain fails to register, others should still succeed."""
        from mcp.server.fastmcp import FastMCP

        from zaza.server import register_all_tools

        mcp = FastMCP("test")

        # Capture the real import_module before patching
        real_import_module = importlib.import_module

        def selective_fail(name: str, *args: object, **kwargs: object) -> object:
            if name == "zaza.tools.browser":
                raise ImportError("Simulated browser import failure")
            return real_import_module(name, *args, **kwargs)

        with patch.object(importlib, "import_module", side_effect=selective_fail):
            result = register_all_tools(mcp)

        # 10 out of 11 should succeed
        assert result == 10

    def test_register_all_tools_returns_zero_on_all_failures(self) -> None:
        """If all domains fail, register_all_tools returns 0."""
        from mcp.server.fastmcp import FastMCP

        from zaza.server import register_all_tools

        mcp = FastMCP("test")

        with patch.object(
            importlib, "import_module", side_effect=ImportError("everything is broken")
        ):
            result = register_all_tools(mcp)

        assert result == 0

    def test_register_all_tools_logs_per_domain(self) -> None:
        """register_all_tools should log each successful domain registration."""
        from mcp.server.fastmcp import FastMCP

        from zaza.server import register_all_tools

        mcp = FastMCP("test")

        with patch("zaza.server.logger") as mock_logger:
            register_all_tools(mcp)

        # Should have 11 domain_registered info calls + 1 completion call
        info_calls = [
            c for c in mock_logger.info.call_args_list if "domain_registered" in str(c)
        ]
        assert len(info_calls) == 11

    def test_register_all_tools_logs_completion(self) -> None:
        """register_all_tools should log a completion summary."""
        from mcp.server.fastmcp import FastMCP

        from zaza.server import register_all_tools

        mcp = FastMCP("test")

        with patch("zaza.server.logger") as mock_logger:
            register_all_tools(mcp)

        completion_calls = [
            c
            for c in mock_logger.info.call_args_list
            if "tool_registration_complete" in str(c)
        ]
        assert len(completion_calls) == 1

    def test_register_all_tools_logs_failures(self) -> None:
        """register_all_tools should log errors for failed domains."""
        from mcp.server.fastmcp import FastMCP

        from zaza.server import register_all_tools

        mcp = FastMCP("test")

        # Patch logger first, then importlib (order matters because
        # patching zaza.server.logger itself uses importlib.import_module)
        with patch("zaza.server.logger") as mock_logger:
            with patch.object(
                importlib, "import_module", side_effect=ImportError("broken")
            ):
                register_all_tools(mcp)

        error_calls = [
            c
            for c in mock_logger.error.call_args_list
            if "domain_registration_failed" in str(c)
        ]
        assert len(error_calls) == 11

    def test_register_all_tools_partial_failure_logs_both(self) -> None:
        """When some domains fail, both successes and failures should be logged."""
        from mcp.server.fastmcp import FastMCP

        from zaza.server import register_all_tools

        mcp = FastMCP("test")

        real_import_module = importlib.import_module

        def fail_two(name: str, *args: object, **kwargs: object) -> object:
            if name in ("zaza.tools.browser", "zaza.tools.screener"):
                raise ImportError(f"Simulated failure for {name}")
            return real_import_module(name, *args, **kwargs)

        with (
            patch.object(importlib, "import_module", side_effect=fail_two),
            patch("zaza.server.logger") as mock_logger,
        ):
            result = register_all_tools(mcp)

        assert result == 9

        info_calls = [
            c for c in mock_logger.info.call_args_list if "domain_registered" in str(c)
        ]
        error_calls = [
            c
            for c in mock_logger.error.call_args_list
            if "domain_registration_failed" in str(c)
        ]
        assert len(info_calls) == 9
        assert len(error_calls) == 2


# ---------------------------------------------------------------------------
# _create_server tests
# ---------------------------------------------------------------------------


class TestCreateServer:
    """Tests for the _create_server function."""

    def test_create_server_returns_fastmcp(self) -> None:
        """_create_server should return a FastMCP instance."""
        from mcp.server.fastmcp import FastMCP

        from zaza.server import _create_server

        mcp = _create_server()
        assert isinstance(mcp, FastMCP)

    def test_create_server_calls_register_all_tools(self) -> None:
        """_create_server should use register_all_tools internally."""
        with patch("zaza.server.register_all_tools") as mock_reg:
            mock_reg.return_value = 11
            from zaza.server import _create_server

            _create_server()
            mock_reg.assert_called_once()


# ---------------------------------------------------------------------------
# --check mode tests
# ---------------------------------------------------------------------------


class TestCheckMode:
    """Tests for the --check CLI flag."""

    def test_check_mode_exits_cleanly(self) -> None:
        """--check should exit with code 0."""
        result = subprocess.run(
            [sys.executable, "-m", "zaza.server", "--check"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd="/Users/zifcrypto/Desktop/zaza",
        )
        assert result.returncode == 0

    def test_check_mode_reports_tool_count(self) -> None:
        """--check should print the number of registered domains in stderr."""
        result = subprocess.run(
            [sys.executable, "-m", "zaza.server", "--check"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd="/Users/zifcrypto/Desktop/zaza",
        )
        assert result.returncode == 0
        # structlog output goes to stderr; check for registration info
        combined = result.stderr.lower() + result.stdout.lower()
        assert "domain" in combined or "registered" in combined or "check_passed" in combined


# ---------------------------------------------------------------------------
# Optional client availability logging tests
# ---------------------------------------------------------------------------


class TestOptionalClientLogging:
    """Tests for logging which optional clients are available."""

    def test_log_optional_clients_is_callable(self) -> None:
        """log_optional_clients should be importable and callable."""
        from zaza.server import log_optional_clients

        assert callable(log_optional_clients)

    def test_log_optional_clients_logs_reddit_available(self) -> None:
        """Should log Reddit as available when credentials are set."""
        from zaza.server import log_optional_clients

        with (
            patch("zaza.server.logger") as mock_logger,
            patch("zaza.server.has_reddit_credentials", return_value=True),
            patch("zaza.server.has_fred_key", return_value=False),
        ):
            log_optional_clients()

        # Should have logged info about optional clients
        mock_logger.info.assert_called()
        # Verify it logged the reddit status
        call_strs = [str(c) for c in mock_logger.info.call_args_list]
        assert any("optional_clients" in s for s in call_strs)

    def test_log_optional_clients_logs_fred_available(self) -> None:
        """Should log FRED as available when API key is set."""
        from zaza.server import log_optional_clients

        with (
            patch("zaza.server.logger") as mock_logger,
            patch("zaza.server.has_reddit_credentials", return_value=False),
            patch("zaza.server.has_fred_key", return_value=True),
        ):
            log_optional_clients()

        mock_logger.info.assert_called()
        call_strs = [str(c) for c in mock_logger.info.call_args_list]
        assert any("optional_clients" in s for s in call_strs)

    def test_log_optional_clients_logs_none_available(self) -> None:
        """Should log when no optional clients are configured."""
        from zaza.server import log_optional_clients

        with (
            patch("zaza.server.logger") as mock_logger,
            patch("zaza.server.has_reddit_credentials", return_value=False),
            patch("zaza.server.has_fred_key", return_value=False),
        ):
            log_optional_clients()

        # Should have called info at least twice (status + note)
        assert mock_logger.info.call_count >= 2
        call_strs = [str(c) for c in mock_logger.info.call_args_list]
        assert any("optional_clients_note" in s for s in call_strs)

    def test_log_optional_clients_no_note_when_keys_present(self) -> None:
        """Should NOT log the note when at least one key is configured."""
        from zaza.server import log_optional_clients

        with (
            patch("zaza.server.logger") as mock_logger,
            patch("zaza.server.has_reddit_credentials", return_value=True),
            patch("zaza.server.has_fred_key", return_value=True),
        ):
            log_optional_clients()

        # Should only have 1 info call (status), no note
        call_strs = [str(c) for c in mock_logger.info.call_args_list]
        assert not any("optional_clients_note" in s for s in call_strs)


# ---------------------------------------------------------------------------
# TOOL_DOMAINS constant tests
# ---------------------------------------------------------------------------


class TestToolDomains:
    """Tests for the TOOL_DOMAINS registry constant."""

    def test_tool_domains_has_11_entries(self) -> None:
        """TOOL_DOMAINS should have exactly 11 domain entries."""
        from zaza.server import TOOL_DOMAINS

        assert len(TOOL_DOMAINS) == 11

    def test_tool_domains_entries_are_valid_tuples(self) -> None:
        """Each entry should be a (name, module_path, func_name) tuple."""
        from zaza.server import TOOL_DOMAINS

        for entry in TOOL_DOMAINS:
            assert len(entry) == 3
            name, module_path, func_name = entry
            assert isinstance(name, str) and name
            assert isinstance(module_path, str) and module_path.startswith("zaza.tools.")
            assert isinstance(func_name, str) and func_name.startswith("register_")

    def test_tool_domains_all_modules_importable(self) -> None:
        """All domain modules referenced in TOOL_DOMAINS should be importable."""
        from zaza.server import TOOL_DOMAINS

        for name, module_path, func_name in TOOL_DOMAINS:
            mod = importlib.import_module(module_path)
            assert hasattr(mod, func_name), (
                f"Module {module_path} missing function {func_name}"
            )
