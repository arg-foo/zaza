#!/bin/bash
# SessionStart hook - runs when a new Claude Code session starts
# Add initialization logic below (env vars, dependency checks, etc.)

# Example: persist env vars for the session
# if [ -n "$CLAUDE_ENV_FILE" ]; then
#   echo 'export MY_VAR=value' >> "$CLAUDE_ENV_FILE"
# fi

echo "Session initialized" >&2
exit 0
