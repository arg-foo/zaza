#!/usr/bin/env bash
# ============================================================
# Zaza Docker Setup Script
# ============================================================
# Automates the full Docker setup:
#   1. Check prerequisites (Docker, Docker Compose)
#   2. Create .env template (if missing)
#   3. Build the runtime Docker image
#   4. Start PKScreener sidecar container
#   5. Verify MCP server health check
#
# Usage:
#   chmod +x setup-docker.sh
#   ./setup-docker.sh
#
# Options:
#   --no-pkscreener   Skip PKScreener sidecar (stock screening unavailable)
# ============================================================
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse flags
SKIP_PKSCREENER=0
for arg in "$@"; do
    case "$arg" in
        --no-pkscreener) SKIP_PKSCREENER=1 ;;
    esac
done

echo "=== Zaza Docker Setup ==="
echo ""

# Step 1: Check prerequisites
echo "[1/5] Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    echo "Install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not available.${NC}"
    echo "Docker Compose is included with Docker Desktop, or install the plugin:"
    echo "  https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}Docker and Docker Compose found.${NC}"

# Step 2: Create .env if needed
echo "[2/5] Checking .env file..."
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Optional API keys for enhanced functionality
# Core tools (yfinance, SEC EDGAR) require no keys.

# Reddit credentials (enables social sentiment tool)
# Register at: https://www.reddit.com/prefs/apps/
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=

# FRED API key (enables economic calendar tool)
# Register at: https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY=
EOF
    echo -e "${YELLOW}Created .env template. Edit it to add API keys (optional).${NC}"
else
    echo ".env already exists."
fi

# Step 3: Build Docker image
echo "[3/5] Building Zaza Docker image..."
docker build --target runtime -t zaza . || {
    echo -e "${RED}Docker build failed.${NC}"
    exit 1
}
echo -e "${GREEN}Image built successfully.${NC}"

# Step 4: Start PKScreener sidecar
if [ "$SKIP_PKSCREENER" = "1" ]; then
    echo "[4/5] Skipping PKScreener (--no-pkscreener flag)."
else
    echo "[4/5] Starting PKScreener sidecar..."
    docker compose up -d pkscreener || {
        echo -e "${YELLOW}Warning: PKScreener failed to start. Stock screening tools will be unavailable.${NC}"
    }
    # Verify PKScreener is responsive
    if docker exec pkscreener echo OK &> /dev/null; then
        echo -e "${GREEN}PKScreener sidecar is running.${NC}"
    else
        echo -e "${YELLOW}Warning: PKScreener started but is not responsive yet. It may need a moment.${NC}"
    fi
fi

# Step 5: Verify health check
echo "[5/5] Verifying MCP server..."
docker run --rm zaza python -m zaza.server --check || {
    echo -e "${RED}Health check failed.${NC}"
    exit 1
}

echo ""
echo -e "${GREEN}=== Setup complete! ===${NC}"
echo ""
echo "Next steps:"
echo "  1. Copy Docker settings to Claude Code:"
echo "     cp .claude/settings.docker.json .claude/settings.json"
echo "  2. (Optional) Edit .env to add Reddit/FRED API keys"
echo "  3. Start Claude Code — Zaza tools are now available via Docker"
