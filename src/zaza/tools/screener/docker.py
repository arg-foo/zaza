"""Helper for running commands in the PKScreener Docker container.

Uses asyncio.create_subprocess_exec (never blocking subprocess.run).
"""

from __future__ import annotations

import asyncio
import re

import structlog

from zaza.config import DOCKER_PATH, PKSCREENER_CONTAINER

logger = structlog.get_logger(__name__)

# Regex to strip ANSI escape sequences from PKScreener output
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\].*?\x07|\x1b\([A-Z]|\r")

# Mandatory CLI flags: test mode, auto-answer yes, exit after run
_MANDATORY_FLAGS: tuple[str, ...] = ("-t", "-a", "y", "-e")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return _ANSI_RE.sub("", text)


async def run_pkscreener(args: list[str], timeout: int = 120) -> str:
    """Run a command in the PKScreener Docker container.

    Args:
        args: Arguments to pass to pkscreenercli.
        timeout: Timeout in seconds (default 120).

    Returns:
        The stdout output as a string (ANSI stripped).

    Raises:
        RuntimeError: If the container command fails.
        asyncio.TimeoutError: If the command times out.
    """
    full_args = list(_MANDATORY_FLAGS) + args
    proc = await asyncio.create_subprocess_exec(
        DOCKER_PATH,
        "exec",
        "-e", "RUNNER=1",
        PKSCREENER_CONTAINER,
        "python3", "-m", "pkscreener.pkscreenercli",
        *full_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    if proc.returncode != 0:
        error_msg = strip_ansi(stderr.decode().strip())
        logger.warning("pkscreener_error", args=full_args, error=error_msg)
        raise RuntimeError(f"PKScreener error: {error_msg}")
    return strip_ansi(stdout.decode())
