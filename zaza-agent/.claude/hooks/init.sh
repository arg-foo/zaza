#!/bin/bash
# SessionStart hook - runs when a new Claude Code session starts
# Creates log directories and cleans up old logs

set -euo pipefail

# Ensure log directories exist (before trace.sh runs)
mkdir -p "$HOME/.zaza/logs/sessions"

# Clean up session logs older than 90 days
find "$HOME/.zaza/logs/sessions" -name "*.jsonl" -mtime +90 -delete 2>/dev/null || true

# Clean up stale index entries (best-effort)
if [ -f "$HOME/.zaza/logs/index.jsonl" ]; then
  CUTOFF="$(date -v-90d -u '+%Y-%m-%dT' 2>/dev/null || date -u -d '90 days ago' '+%Y-%m-%dT' 2>/dev/null || echo '')"
  if [ -n "$CUTOFF" ]; then
    TMP="$(mktemp)"
    jq -c --arg cutoff "$CUTOFF" 'select(.start >= $cutoff)' "$HOME/.zaza/logs/index.jsonl" > "$TMP" 2>/dev/null || true
    if [ -s "$TMP" ]; then
      mv "$TMP" "$HOME/.zaza/logs/index.jsonl"
    else
      rm -f "$TMP"
    fi
  fi
fi

echo "Session initialized" >&2
exit 0
