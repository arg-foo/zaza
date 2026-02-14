# TASK-034: Sub-Agent Prompt Templates — Analysis Workflows

## Task ID
TASK-034

## Status
PENDING

## Title
Create Sub-Agent Prompt Templates for Analysis Workflows

## Description
Create detailed, production-ready prompt templates for the 5 analysis-focused sub-agents: **TA, Comparative, Options, Sentiment, and Macro**. Each template is a structured Task tool prompt that the main Claude Code agent fills in when delegating a workflow. Templates include the research question, tool call sequence, synthesis instructions, output format, and required disclaimers.

These templates are embedded in CLAUDE.md's `<delegation>` section and are the primary mechanism that ensures sub-agents produce consistent, high-quality, concise outputs.

## Acceptance Criteria

### Functional Requirements

#### TA Sub-Agent Template
- [ ] Prompt includes all 10 tool calls in correct order: get_price_snapshot, get_moving_averages, get_trend_strength, get_momentum_indicators, get_money_flow, get_volatility_indicators, get_support_resistance, get_price_patterns, get_volume_analysis, get_relative_performance
- [ ] Synthesis instructions: directional bias, key levels, confluence signals, risk assessment
- [ ] Output format: structured summary with signal strength ratings
- [ ] Includes TA disclaimer
- [ ] Handles partial data (some tools fail gracefully)

#### Comparative Sub-Agent Template
- [ ] Prompt iterates over N tickers with: get_income_statements, get_balance_sheets, get_cash_flow_statements, get_key_ratios_snapshot, get_key_ratios, get_analyst_estimates, get_company_facts
- [ ] Synthesis instructions: build comparison table, identify relative strengths/weaknesses, trend analysis
- [ ] Output format: compact markdown table with abbreviated headers (Rev, OM, NI, EPS, FCF, D/E, ROE, P/E)
- [ ] Handles 2-5 tickers efficiently

#### Options Sub-Agent Template
- [ ] Prompt includes all 7-8 tool calls: get_options_expirations, get_options_chain, get_implied_volatility, get_put_call_ratio, get_options_flow, get_max_pain, get_gamma_exposure, get_price_snapshot
- [ ] Synthesis instructions: directional bias from positioning, GEX levels, IV regime classification, unusual activity highlights
- [ ] Output format: positioning summary with key strike levels
- [ ] Includes options/TA disclaimer

#### Sentiment Sub-Agent Template
- [ ] Prompt includes all 4 tools: get_news_sentiment, get_social_sentiment, get_insider_sentiment, get_fear_greed_index
- [ ] Synthesis instructions: weight sources by reliability, identify agreement/divergence, flag contrarian signals
- [ ] Output format: aggregate sentiment score with source breakdown
- [ ] Source weighting: insider > news > social > fear/greed

#### Macro Sub-Agent Template
- [ ] Prompt includes all 5 tools: get_treasury_yields, get_market_indices, get_commodity_prices, get_economic_calendar, get_intermarket_correlations
- [ ] Synthesis instructions: classify regime (risk-on/off, tightening/easing), identify dominant driver, flag upcoming catalysts
- [ ] Output format: regime summary with key data points
- [ ] Handles ticker-specific correlation context

### Non-Functional Requirements
- [ ] All templates follow the `<prompt-pattern>` from TASK-033
- [ ] Templates are copy-paste ready — main agent only needs to fill in ticker(s) and specific question
- [ ] Each template produces output under 800 tokens (target for context savings)
- [ ] Tool names match MCP registration exactly (e.g., `get_price_snapshot`)

## Dependencies
- TASK-033: Sub-Agent Delegation Framework (prompt pattern must exist)
- TASK-012: Financial Tools — Prices & Company
- TASK-013: Financial Tools — Statements & Ratios
- TASK-015: Technical Analysis Tools
- TASK-016: Options & Derivatives Tools
- TASK-017: Sentiment Analysis Tools
- TASK-018: Macro & Cross-Asset Tools

## Technical Notes

### Template Structure (per sub-agent)
Each prompt template should include:
1. **Role**: "You are a financial research sub-agent with access to Zaza MCP tools."
2. **Task**: Specific research question with ticker(s)
3. **Workflow**: Numbered tool call sequence
4. **Synthesis**: What to extract and how to combine
5. **Format**: Exact output structure expected
6. **Constraints**: Token budget, disclaimers, what NOT to include (raw data dumps)

### Key Design Decisions
- Templates live in CLAUDE.md `<delegation>` section, one per sub-agent
- Use XML-like structure for machine-readability within markdown
- Include "when to use" trigger examples and "when NOT to use" counter-examples
- Synthesis instructions should emphasize "specific numbers, not vague statements"

## Estimated Complexity
**Medium** (4-6 hours)

## References
- ZAZA_ARCHITECTURE.md Section 6.2 (Sub-Agent Catalog — TA, Comparative, Options, Sentiment, Macro)
- ZAZA_ARCHITECTURE.md Section 11 (CLAUDE.md workflow instructions)
- ZAZA_ARCHITECTURE.md Section 12 (Execution flow examples)
