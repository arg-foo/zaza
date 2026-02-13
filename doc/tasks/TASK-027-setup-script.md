# TASK-027: Setup Script & Environment Configuration

## Task ID
TASK-027

## Status
PENDING

## Title
Implement Setup Script & Environment Configuration

## Description
Create `setup.sh` — a one-command setup script that installs all dependencies, configures Claude Code's MCP server settings, optionally starts the PKScreener Docker container, installs Playwright browsers, and verifies the MCP server starts correctly.

This is the "getting started" experience for new users.

## Acceptance Criteria

### Functional Requirements
- [ ] `setup.sh` created at project root
- [ ] Installs Python dependencies via `uv sync`
- [ ] Creates `.env` from `.env.example` if `.env` doesn't exist
- [ ] Configures Claude Code MCP settings in `.claude/settings.json`
- [ ] Installs Playwright Chromium browser: `uv run playwright install chromium`
- [ ] Optionally starts PKScreener Docker container (with prompt or flag)
- [ ] Creates cache directories (`~/.zaza/cache/`, `~/.zaza/cache/predictions/`)
- [ ] Verifies MCP server starts: `uv run python -m zaza.server --check`
- [ ] Prints success message with next steps
- [ ] Handles errors gracefully with clear messages

### Non-Functional Requirements
- [ ] **Documentation**: Script includes comments explaining each step
- [ ] **Reliability**: Idempotent — safe to run multiple times
- [ ] **Observability**: Progress messages for each step

## Dependencies
- TASK-001: Project scaffolding
- TASK-006: MCP server entry point
- TASK-025: Server tool registration (for --check verification)

## Technical Notes

### Script Structure
```bash
#!/bin/bash
set -e

echo "=== Zaza Financial Research Agent Setup ==="

# 1. Check prerequisites
command -v uv >/dev/null 2>&1 || { echo "Error: uv not installed"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Error: Python 3 not installed"; exit 1; }

# 2. Install dependencies
echo "Installing dependencies..."
uv sync

# 3. Create .env if needed
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example — edit to add optional API keys"
fi

# 4. Configure Claude Code MCP
mkdir -p .claude
cat > .claude/settings.json << 'EOF'
{
  "mcpServers": {
    "zaza": {
      "command": "uv",
      "args": ["run", "--directory", ".", "python", "-m", "zaza.server"]
    }
  }
}
EOF
echo "Configured Claude Code MCP settings"

# 5. Install Playwright browsers
echo "Installing Playwright Chromium..."
uv run playwright install chromium

# 6. Create cache directories
mkdir -p ~/.zaza/cache/predictions

# 7. Optional: Start PKScreener Docker
if command -v docker >/dev/null 2>&1; then
    read -p "Start PKScreener Docker container? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker run -d --name pkscreener \
            -e PKSCREENER_DOCKER=1 \
            -v pkscreener-data:/PKScreener-main/actions_data \
            pkjmesra/pkscreener:latest \
            sleep infinity 2>/dev/null || echo "PKScreener container already exists"
    fi
fi

# 8. Verify server
echo "Verifying MCP server..."
uv run python -m zaza.server --check

echo ""
echo "=== Setup complete! ==="
echo "Start Claude Code in this directory to use Zaza."
echo ""
echo "Optional: Set these in .env for additional features:"
echo "  REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET — Social sentiment"
echo "  FRED_API_KEY — Economic calendar"
```

### Implementation Hints
1. Use `set -e` to stop on first error
2. Check for `uv` and `python3` before anything else
3. The `.claude/settings.json` path is relative to project root
4. Make idempotent — check before creating/overwriting
5. The PKScreener Docker step should be optional (not everyone has Docker)

## Estimated Complexity
**Small** (2-3 hours)

## References
- ZAZA_ARCHITECTURE.md Section 13 (Configuration & Setup)
