"""Zaza MCP server entry point.

Communicates with Claude Code over stdin/stdout using the MCP protocol.
Registers all 66 financial research tools organized across 11 domains.
"""

from __future__ import annotations

import importlib
import logging
import sys

import structlog

from zaza.config import has_fred_key, has_reddit_credentials

# Configure logging to stderr (stdout is reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stderr,
)

# Configure structlog to use stdlib logging (which writes to stderr)
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger(__name__)

# Domain registry: (display_name, module_path, registration_function_name)
TOOL_DOMAINS: list[tuple[str, str, str]] = [
    ("finance", "zaza.tools.finance", "register_finance_tools"),
    ("ta", "zaza.tools.ta", "register_ta_tools"),
    ("options", "zaza.tools.options", "register_options_tools"),
    ("sentiment", "zaza.tools.sentiment", "register_sentiment_tools"),
    ("macro", "zaza.tools.macro", "register_macro_tools"),
    ("quantitative", "zaza.tools.quantitative", "register_quantitative_tools"),
    ("institutional", "zaza.tools.institutional", "register_institutional_tools"),
    ("earnings", "zaza.tools.earnings", "register_earnings_tools"),
    ("backtesting", "zaza.tools.backtesting", "register_backtesting_tools"),
    ("screener", "zaza.tools.screener", "register_screener_tools"),
    ("browser", "zaza.tools.browser", "register_browser_tools"),
]


def register_all_tools(mcp: object) -> int:
    """Register all tool domains with the MCP server.

    Iterates through all 11 domain modules, importing and calling each
    registration function. If a domain fails to register, the error is
    logged and registration continues with remaining domains.

    Args:
        mcp: A FastMCP server instance.

    Returns:
        The number of domains successfully registered.
    """
    registered = 0
    for name, module_path, func_name in TOOL_DOMAINS:
        try:
            mod = importlib.import_module(module_path)
            getattr(mod, func_name)(mcp)
            logger.info("domain_registered", domain=name)
            registered += 1
        except Exception as e:
            logger.error(
                "domain_registration_failed",
                domain=name,
                error=str(e),
            )
    logger.info(
        "tool_registration_complete",
        domains_registered=registered,
        domains_total=len(TOOL_DOMAINS),
    )
    if registered < len(TOOL_DOMAINS):
        logger.warning(
            "incomplete_tool_registration",
            failed_count=len(TOOL_DOMAINS) - registered,
        )
    return registered


def log_optional_clients() -> None:
    """Log which optional API clients are available.

    Checks for Reddit credentials and FRED API key in the environment
    and logs their availability status.
    """
    reddit_available = has_reddit_credentials()
    fred_available = has_fred_key()

    logger.info(
        "optional_clients",
        reddit=reddit_available,
        fred=fred_available,
    )

    if not reddit_available and not fred_available:
        logger.info(
            "optional_clients_note",
            message=(
                "No optional API keys configured. "
                "Set REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET "
                "and/or FRED_API_KEY to enable additional tools."
            ),
        )


def _create_server() -> object:
    """Create and configure the MCP server.

    Returns:
        A configured FastMCP server instance with all tool domains registered.
    """
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("zaza")
    register_all_tools(mcp)
    return mcp


async def main() -> None:
    """Start the Zaza MCP server.

    Supports a ``--check`` flag for health checks: creates the server,
    logs the count of registered domains, and exits without entering
    the event loop.
    """
    if "--check" in sys.argv:
        # Health check mode: verify server can be created, then exit
        _create_server()
        log_optional_clients()
        logger.info("zaza_check_passed", status="ok")
        return

    logger.info("zaza_server_starting")
    log_optional_clients()
    mcp = _create_server()
    await mcp.run_stdio_async()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
