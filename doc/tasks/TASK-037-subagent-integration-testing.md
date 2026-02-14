# TASK-037: Sub-Agent Integration Testing & Validation

## Task ID
TASK-037

## Status
PENDING

## Title
Sub-Agent Integration Testing & End-to-End Validation

## Description
Validate that all 10 sub-agent workflows function correctly end-to-end. This includes testing delegation trigger accuracy, tool call sequencing, output format compliance, context savings verification, error handling, and prediction logging integration.

Since sub-agents are behavioral (CLAUDE.md-driven, not code), this task combines automated tests (for prediction logging, output format parsing) with structured manual validation checklists for each sub-agent workflow.

## Acceptance Criteria

### Functional Requirements

#### Automated Tests
- [ ] Prediction logging tests:
  - log_prediction() creates valid JSON files
  - score_predictions() correctly computes directional accuracy, MAE, bias
  - Handles missing/corrupt files gracefully
  - Log rotation works correctly
- [ ] Output format validation tests:
  - Parse expected output formats from each sub-agent template
  - Verify synthesized outputs match format spec (tables have correct columns, summaries have required sections)
- [ ] Tool dependency tests:
  - Each sub-agent's tool list matches the tools registered in the MCP server
  - All tool names in CLAUDE.md templates match actual MCP tool registrations

#### Manual Validation Checklists
- [ ] **TA Sub-Agent**: Ask "Technical outlook for AAPL" → verify 10 tools called, directional bias returned, disclaimer present
- [ ] **Comparative Sub-Agent**: Ask "Compare AAPL MSFT GOOGL" → verify comparison table, all metrics present
- [ ] **Filings Sub-Agent**: Ask "TSLA risk factors from latest 10-K" → verify get_filings called first, accession number not guessed, key findings summarized
- [ ] **Discovery Sub-Agent**: Ask "Find breakout stocks on NASDAQ" → verify screen_stocks called, top results analyzed with buy/sell levels
- [ ] **Browser Sub-Agent**: Ask to navigate to a JS-rendered page → verify browser opened, content extracted, browser closed
- [ ] **Options Sub-Agent**: Ask "Options positioning on NVDA" → verify all options tools called, GEX/max pain/IV reported
- [ ] **Sentiment Sub-Agent**: Ask "What's the sentiment on TSLA?" → verify all 4 sentiment tools called, aggregate score returned
- [ ] **Macro Sub-Agent**: Ask "What's the macro environment?" → verify yields, indices, commodities, calendar, correlations
- [ ] **Prediction Sub-Agent**: Ask "Where will NVDA be in 30 days?" → verify all tool categories called, prediction logged, weighted synthesis returned
- [ ] **Backtesting Sub-Agent**: Ask "Backtest RSI oversold on AAPL" → verify signal_backtest + strategy_simulation + risk_metrics called

#### Context Savings Verification
- [ ] For each sub-agent, estimate actual token count of synthesized output
- [ ] Compare against inline execution (all raw tool results in main context)
- [ ] Verify savings are within expected ranges (from TASK-033 estimates)

#### Error Handling Tests
- [ ] Sub-agent with one failing tool still produces partial results
- [ ] Sub-agent with all tools failing returns graceful error message
- [ ] Main agent handles sub-agent timeout gracefully

### Non-Functional Requirements
- [ ] Automated tests pass with `uv run pytest tests/`
- [ ] Manual validation checklist documented as a markdown file in `doc/`
- [ ] All tests mock external APIs (no live calls)
- [ ] Test coverage for prediction logging module ≥ 90%

## Dependencies
- TASK-033: Sub-Agent Delegation Framework
- TASK-034: Sub-Agent Prompt Templates — Analysis Workflows
- TASK-035: Sub-Agent Prompt Templates — Research & Prediction Workflows
- TASK-036: Prediction Logging Infrastructure
- TASK-025: MCP Server Tool Registration & Wiring
- TASK-028: Comprehensive Test Suite (test infrastructure)

## Technical Notes

### Testing Strategy
Sub-agent behavior is driven by CLAUDE.md, not code. This means:
1. **Prediction logging** (TASK-036) can be fully unit-tested — it's Python code
2. **Tool name consistency** can be automated — cross-reference CLAUDE.md tool names with MCP server tool registry
3. **Output format compliance** can be partially automated — parse expected formats from templates
4. **Delegation routing** is behavioral — requires manual testing with real Claude Code sessions
5. **Context savings** can be estimated — count tokens in tool results vs. synthesized outputs

### Test File Structure
```
tests/
├── subagents/
│   ├── test_prediction_logging.py
│   ├── test_tool_name_consistency.py
│   └── test_output_formats.py
doc/
├── subagent-validation-checklist.md
```

### Implementation Hints
1. For tool name consistency: parse CLAUDE.md for tool names, compare against `server.py` tool registry
2. For prediction logging: use `tmp_path` fixture for filesystem tests
3. For output format: define expected schemas and validate against them
4. Manual checklist should include expected behavior AND actual observed behavior columns

## Estimated Complexity
**Medium** (6-8 hours)

## References
- ZAZA_ARCHITECTURE.md Section 6 (Sub-Agent Architecture)
- ZAZA_ARCHITECTURE.md Section 12 (Execution Flow examples)
- ZAZA_ARCHITECTURE.md Section 14 (Testing Strategy)
