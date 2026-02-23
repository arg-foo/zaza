#!/bin/bash
# trace.sh — Unified tracing hook for all 7 Claude Code hook events.
# Reads JSON from stdin, routes by hook_event_name, writes JSONL logs.
# Log path: ~/.zaza/logs/sessions/YYYY-MM-DD_<session_id>.jsonl

set -euo pipefail

LOG_DIR="$HOME/.zaza/logs/sessions"
INDEX_FILE="$HOME/.zaza/logs/index.jsonl"
MAX_RESPONSE_LEN=2000

# Ensure log directory exists (guard for non-SessionStart events)
mkdir -p "$LOG_DIR"

# Read hook JSON from stdin
INPUT="$(cat)"

# Guard against malformed JSON
if ! EVENT="$(printf '%s' "$INPUT" | jq -r '.hook_event_name // empty' 2>/dev/null)"; then
  exit 0
fi
if ! SESSION_ID="$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)"; then
  exit 0
fi

if [ -z "$EVENT" ] || [ -z "$SESSION_ID" ]; then
  exit 0
fi

# Sanitize session_id to prevent path traversal
SESSION_ID="$(printf '%s' "$SESSION_ID" | tr -cd 'a-zA-Z0-9_-')"
if [ -z "$SESSION_ID" ]; then
  exit 0
fi

# Timestamp (second-precision; macOS date lacks %3N)
TS="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
DATE_PREFIX="$(date -u '+%Y-%m-%d')"

# Log file for this session
LOG_FILE="$LOG_DIR/${DATE_PREFIX}_${SESSION_ID}.jsonl"

# Helper: truncate a string and report original size
# Usage: truncate_field "$value" → sets TRUNC_VAL, TRUNC_SIZE, TRUNC_FLAG
truncate_field() {
  local val="$1"
  TRUNC_SIZE="${#val}"
  if [ "$TRUNC_SIZE" -gt "$MAX_RESPONSE_LEN" ]; then
    TRUNC_VAL="${val:0:$MAX_RESPONSE_LEN}"
    TRUNC_FLAG=true
  else
    TRUNC_VAL="$val"
    TRUNC_FLAG=false
  fi
}

