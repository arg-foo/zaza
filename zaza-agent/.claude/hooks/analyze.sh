#!/bin/bash
# analyze.sh — Query accumulated session logs from trace.sh
# Usage: analyze.sh <command> [options]
# Logs at: ~/.zaza/logs/sessions/*.jsonl

set -euo pipefail

LOG_DIR="$HOME/.zaza/logs/sessions"
INDEX_FILE="$HOME/.zaza/logs/index.jsonl"

usage() {
  cat <<'USAGE'
Usage: analyze.sh <command> [options]

Commands:
  summary                Total sessions, tool calls, errors, error rate, sub-agents
  tools [--top N]        Tool call frequency + error frequency (default top 20)
  slow [--threshold N]   Tool calls exceeding N seconds (default 5)
  errors [--recent N]    Recent tool failures with error messages (default 20)
  subagents              Sub-agent launches and completions by type
  tickers [--top N]      Most queried tickers (default 20)
  session <id>           Full timeline for a specific session
  session-list [--last N] Recent sessions with tool/error counts (default 10)
USAGE
  exit 1
}

# Ensure log directory exists
if [ ! -d "$LOG_DIR" ]; then
  echo "No log directory found at $LOG_DIR"
  exit 1
fi

# Check if any logs exist
shopt -s nullglob
LOG_FILES=("$LOG_DIR"/*.jsonl)
shopt -u nullglob

if [ ${#LOG_FILES[@]} -eq 0 ]; then
  echo "No session logs found in $LOG_DIR"
  exit 0
fi

CMD="${1:-}"
shift 2>/dev/null || true

case "$CMD" in

  # ── summary ─────────────────────────────────────────────────────────
  summary)
    SESSIONS="$(grep -l 'SessionStart' "${LOG_FILES[@]}" 2>/dev/null | wc -l | tr -d ' ' || echo 0)"
    TOOL_CALLS="$( (grep '"event":"PreToolUse"' "${LOG_FILES[@]}" 2>/dev/null || true) | wc -l | tr -d ' ')"
    ERRORS="$( (grep '"event":"PostToolUseFailure"' "${LOG_FILES[@]}" 2>/dev/null || true) | wc -l | tr -d ' ')"
    SUBAGENTS="$( (grep '"event":"SubagentStart"' "${LOG_FILES[@]}" 2>/dev/null || true) | wc -l | tr -d ' ')"

    if [ "$TOOL_CALLS" -gt 0 ]; then
      ERROR_RATE="$(awk "BEGIN {printf \"%.1f\", ($ERRORS/$TOOL_CALLS)*100}")"
    else
      ERROR_RATE="0.0"
    fi

    echo "=== Zaza Trace Summary ==="
    echo "Sessions:    $SESSIONS"
    echo "Tool calls:  $TOOL_CALLS"
    echo "Errors:      $ERRORS ($ERROR_RATE%)"
    echo "Sub-agents:  $SUBAGENTS"
    echo "Log files:   ${#LOG_FILES[@]}"
    ;;

  # ── tools ───────────────────────────────────────────────────────────
  tools)
    TOP="${2:-20}"
    [ "${1:-}" = "--top" ] && TOP="${2:-20}"

    echo "=== Tool Call Frequency (top $TOP) ==="
    cat "${LOG_FILES[@]}" \
      | jq -r 'select(.event == "PreToolUse") | .tool_name' 2>/dev/null \
      | sort | uniq -c | sort -rn | head -n "$TOP" \
      | awk '{printf "  %-40s %s\n", $2, $1}'

    echo ""
    echo "=== Tool Error Frequency ==="
    cat "${LOG_FILES[@]}" \
      | jq -r 'select(.event == "PostToolUseFailure") | .tool_name' 2>/dev/null \
      | sort | uniq -c | sort -rn | head -n "$TOP" \
      | awk '{printf "  %-40s %s\n", $2, $1}'
    ;;

  # ── slow ────────────────────────────────────────────────────────────
  slow)
    THRESHOLD="${2:-5}"
    [ "${1:-}" = "--threshold" ] && THRESHOLD="${2:-5}"

    echo "=== Slow Tool Calls (> ${THRESHOLD}s) ==="
    # Match PreToolUse and PostToolUse by tool_use_id, compute duration
    # Validate timestamps match ISO 8601 before using in date command
    TS_REGEX='^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$'
    for f in "${LOG_FILES[@]}"; do
      jq -r 'select(.event == "PreToolUse" or .event == "PostToolUse") | [.event, .tool_use_id, .tool_name, .timestamp] | @tsv' "$f" 2>/dev/null
    done | while IFS=$'\t' read -r evt tid tname tstamp; do
      if [ "$evt" = "PreToolUse" ]; then
        # Store in temp files keyed by tool_use_id (safe for concurrent reads)
        printf '%s\t%s\t%s\n' "$tname" "$tstamp" "$tid" >> "/tmp/zaza_slow_pre_$$"
      elif [ "$evt" = "PostToolUse" ]; then
        printf '%s\n' "$tstamp" >> "/tmp/zaza_slow_post_${tid}_$$"
      fi
    done

    # Process pairs
    if [ -f "/tmp/zaza_slow_pre_$$" ]; then
      while IFS=$'\t' read -r tname start_ts tid; do
        POST_FILE="/tmp/zaza_slow_post_${tid}_$$"
        if [ -f "$POST_FILE" ]; then
          end_ts="$(head -1 "$POST_FILE")"
          # Validate timestamps
          if [[ "$start_ts" =~ $TS_REGEX ]] && [[ "$end_ts" =~ $TS_REGEX ]]; then
            t1="$(date -jf '%Y-%m-%dT%H:%M:%SZ' "$start_ts" '+%s' 2>/dev/null || echo '')"
            t2="$(date -jf '%Y-%m-%dT%H:%M:%SZ' "$end_ts" '+%s' 2>/dev/null || echo '')"
            if [ -n "$t1" ] && [ -n "$t2" ]; then
              dur=$((t2 - t1))
              if [ "$dur" -ge "$THRESHOLD" ]; then
                printf "  %-40s %ds  (%s)\n" "$tname" "$dur" "$start_ts"
              fi
            fi
          fi
        fi
      done < "/tmp/zaza_slow_pre_$$"
    fi

    # Cleanup temp files
    rm -f /tmp/zaza_slow_pre_$$ /tmp/zaza_slow_post_*_$$ 2>/dev/null || true
    ;;

  # ── errors ──────────────────────────────────────────────────────────
  errors)
    RECENT="${2:-20}"
    [ "${1:-}" = "--recent" ] && RECENT="${2:-20}"

    echo "=== Recent Tool Errors (last $RECENT) ==="
    cat "${LOG_FILES[@]}" \
      | jq -r 'select(.event == "PostToolUseFailure") | "\(.timestamp)  \(.tool_name)\n    Error: \(.error | tostring[:80])\n"' 2>/dev/null \
      | tail -n "$((RECENT * 3))"
    ;;

  # ── subagents ───────────────────────────────────────────────────────
  subagents)
    echo "=== Sub-agent Launches by Type ==="
    cat "${LOG_FILES[@]}" \
      | jq -r 'select(.event == "SubagentStart") | .agent_type' 2>/dev/null \
      | sort | uniq -c | sort -rn \
      | awk '{printf "  %-25s %s launches\n", $2, $1}'

    echo ""
    echo "=== Sub-agent Completions by Type ==="
    cat "${LOG_FILES[@]}" \
      | jq -r 'select(.event == "SubagentStop") | .agent_type' 2>/dev/null \
      | sort | uniq -c | sort -rn \
      | awk '{printf "  %-25s %s completions\n", $2, $1}'
    ;;

  # ── tickers ─────────────────────────────────────────────────────────
  tickers)
    TOP="${2:-20}"
    [ "${1:-}" = "--top" ] && TOP="${2:-20}"

    echo "=== Most Queried Tickers (top $TOP) ==="
    cat "${LOG_FILES[@]}" \
      | jq -r 'select(.event == "PreToolUse") | .tool_input | (.ticker // .symbol // .tickers // .symbols // empty)' 2>/dev/null \
      | tr ',' '\n' | tr -d '[] "' | (grep -v '^$' || true) \
      | tr '[:lower:]' '[:upper:]' \
      | sort | uniq -c | sort -rn | head -n "$TOP" \
      | awk '{printf "  %-10s %s calls\n", $2, $1}'
    ;;

  # ── session ─────────────────────────────────────────────────────────
  session)
    SID="${1:-}"
    if [ -z "$SID" ]; then
      echo "Usage: analyze.sh session <session_id>"
      exit 1
    fi

    # Sanitize session ID for safe grep usage
    SID="$(printf '%s' "$SID" | tr -cd 'a-zA-Z0-9_-')"

    # Find log file containing this session
    MATCH="$(grep -l "\"session_id\":\"$SID\"" "${LOG_FILES[@]}" 2>/dev/null | head -1 || echo '')"
    if [ -z "$MATCH" ]; then
      echo "Session $SID not found"
      exit 1
    fi

    echo "=== Session Timeline: $SID ==="
    echo "Log file: $MATCH"
    echo ""
    jq -r '
      if .event == "SessionStart" then
        "\(.timestamp) ▶ SESSION START (model: \(.model), source: \(.source))"
      elif .event == "SessionEnd" then
        "\(.timestamp) ◼ SESSION END (reason: \(.reason))"
      elif .event == "PreToolUse" then
        "\(.timestamp) → \(.tool_name) [id: \(.tool_use_id)]"
      elif .event == "PostToolUse" then
        "\(.timestamp) ← \(.tool_name) (\(.response_size) bytes\(if .truncated then ", truncated" else "" end))"
      elif .event == "PostToolUseFailure" then
        "\(.timestamp) ✗ \(.tool_name) ERROR: \(.error | tostring[:80])"
      elif .event == "SubagentStart" then
        "\(.timestamp) ⇨ SUBAGENT \(.agent_type) started [id: \(.agent_id)]"
      elif .event == "SubagentStop" then
        "\(.timestamp) ⇦ SUBAGENT \(.agent_type) stopped [id: \(.agent_id)]"
      else
        "\(.timestamp) ? \(.event)"
      end
    ' "$MATCH"
    ;;

  # ── session-list ────────────────────────────────────────────────────
  session-list)
    LAST="${2:-10}"
    [ "${1:-}" = "--last" ] && LAST="${2:-10}"

    echo "=== Recent Sessions (last $LAST) ==="
    if [ -f "$INDEX_FILE" ]; then
      tail -n "$LAST" "$INDEX_FILE" \
        | jq -r '"  \(.start)  tools:\(.tool_calls) errors:\(.errors) subagents:\(.subagents)  \(.session_id[:12])..."'
    else
      # Fallback: derive from log files (sorted by modification time)
      COUNT=0
      while IFS= read -r f && [ "$COUNT" -lt "$LAST" ]; do
        FNAME="$(basename "$f")"
        TOOLS="$( (grep '"event":"PreToolUse"' "$f" 2>/dev/null || true) | wc -l | tr -d ' ')"
        ERRS="$( (grep '"event":"PostToolUseFailure"' "$f" 2>/dev/null || true) | wc -l | tr -d ' ')"
        echo "  $FNAME  tools:$TOOLS errors:$ERRS"
        COUNT=$((COUNT + 1))
      done < <(ls -t "${LOG_FILES[@]}" 2>/dev/null)
    fi
    ;;

  *)
    usage
    ;;
esac

exit 0
