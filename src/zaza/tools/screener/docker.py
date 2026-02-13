"""Helper for running commands in the PKScreener Docker container.

Uses asyncio.create_subprocess_exec (never blocking subprocess.run).
"""

from __future__ import annotations

import asyncio

import structlog

from zaza.config import PKSCREENER_CONTAINER

logger = structlog.get_logger(__name__)


async def run_pkscreener(args: list[str], timeout: int = 120) -> str:
    """Run a command in the PKScreener Docker container.

    Args:
        args: Arguments to pass to pkscreenercli.py.
        timeout: Timeout in seconds (default 120).

    Returns:
        The stdout output as a string.

    Raises:
        RuntimeError: If the container command fails.
        asyncio.TimeoutError: If the command times out.
    """
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "exec",
        PKSCREENER_CONTAINER,
        "python3",
        "pkscreener/pkscreenercli.py",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    if proc.returncode != 0:
        error_msg = stderr.decode().strip()
        logger.warning("pkscreener_error", args=args, error=error_msg)
        raise RuntimeError(f"PKScreener error: {error_msg}")
    return stdout.decode()
