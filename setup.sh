#!/bin/bash
set -e

echo "=== Zaza Financial Research Agent Setup ==="
echo ""

# 1. Check prerequisites
command -v uv >/dev/null 2>&1 || { echo "Error: uv is not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }

PYTHON_VERSION=$(uv run python --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1)
if [ -n "$PYTHON_VERSION" ]; then
    MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 12 ]; }; then
        echo "Error: Python >= 3.12 is required (found $PYTHON_VERSION)"
        exit 1
    fi
fi

# 2. Install dependencies
echo "[1/6] Installing Python dependencies..."
uv sync

# 3. Create .env from .env.example if it doesn't exist
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "[2/6] Created .env from .env.example — edit to add optional API keys"
    else
        echo "[2/6] No .env.example found, skipping .env creation"
    fi
else
    echo "[2/6] .env already exists, skipping"
fi

# 4. Configure Claude Code MCP settings
mkdir -p .claude
if [ ! -f .claude/settings.json ]; then
    cat > .claude/settings.json << 'SETTINGS_EOF'
{
  "mcpServers": {
    "zaza": {
      "command": "uv",
      "args": ["run", "--directory", ".", "python", "-m", "zaza.server"]
    }
  }
}
SETTINGS_EOF
    echo "[3/6] Configured Claude Code MCP settings"
else
    # Ensure mcpServers.zaza exists even if settings.json was already present
    if command -v python3 >/dev/null 2>&1 && python3 -c "import json" 2>/dev/null; then
        if ! python3 -c "
import json, sys
with open('.claude/settings.json') as f:
    data = json.load(f)
sys.exit(0 if 'mcpServers' in data and 'zaza' in data.get('mcpServers', {}) else 1)
" 2>/dev/null; then
            echo "[3/6] Warning: .claude/settings.json exists but may be missing Zaza MCP config"
            echo "       Ensure it contains:"
            echo '       "mcpServers": { "zaza": { "command": "uv", "args": ["run", "--directory", ".", "python", "-m", "zaza.server"] } }'
        else
            echo "[3/6] .claude/settings.json already configured with Zaza MCP server"
        fi
    else
        echo "[3/6] .claude/settings.json already exists, skipping"
    fi
fi

# 5. Install Playwright browsers
echo "[4/6] Installing Playwright Chromium browser..."
uv run playwright install chromium 2>/dev/null || echo "  Warning: Playwright install failed — browser tools won't be available"

# 6. Create cache directories
mkdir -p ~/.zaza/cache/predictions
echo "[5/6] Cache directories ready"

# 7. Optional: Start PKScreener Docker
if command -v docker >/dev/null 2>&1; then
    if ! docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q '^pkscreener$'; then
        echo ""
        read -p "  Start PKScreener Docker container for stock screening? (y/N) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker run -d --name pkscreener \
                -e PKSCREENER_DOCKER=1 \
                -v pkscreener-data:/PKScreener-main/actions_data \
                pkjmesra/pkscreener:latest \
                sleep infinity
            echo "  PKScreener container started"
        else
            echo "  Skipping PKScreener setup"
        fi
    else
        echo "  PKScreener container already exists"
    fi
else
    echo "  Docker not found — skipping PKScreener setup (optional, needed for stock screening tools)"
fi

# 8. Verify server
echo "[6/6] Verifying MCP server..."
if uv run python -m zaza.server --check 2>/dev/null; then
    echo "  MCP server verification passed"
else
    echo "  Warning: MCP server verification failed — this is expected if server.py is not yet implemented"
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Start Claude Code in this directory to use Zaza."
echo ""
echo "Optional: Set these in .env for additional features:"
echo "  REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET — Social sentiment from Reddit"
echo "  FRED_API_KEY — Economic calendar from Federal Reserve"
