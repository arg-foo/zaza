"""Tests for MCP server entry point."""

import subprocess
import sys


def test_server_check_mode():
    """Verify --check flag works (creates server, exits cleanly)."""
    result = subprocess.run(
        [sys.executable, "-m", "zaza.server", "--check"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd="/Users/zifcrypto/Desktop/zaza",
    )
    assert result.returncode == 0


def test_server_creates_without_error():
    """Verify _create_server doesn't raise."""
    from zaza.server import _create_server

    mcp = _create_server()
    assert mcp is not None


def test_server_import():
    """Verify server module can be imported."""
    from zaza.server import main

    assert callable(main)