case "$EVENT" in

  # ── SessionStart (sync — creates the log file) ─────────────────────
  SessionStart)
    MODEL="$(printf '%s' "$INPUT" | jq -r '.model // ""')"
    SOURCE="$(printf '%s' "$INPUT" | jq -r '.source // ""')"
    TRANSCRIPT="$(printf '%s' "$INPUT" | jq -r '.transcript_path // ""')"

    jq -n -c \
      --arg event "$EVENT" \
      --arg ts "$TS" \
      --arg sid "$SESSION_ID" \
      --arg model "$MODEL" \
      --arg source "$SOURCE" \
      --arg transcript "$TRANSCRIPT" \
      '{event: $event, timestamp: $ts, session_id: $sid, model: $model, source: $source, transcript_path: $transcript}' \
      >> "$LOG_FILE"

    # Export log path for downstream hooks (via env file if available)
    if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
      echo "export ZAZA_SESSION_LOG=\"$LOG_FILE\"" >> "$CLAUDE_ENV_FILE"
    fi
    ;;

  # ── SessionEnd ──────────────────────────────────────────────────────
  SessionEnd)
    REASON="$(printf '%s' "$INPUT" | jq -r '.reason // ""')"

    jq -n -c \
      --arg event "$EVENT" \
      --arg ts "$TS" \
      --arg sid "$SESSION_ID" \
      --arg reason "$REASON" \
      '{event: $event, timestamp: $ts, session_id: $sid, reason: $reason}' \
      >> "$LOG_FILE"

    # Write summary to index.jsonl
    if [ -f "$LOG_FILE" ]; then
      TOOL_CALLS="$( (grep '"event":"PreToolUse"' "$LOG_FILE" 2>/dev/null || true) | wc -l | tr -d ' ')"
      ERRORS="$( (grep '"event":"PostToolUseFailure"' "$LOG_FILE" 2>/dev/null || true) | wc -l | tr -d ' ')"
      SUBAGENTS="$( (grep '"event":"SubagentStart"' "$LOG_FILE" 2>/dev/null || true) | wc -l | tr -d ' ')"
      START_TS="$(head -1 "$LOG_FILE" | jq -r '.timestamp // ""' 2>/dev/null || echo "")"

      jq -n -c \
        --arg sid "$SESSION_ID" \
        --arg start "$START_TS" \
        --arg end "$TS" \
        --argjson tool_calls "$TOOL_CALLS" \
        --argjson errors "$ERRORS" \
        --argjson subagents "$SUBAGENTS" \
        --arg log_file "$LOG_FILE" \
        '{session_id: $sid, start: $start, end: $end, tool_calls: $tool_calls, errors: $errors, subagents: $subagents, log_file: $log_file}' \
        >> "$INDEX_FILE"
    fi
    ;;

  # ── PreToolUse ──────────────────────────────────────────────────────
  PreToolUse)
    TOOL_NAME="$(printf '%s' "$INPUT" | jq -r '.tool_name // ""')"
    TOOL_USE_ID="$(printf '%s' "$INPUT" | jq -r '.tool_use_id // ""')"
    TOOL_INPUT="$(printf '%s' "$INPUT" | jq -c '.tool_input // {}')"

    jq -n -c \
      --arg event "$EVENT" \
      --arg ts "$TS" \
      --arg sid "$SESSION_ID" \
      --arg tool_name "$TOOL_NAME" \
      --arg tool_use_id "$TOOL_USE_ID" \
      --argjson tool_input "$TOOL_INPUT" \
      '{event: $event, timestamp: $ts, session_id: $sid, tool_name: $tool_name, tool_use_id: $tool_use_id, tool_input: $tool_input}' \
      >> "$LOG_FILE"
    ;;

  # ── PostToolUse ─────────────────────────────────────────────────────
  PostToolUse)
    TOOL_NAME="$(printf '%s' "$INPUT" | jq -r '.tool_name // ""')"
    TOOL_USE_ID="$(printf '%s' "$INPUT" | jq -r '.tool_use_id // ""')"
    TOOL_INPUT="$(printf '%s' "$INPUT" | jq -c '.tool_input // {}')"
    RAW_RESPONSE="$(printf '%s' "$INPUT" | jq -r '.tool_response // ""')"

    truncate_field "$RAW_RESPONSE"

    jq -n -c \
      --arg event "$EVENT" \
      --arg ts "$TS" \
      --arg sid "$SESSION_ID" \
      --arg tool_name "$TOOL_NAME" \
      --arg tool_use_id "$TOOL_USE_ID" \
      --argjson tool_input "$TOOL_INPUT" \
      --arg tool_response "$TRUNC_VAL" \
      --argjson response_size "$TRUNC_SIZE" \
      --argjson truncated "$TRUNC_FLAG" \
      '{event: $event, timestamp: $ts, session_id: $sid, tool_name: $tool_name, tool_use_id: $tool_use_id, tool_input: $tool_input, tool_response: $tool_response, response_size: $response_size, truncated: $truncated}' \
      >> "$LOG_FILE"
    ;;

  # ── PostToolUseFailure ──────────────────────────────────────────────
  PostToolUseFailure)
    TOOL_NAME="$(printf '%s' "$INPUT" | jq -r '.tool_name // ""')"
    TOOL_USE_ID="$(printf '%s' "$INPUT" | jq -r '.tool_use_id // ""')"
    TOOL_INPUT="$(printf '%s' "$INPUT" | jq -c '.tool_input // {}')"
    ERROR="$(printf '%s' "$INPUT" | jq -r '.error // ""')"
    IS_INTERRUPT="$(printf '%s' "$INPUT" | jq -r '.is_interrupt // false')"

    jq -n -c \
      --arg event "$EVENT" \
      --arg ts "$TS" \
      --arg sid "$SESSION_ID" \
      --arg tool_name "$TOOL_NAME" \
      --arg tool_use_id "$TOOL_USE_ID" \
      --argjson tool_input "$TOOL_INPUT" \
      --arg error "$ERROR" \
      --argjson is_interrupt "$IS_INTERRUPT" \
      '{event: $event, timestamp: $ts, session_id: $sid, tool_name: $tool_name, tool_use_id: $tool_use_id, tool_input: $tool_input, error: $error, is_interrupt: $is_interrupt}' \
      >> "$LOG_FILE"
    ;;

  # ── SubagentStart ───────────────────────────────────────────────────
  SubagentStart)
    AGENT_ID="$(printf '%s' "$INPUT" | jq -r '.agent_id // ""')"
    AGENT_TYPE="$(printf '%s' "$INPUT" | jq -r '.agent_type // ""')"

    jq -n -c \
      --arg event "$EVENT" \
      --arg ts "$TS" \
      --arg sid "$SESSION_ID" \
      --arg agent_id "$AGENT_ID" \
      --arg agent_type "$AGENT_TYPE" \
      '{event: $event, timestamp: $ts, session_id: $sid, agent_id: $agent_id, agent_type: $agent_type}' \
      >> "$LOG_FILE"
    ;;

  # ── SubagentStop ────────────────────────────────────────────────────
  SubagentStop)
    AGENT_ID="$(printf '%s' "$INPUT" | jq -r '.agent_id // ""')"
    AGENT_TYPE="$(printf '%s' "$INPUT" | jq -r '.agent_type // ""')"
    TRANSCRIPT_PATH="$(printf '%s' "$INPUT" | jq -r '.agent_transcript_path // ""')"
    RAW_MSG="$(printf '%s' "$INPUT" | jq -r '.last_assistant_message // ""')"

    truncate_field "$RAW_MSG"

    jq -n -c \
      --arg event "$EVENT" \
      --arg ts "$TS" \
      --arg sid "$SESSION_ID" \
      --arg agent_id "$AGENT_ID" \
      --arg agent_type "$AGENT_TYPE" \
      --arg transcript "$TRANSCRIPT_PATH" \
      --arg preview "$TRUNC_VAL" \
      --argjson message_size "$TRUNC_SIZE" \
      --argjson truncated "$TRUNC_FLAG" \
      '{event: $event, timestamp: $ts, session_id: $sid, agent_id: $agent_id, agent_type: $agent_type, agent_transcript_path: $transcript, last_message_preview: $preview, message_size: $message_size, truncated: $truncated}' \
      >> "$LOG_FILE"
    ;;

  *)
    # Unknown event — ignore silently
    ;;
esac

exit 0
