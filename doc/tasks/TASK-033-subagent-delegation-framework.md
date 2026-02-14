# TASK-033: Sub-Agent Delegation Framework & Decision Matrix

## Task ID
TASK-033

## Status
PENDING

## Title
Define Sub-Agent Delegation Framework & Decision Matrix

## Description
Define the complete sub-agent delegation framework in CLAUDE.md. This is the routing layer that tells the main Claude Code agent when to handle queries inline (1-2 tool calls) vs. spawn a sub-agent via the Task tool (3+ tool calls). This task establishes the decision matrix, trigger patterns, context budget estimates, error handling rules, and spawn configuration for all 10 sub-agents.

This task expands the existing `<delegation>` section in CLAUDE.md from a basic outline into a production-ready delegation framework, as specified in ZAZA_ARCHITECTURE.md Section 6.

## Acceptance Criteria

### Functional Requirements
- [ ] Complete inline vs. delegate decision matrix covering all query types
- [ ] Trigger patterns for each of the 10 sub-agents (TA, Comparative, Filings, Discovery, Browser, Options, Sentiment, Macro, Prediction, Backtesting)
- [ ] Context budget estimates per sub-agent (expected input tokens from raw tool results vs. synthesized output tokens)
- [ ] Error handling rules: what happens when a tool fails mid-workflow (graceful degradation, partial results)
- [ ] Concurrency guidance: when multiple sub-agents can run in parallel (e.g., Sentiment + Macro for a prediction)
- [ ] Fallback rules: when a sub-agent should fall back to inline execution (e.g., only 1 tool needed from the workflow)
- [ ] Clear documentation of the `<prompt-pattern>` that all sub-agent Task prompts must follow
- [ ] Explicit "NEVER delegate" list (single data lookups, simple calculations)

### Non-Functional Requirements
- [ ] Decision matrix is unambiguous — no query should match multiple sub-agents without clear priority
- [ ] Framework is consistent with ZAZA_ARCHITECTURE.md Section 6.3 (Delegation Decision Matrix)
- [ ] Integrates cleanly with existing CLAUDE.md `<delegation>` section structure

## Dependencies
- TASK-026: CLAUDE.md Behavioral Instructions (base CLAUDE.md must exist)
- TASK-006: MCP Server Entry Point (sub-agents need MCP tools available)

## Technical Notes

### Decision Matrix (from Architecture Section 6.3)
| Query Type | Tool Calls | Approach | Example |
|-----------|:----------:|----------|---------|
| Single data point | 1 | Inline | "AAPL price" |
| Single indicator | 1 | Inline | "AAPL RSI" |
| Comprehensive TA | 10+ | Sub-agent: TA | "Technical outlook for NVDA" |
| Multi-company comparison | 2×N | Sub-agent: Comparative | "Compare AAPL MSFT GOOGL" |
| Filing content | 2-3 | Sub-agent: Filings | "TSLA risk factors from 10-K" |
| Stock screening + analysis | 5-20 | Sub-agent: Discovery | "Find breakout stocks" |
| Interactive browser | 5-8 | Sub-agent: Browser | "Go to Apple IR page" |
| Options positioning | 7-8 | Sub-agent: Options | "Options positioning on NVDA" |
| Multi-source sentiment | 4+ | Sub-agent: Sentiment | "Sentiment on TSLA" |
| Macro regime | 5+ | Sub-agent: Macro | "Macro environment for tech" |
| Price prediction | 15-20+ | Sub-agent: Prediction | "Where will NVDA be in 30 days?" |
| Signal backtest | 3-5 | Sub-agent: Backtesting | "Backtest RSI oversold on AAPL" |

### Context Savings Estimates (from Architecture Section 12)
| Sub-Agent | Inline Tokens | Synthesized Tokens | Savings |
|-----------|:------------:|:------------------:|:-------:|
| TA | ~8k | ~500 | 94% |
| Comparative | ~6k | ~800 | 87% |
| Filings | ~15k | ~1k | 93% |
| Discovery | ~10k | ~800 | 92% |
| Browser | ~12k | ~500 | 96% |
| Options | ~5k | ~500 | 90% |
| Sentiment | ~4k | ~500 | 88% |
| Macro | ~4k | ~500 | 88% |
| Prediction | ~20k | ~1.5k | 93% |
| Backtesting | ~4k | ~500 | 88% |

### Implementation Hints
1. The framework lives in CLAUDE.md, not in Python code
2. Sub-agents are spawned via Claude Code's built-in Task tool — no custom orchestration code
3. The prompt-pattern template should be generic enough for all sub-agents but specific enough to ensure consistent output quality
4. Error handling is behavioral (CLAUDE.md instructions), not programmatic

## Estimated Complexity
**Small** (2-3 hours)

## References
- ZAZA_ARCHITECTURE.md Section 6 (Sub-Agent Architecture)
- ZAZA_ARCHITECTURE.md Section 6.3 (Delegation Decision Matrix)
- ZAZA_ARCHITECTURE.md Section 6.4 (Sub-Agent Prompt Pattern)
- ZAZA_ARCHITECTURE.md Section 12 (Execution Flow examples)
