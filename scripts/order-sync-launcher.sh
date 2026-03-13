#!/usr/bin/env bash
# Wrapper for launchd: waits for the working directory to be available
# before invoking uv. Handles slow disk mounts after sleep/restart.

WORKDIR="/Users/zifcrypto/Desktop/zaza"
MAX_WAIT=30  # seconds
INTERVAL=2   # seconds between checks

elapsed=0
while [ ! -d "$WORKDIR" ]; do
    if [ "$elapsed" -ge "$MAX_WAIT" ]; then
        echo "ERROR: $WORKDIR not available after ${MAX_WAIT}s" >&2
        exit 1
    fi
    sleep "$INTERVAL"
    elapsed=$((elapsed + INTERVAL))
done

cd "$WORKDIR" || exit 1
exec /Users/zifcrypto/.local/bin/uv run python -m order_sync "$@"
