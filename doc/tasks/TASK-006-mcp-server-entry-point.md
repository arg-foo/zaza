# TASK-006: MCP Server Entry Point

## Task ID
TASK-006

## Status
COMPLETED

## Title
Implement MCP Server Entry Point

## Description
Implement the MCP server skeleton in `src/zaza/server.py`. This is the entry point that Claude Code launches as a subprocess. It initializes the MCP server, registers tool handlers, and communicates over stdin/stdout using the MCP protocol.

Initially this will be a skeleton with the server infrastructure but no tool registrations — tools will be wired in as they are implemented in later tasks. The server should start, run, and respond to MCP protocol messages.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/server.py` implemented with MCP server initialization
- [ ] Uses `mcp.server.Server` and `mcp.server.stdio.stdio_server`
- [ ] `async def main()` starts the server on stdin/stdout
- [ ] Placeholder `register_*_tools(app)` functions for all 11 tool domains (initially no-ops)
- [ ] `--check` flag: starts server, verifies initialization, exits cleanly (for health checks)
- [ ] `src/zaza/__main__.py` calls `server.main()` via `asyncio.run()`
- [ ] Server starts successfully with `uv run python -m zaza.server`
- [ ] Server responds to MCP `tools/list` request (returns empty list initially)

### Non-Functional Requirements
- [ ] **Testing**: Integration test that starts the server subprocess and verifies MCP handshake
- [ ] **Observability**: Logging on server start, tool registration, and errors
- [ ] **Reliability**: Graceful shutdown on SIGINT/SIGTERM
- [ ] **Documentation**: Docstrings explaining server architecture

## Dependencies
- TASK-001: Project scaffolding
- TASK-002: Configuration module

## Technical Notes

### Server Structure
```python
# src/zaza/server.py
import asyncio
import logging
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server

logger = logging.getLogger(__name__)

app = Server("zaza")

def register_finance_tools(app: Server): pass  # TASK-012, TASK-013, TASK-014
def register_ta_tools(app: Server): pass        # TASK-015
def register_options_tools(app: Server): pass    # TASK-016
def register_sentiment_tools(app: Server): pass  # TASK-017
def register_macro_tools(app: Server): pass      # TASK-018
def register_quantitative_tools(app: Server): pass  # TASK-019
def register_institutional_tools(app: Server): pass  # TASK-020
def register_earnings_tools(app: Server): pass   # TASK-021
def register_backtesting_tools(app: Server): pass  # TASK-022
def register_screener_tools(app: Server): pass   # TASK-023
def register_browser_tools(app: Server): pass    # TASK-024

async def main():
    if "--check" in sys.argv:
        logger.info("Zaza MCP server check passed")
        return

    logger.info("Starting Zaza MCP server")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream)
```

### __main__.py
```python
import asyncio
from zaza.server import main

if __name__ == "__main__":
    asyncio.run(main())
```

### Implementation Hints
1. The MCP Python SDK uses `mcp.server.Server` — check the latest API
2. Tool registration functions will be replaced with real implementations as tool tasks complete
3. The `--check` flag is used by setup.sh to verify the server starts correctly
4. Configure logging to stderr (stdout is reserved for MCP protocol)

## Estimated Complexity
**Small** (2-3 hours)

## References
- ZAZA_ARCHITECTURE.md Section 5 (MCP Server)
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
