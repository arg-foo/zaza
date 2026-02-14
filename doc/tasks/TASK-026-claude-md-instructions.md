# TASK-026: CLAUDE.md Behavioral Instructions

## Task ID
TASK-026

## Status
COMPLETED

## Title
Write Complete CLAUDE.md Behavioral Instructions

## Description
Write the complete `CLAUDE.md` file that turns Claude Code into a financial research agent. This is the single configuration file that controls tool usage policy, sub-agent delegation rules, response formatting, TA/prediction disclaimers, and all behavioral instructions.

CLAUDE.md replaces the entire prompt infrastructure from the original proposal — there are no system prompts, router prompts, or tool descriptions outside of this file and the MCP tool schemas.

## Acceptance Criteria

### Functional Requirements
- [ ] `CLAUDE.md` contains all sections specified in the architecture:
  - Project description (What is Zaza)
  - Build & Development Commands
  - Architecture overview
  - Tool Usage Policy with tool selection guide for all 11 domains
  - Sub-Agent Delegation rules (when to delegate vs handle inline)
  - Sub-Agent Task Prompt templates for all 10 sub-agents
  - Ticker Resolution rules
  - Date Inference rules
  - Period Selection defaults
  - Behavior guidelines
  - Response Format instructions (tables, compact format)
  - TA & Prediction Disclaimers
- [ ] Tool selection guide covers all 66 tools organized by query type
- [ ] Sub-agent delegation matrix clearly distinguishes inline (1-2 tools) from delegated (3+ tools) workflows
- [ ] 10 sub-agent workflow templates with step-by-step instructions
- [ ] Filings workflow explicitly documents the two-step pattern
- [ ] PKScreener workflow documents the screen → analyze → synthesize pattern
- [ ] Price Prediction workflow documents the signal weighting hierarchy

### Non-Functional Requirements
- [ ] **Documentation**: CLAUDE.md is self-contained — Claude Code should be able to use all tools correctly with only this file
- [ ] **Maintainability**: Organized with clear headings and consistent formatting
- [ ] **Correctness**: All tool names match actual MCP tool names exactly

## Dependencies
- TASK-012 through TASK-024: All tool implementations (to verify exact tool names and parameters)

## Technical Notes

### Key Sections from Architecture

The CLAUDE.md content is fully specified in ZAZA_ARCHITECTURE.md Section 11. Key elements:

**Tool Usage Policy:**
- ALWAYS prefer financial tools over WebSearch for financial data
- Don't break queries into multiple calls when one tool handles it
- Tool selection guide maps query types → specific tool names

**Sub-Agent Delegation Decision Matrix:**
| Query Type | Tool Calls | Approach |
|-----------|:----------:|----------|
| Single data point | 1 | Inline |
| Single indicator | 1 | Inline |
| Comprehensive TA | 10+ | Sub-agent: TA |
| Multi-company comparison | 2×N | Sub-agent: Comparative |
| Filing content | 2-3 | Sub-agent: Filings |
| Stock screening + analysis | 5-20 | Sub-agent: Discovery |
| Options positioning | 7-8 | Sub-agent: Options |
| Multi-source sentiment | 4+ | Sub-agent: Sentiment |
| Macro regime | 5+ | Sub-agent: Macro |
| Price prediction | 15-20+ | Sub-agent: Prediction |
| Signal backtest | 3-5 | Sub-agent: Backtesting |

**Signal Weighting Hierarchy (Prediction):**
1. Quantitative models (statistical backbone)
2. Options positioning (market's own forecast)
3. Technical levels (price structure)
4. Macro regime (environment context)
5. Sentiment (contrarian/confirmation)
6. Analyst consensus (anchoring reference)

### Implementation Hints
1. Keep the existing CLAUDE.md structure but expand all sections with full content
2. Use markdown headers for clear navigation
3. Tool names must match MCP registration exactly (e.g., `get_price_snapshot`, not `price_snapshot`)
4. Sub-agent prompts should be copy-pasteable templates that the main agent fills in
5. Include both "when to use" and "when NOT to use" for each sub-agent
6. The file will be large (~500-800 lines) — that's expected for this project

## Estimated Complexity
**Medium** (4-6 hours)

## References
- ZAZA_ARCHITECTURE.md Section 11 (CLAUDE.md — Behavioral Instructions)
- ZAZA_ARCHITECTURE.md Section 6 (Sub-Agent Architecture)
