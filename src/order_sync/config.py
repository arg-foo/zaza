"""Configuration for the Order Sync Worker.

MCP server URLs, retry settings, and logging configuration.
All values are overridable via environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path

# MCP server endpoints
ZAZA_MCP_URL = os.environ.get("ZAZA_MCP_URL", "http://localhost:8100/mcp")
TIGER_MCP_URL = os.environ.get("TIGER_MCP_URL", "http://localhost:8000/mcp")

# MCP connection retry settings
MCP_CONNECT_RETRIES = 3
MCP_CONNECT_BACKOFF_BASE = 2.0  # seconds

# Logging
LOG_DIR = Path.home() / ".zaza" / "logs"
LOG_FILE = LOG_DIR / "order_sync.log"
