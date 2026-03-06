#!/bin/bash
# Install the order-sync launchd agent for scheduled execution.
#
# Copies the plist to ~/Library/LaunchAgents/ and loads it.
# Run from the project root: ./scripts/install_launchd.sh

set -euo pipefail

PLIST_NAME="com.zaza.order-sync.plist"
PLIST_SRC="$(cd "$(dirname "$0")/.." && pwd)/${PLIST_NAME}"
PLIST_DEST="$HOME/Library/LaunchAgents/${PLIST_NAME}"
LOG_DIR="$HOME/.zaza/logs"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Unload if already loaded
if launchctl list | grep -q "com.zaza.order-sync"; then
    echo "Unloading existing agent..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Copy plist
echo "Copying ${PLIST_NAME} to ~/Library/LaunchAgents/"
cp "$PLIST_SRC" "$PLIST_DEST"

# Load
echo "Loading agent..."
launchctl load "$PLIST_DEST"

# Verify
if launchctl list | grep -q "com.zaza.order-sync"; then
    echo "Successfully installed and loaded com.zaza.order-sync"
    echo "Schedule: weekdays at 9:25 AM ET (13:25 UTC during EDT)"
    echo "Logs: ${LOG_DIR}/order_sync_*.log"
else
    echo "ERROR: Agent not found after loading" >&2
    exit 1
fi
