# TASK-035: Sub-Agent Prompt Templates — Research & Prediction Workflows

## Task ID
TASK-035

## Status
PENDING

## Title
Create Sub-Agent Prompt Templates for Research & Prediction Workflows

## Description
Create detailed, production-ready prompt templates for the 5 research and prediction-focused sub-agents: **Filings, Discovery, Browser, Prediction, and Backtesting**. These sub-agents handle the most context-intensive workflows in the system. The Prediction sub-agent is the most complex, pulling from nearly every tool category and applying a signal weighting hierarchy.

These templates are embedded in CLAUDE.md's `<delegation>` section.

## Acceptance Criteria

### Functional Requirements

#### Filings Sub-Agent Template
- [ ] Two-step workflow: get_filings (discover accession numbers) → get_filing_items (fetch section text)
- [ ] NEVER guess accession numbers — always discover first
- [ ] Synthesis instructions: summarize key findings with specific quotes from filing text
- [ ] Output format: structured summary with section references
- [ ] Handles large filing sections (10-K Item 1A can be 15-20k tokens) — sub-agent reads and synthesizes, only returns key findings
- [ ] Supports multiple filing types: 10-K, 10-Q, 8-K

#### Discovery Sub-Agent Template
- [ ] Workflow: get_screening_strategies or screen_stocks → for top 3-5 results: get_buy_sell_levels, get_price_snapshot, get_support_resistance, get_momentum_indicators, get_volume_analysis
- [ ] Cross-validates PKScreener levels with TA-derived support/resistance
- [ ] Output format: ranked table with entry, stop-loss, target, pattern, signal strength
- [ ] Includes TA disclaimer
- [ ] Handles variable result counts (0 results, 1-2, 3-5, 5+)

#### Browser Sub-Agent Template
- [ ] Workflow: browser_navigate → browser_snapshot → browser_act → browser_snapshot → browser_read → browser_close
- [ ] Always closes browser when done (resource cleanup)
- [ ] Synthesis instructions: extract relevant content, return structured data
- [ ] Includes guidance on when to use browser vs. WebFetch (browser only for JS-rendered/interactive)
- [ ] Error handling: if page fails to load, return error gracefully

#### Prediction Sub-Agent Template (MOST COMPLEX)
- [ ] Complete workflow across 6 tool categories:
  1. Current state: get_price_snapshot, get_prices
  2. Quantitative: get_price_forecast, get_volatility_forecast, get_monte_carlo_simulation, get_return_distribution, get_mean_reversion, get_regime_detection
  3. Options: get_implied_volatility, get_options_flow, get_gamma_exposure
  4. Technical: get_moving_averages, get_momentum_indicators, get_support_resistance
  5. Sentiment: get_news_sentiment, get_fear_greed_index
  6. Macro: get_treasury_yields, get_market_indices, get_intermarket_correlations
  7. Catalysts: get_analyst_estimates, get_earnings_calendar
- [ ] Signal weighting hierarchy: (1) Quant models → (2) Options positioning → (3) Technical levels → (4) Macro regime → (5) Sentiment → (6) Analyst consensus
- [ ] Output format: probability-weighted price range with confidence intervals, key levels, risks, catalysts
- [ ] Logs prediction to filesystem (see TASK-036)
- [ ] Includes prediction disclaimer
- [ ] ALWAYS delegated — never run inline

#### Backtesting Sub-Agent Template
- [ ] Workflow: get_signal_backtest, get_strategy_simulation, get_risk_metrics, get_prediction_score
- [ ] Output format: results table with win rate, P&L, Sharpe, max drawdown, vs. buy-and-hold
- [ ] Includes statistical significance notes and sample size
- [ ] Includes backtesting disclaimer (past performance ≠ future results, no slippage/costs)
- [ ] Warns about overfitting risk when sample size is small

### Non-Functional Requirements
- [ ] All templates follow the `<prompt-pattern>` from TASK-033
- [ ] Prediction template produces output under 1.5k tokens (saves ~18.5k vs inline)
- [ ] Filings template produces output under 1k tokens (saves ~14k vs inline)
- [ ] Other templates produce output under 800 tokens
- [ ] Tool names match MCP registration exactly

## Dependencies
- TASK-033: Sub-Agent Delegation Framework (prompt pattern must exist)
- TASK-014: Financial Tools — SEC Filings
- TASK-015: Technical Analysis Tools
- TASK-016: Options & Derivatives Tools
- TASK-017: Sentiment Analysis Tools
- TASK-018: Macro & Cross-Asset Tools
- TASK-019: Quantitative Model Tools
- TASK-022: Backtesting & Validation Tools
- TASK-023: PKScreener Docker & Screener Tools
- TASK-024: Browser Automation Tools

## Technical Notes

### Prediction Sub-Agent Signal Weighting
The architecture specifies a priority-weighted synthesis:
1. **Quantitative models** (statistical backbone) — ARIMA/Prophet point forecast + Monte Carlo probability distribution
2. **Options positioning** (market's own forecast) — implied vol regime, GEX levels, unusual flow direction
3. **Technical levels** (price structure) — S/R, moving averages, momentum divergence
4. **Macro regime** (environment context) — risk-on/off, yield curve, correlation shifts
5. **Sentiment** (contrarian/confirmation) — agree with technicals = confirmation, disagree = caution
6. **Analyst consensus** (anchoring reference) — mean target as sanity check, not primary signal

### Filings Context Challenge
Filing sections are the largest individual tool results in the system. A single 10-K Item 1A (Risk Factors) can be 15-20k tokens. The Filings sub-agent reads the full text in its isolated context, synthesizes key findings, and returns only ~1k tokens to the main context. This is where sub-agents provide the most value.

### Implementation Hints
1. Prediction template should instruct the sub-agent to call tool categories in parallel where possible (e.g., quant + options + TA can run simultaneously)
2. Filings template must emphasize: ALWAYS call get_filings first, NEVER fabricate accession numbers
3. Browser template must always include browser_close as final step
4. Discovery template should adapt analysis depth to result count (fewer results = deeper analysis per stock)

## Estimated Complexity
**Medium** (4-6 hours)

## References
- ZAZA_ARCHITECTURE.md Section 6.2 (Sub-Agent Catalog — Filings, Discovery, Browser, Prediction, Backtesting)
- ZAZA_ARCHITECTURE.md Section 11 (CLAUDE.md workflow instructions)
- ZAZA_ARCHITECTURE.md Section 12 (Execution flow examples — especially Prediction walkthrough)
