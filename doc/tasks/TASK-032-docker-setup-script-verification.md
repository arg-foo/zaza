# TASK-032: Create Docker Setup Script & Verification

## Task ID
TASK-032

## Status
COMPLETED

## Title
Create Docker Setup Script & Verification

## Description
Create `setup-docker.sh`, a one-command script that automates the entire Docker setup: checking prerequisites, creating a `.env` template, building the image, starting the PKScreener sidecar, and verifying the MCP server health check. This provides a frictionless onboarding experience for users who want to run Zaza in Docker.

This task also includes running all verification checks from the Docker plan to ensure the full stack works end-to-end.

## Acceptance Criteria

### Functional Requirements
- [ ] `setup-docker.sh` created and executable (`chmod +x`)
- [ ] Script checks for Docker and Docker Compose availability, exits with clear error if missing
- [ ] Script creates `.env` template file with placeholder keys if `.env` doesn't exist
- [ ] Script builds the runtime image (`docker build --target runtime -t zaza .`)
- [ ] Script starts PKScreener via `docker compose up -d pkscreener`
- [ ] Script runs `docker run --rm zaza python -m zaza.server --check` to verify health
- [ ] Script prints clear success/failure message with next steps
- [ ] All 6 verification checks pass:
  1. `docker build --target runtime -t zaza .` — builds successfully
  2. `docker run --rm zaza python -m zaza.server --check` — health check passes
  3. `echo '{}' | docker run -i --rm zaza` — stdin/stdout pipe works
  4. `docker build --target dev -t zaza-dev .` — dev target builds
  5. `docker run --rm zaza-dev` — tests pass in container
  6. `docker compose up -d && docker compose ps` — both services running
- [ ] Existing `uv run pytest tests/` still passes (backward compatibility)

### Non-Functional Requirements
- [ ] **Testing**: Manual verification checklist (Docker builds are not unit-testable)
- [ ] **Observability**: Script uses colored output and clear step numbering
- [ ] **Security**: `.env` template contains only placeholder values, not real keys
- [ ] **Documentation**: Script includes usage instructions in header comments

## Dependencies
- TASK-029: Config env var overrides (required for Docker cache path)
- TASK-030: Dockerfile (required to build)
- TASK-031: Docker Compose (required for orchestration verification)

## Technical Notes

### setup-docker.sh Structure

```bash
#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== Zaza Docker Setup ==="

# Step 1: Check prerequisites
echo "[1/5] Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    echo "Install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not available.${NC}"
    exit 1
fi

echo -e "${GREEN}Docker and Docker Compose found.${NC}"

# Step 2: Create .env if needed
echo "[2/5] Checking .env file..."
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Optional API keys for enhanced functionality
# Reddit credentials (enables social sentiment)
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
# FRED API key (enables economic calendar)
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
echo "[4/5] Starting PKScreener sidecar..."
docker compose up -d pkscreener || {
    echo -e "${YELLOW}Warning: PKScreener failed to start. Stock screening tools will be unavailable.${NC}"
}

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
```

### .env Template

```bash
# Optional API keys for enhanced functionality
# Core tools (yfinance, SEC EDGAR) require no keys.

# Reddit credentials (enables social sentiment tool)
# Register at: https://www.reddit.com/prefs/apps/
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=

# FRED API key (enables economic calendar tool)
# Register at: https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY=
```

### Verification Checklist

Run these manually after `setup-docker.sh` completes:

| # | Command | Expected Result |
|---|---------|----------------|
| 1 | `docker build --target runtime -t zaza .` | Builds without errors |
| 2 | `docker run --rm zaza python -m zaza.server --check` | Prints health check pass |
| 3 | `echo '{}' \| docker run -i --rm zaza` | Reads from stdin, writes to stdout |
| 4 | `docker build --target dev -t zaza-dev .` | Builds without errors |
| 5 | `docker run --rm zaza-dev` | Tests pass |
| 6 | `docker compose up -d && docker compose ps` | Both services show as running |
| 7 | `uv run pytest tests/` | All existing tests still pass |

### Implementation Hints
1. Use `set -euo pipefail` for strict error handling — any failure stops the script
2. The PKScreener step should warn but not fail the entire setup (it's optional for most users)
3. Consider adding a `--no-pkscreener` flag for users who don't need stock screening
4. The stdin/stdout pipe test (check #3) may need a timeout since the MCP server will wait for input

## Estimated Complexity
**Small** (2-3 hours)

## References
- doc/DOCKER-PLAN.md Sections 5, 7 (setup-docker.sh, Verification)
