# Sub-Agent Validation Checklist

Manual validation checklist for testing each sub-agent workflow end-to-end.
Use this after automated tests pass to verify real-world behavior.

## Instructions

For each sub-agent, run the test query in Claude Code with the Zaza MCP server active.
Verify the expected behavior occurs. Check the box when validated.

---

## Sub-Agent Functional Tests

| # | Sub-Agent | Test Query | Expected Behavior | Verified | Notes |
|---|-----------|-----------|-------------------|:--------:|-------|
| 1 | TA | "Technical outlook for AAPL" | 10 tools called in parallel, signal table returned, directional bias stated, key levels listed, disclaimer present | [ ] | |
| 2 | Comparative | "Compare AAPL vs MSFT vs GOOGL" | 7 tools called per ticker (21 total), comparison table with compact numbers, relative assessment at bottom | [ ] | |
| 3 | Filings | "TSLA risk factors from latest 10-K" | get_filings called FIRST, accession number extracted from result, get_filing_items called with correct accession number, key findings with quotes | [ ] | |
| 4 | Discovery | "Find breakout stocks on NASDAQ" | screen_stocks called first, top 3-5 results analyzed with get_buy_sell_levels + get_support_resistance + get_momentum_indicators + get_volume_analysis, ranked table with entry/stop/target | [ ] | |
| 5 | Browser | "Go to https://example.com and extract the heading" | browser_navigate called, browser_snapshot called, browser_read called, browser_close called at the end, content returned | [ ] | |
| 6 | Options | "Options positioning on NVDA" | All 7-8 options tools called (expirations, chain, IV, P/C ratio, flow, max pain, GEX), metrics table returned, positioning bias stated, disclaimer present | [ ] | |
| 7 | Sentiment | "What's the sentiment on TSLA?" | All 4 sentiment tools called (news, social, insider, fear/greed), source table with scores, weighted aggregate, contrarian flag if applicable | [ ] | |
| 8 | Macro | "What's the macro environment?" | All 5 macro tools called (yields, indices, commodities, calendar, correlations), factor table returned, regime classified, upcoming events listed | [ ] | |
| 9 | Prediction | "Where will NVDA be in 30 days?" | 15-21 tools called across all categories (quant, options, TA, sentiment, macro, catalysts), scenario table with percentiles, key levels, regime, risks, disclaimer, prediction logged to file | [ ] | |
| 10 | Backtesting | "Backtest RSI oversold on AAPL" | get_signal_backtest + get_strategy_simulation + get_risk_metrics called, metrics table with win rates, sample size note, statistical significance assessment, disclaimer | [ ] | |

---

## Inline vs. Delegate Decision Tests

Verify the decision matrix works correctly -- these should NOT spawn sub-agents.

| # | Test Query | Expected Behavior | Verified | Notes |
|---|-----------|-------------------|:--------:|-------|
| 1 | "AAPL price" | Single get_price_snapshot call, no sub-agent | [ ] | |
| 2 | "AAPL RSI" | Single get_momentum_indicators call, no sub-agent | [ ] | |
| 3 | "What does NVDA do?" | Single get_company_facts call, no sub-agent | [ ] | |
| 4 | "TSLA IV rank" | Single get_implied_volatility call, no sub-agent | [ ] | |
| 5 | "Current VIX" | Single get_market_indices call, no sub-agent | [ ] | |
| 6 | "AAPL Sharpe ratio" | Single get_risk_metrics call, no sub-agent | [ ] | |
| 7 | "Fear greed index" | Single get_fear_greed_index call, no sub-agent | [ ] | |
| 8 | "AAPL support levels" | Single get_support_resistance call, no sub-agent | [ ] | |
| 9 | "AAPL buy/sell levels" | Single get_buy_sell_levels call, no sub-agent | [ ] | |
| 10 | "When did AAPL file their 10-K?" | Single get_filings call, no sub-agent | [ ] | |

---

## Error Handling Tests

| # | Scenario | Test Setup | Expected Behavior | Verified | Notes |
|---|----------|-----------|-------------------|:--------:|-------|
| 1 | Partial tool failure in TA | Disconnect network mid-TA-analysis (or mock 1-2 tool failures) | Analysis proceeds with available data, missing tools noted explicitly | [ ] | |
| 2 | All tools fail | No network / all APIs down | Graceful error message returned, no raw tracebacks | [ ] | |
| 3 | PKScreener Docker unavailable | Stop pkscreener container, then "Find breakout stocks" | Falls back to manual screening or reports Docker unavailability | [ ] | |
| 4 | Missing Reddit credentials | Unset REDDIT_CLIENT_ID, then "Sentiment on TSLA" | Proceeds with news + insider + fear/greed (3 sources), weights adjusted | [ ] | |
| 5 | Missing FRED API key | Unset FRED_API_KEY, then "Macro environment" | Proceeds without economic calendar, notes the gap | [ ] | |
| 6 | Filings accession number not found | "Risk factors for a very new/small company" | get_filings returns empty list, user informed no filings available | [ ] | |
| 7 | Prediction tool category fails | Mock quant model failures during prediction | Remaining categories used, weights adjusted, gaps noted | [ ] | |

---

## Context Savings Verification

Verify sub-agents compress raw tool output into concise summaries.

| # | Sub-Agent | Expected Raw Output | Expected Synthesized Output | Savings Target | Verified | Notes |
|---|-----------|:------------------:|:--------------------------:|:-------------:|:--------:|-------|
| 1 | TA | ~8k tokens | ~500 tokens | 94% | [ ] | Check response is concise table + bias, not raw JSON |
| 2 | Comparative | ~6k tokens | ~800 tokens | 87% | [ ] | Check response is comparison table, not raw statements |
| 3 | Filings | ~15k tokens | ~1k tokens | 93% | [ ] | Check response has key findings with quotes, not full filing text |
| 4 | Discovery | ~10k tokens | ~800 tokens | 92% | [ ] | Check response is ranked table, not raw screening output |
| 5 | Browser | ~12k tokens | ~500 tokens | 96% | [ ] | Check response has extracted data, not full page text |
| 6 | Options | ~5k tokens | ~500 tokens | 90% | [ ] | Check response is metrics table + bias, not raw chains |
| 7 | Sentiment | ~4k tokens | ~500 tokens | 88% | [ ] | Check response is source table + aggregate, not raw articles |
| 8 | Macro | ~4k tokens | ~500 tokens | 88% | [ ] | Check response is factor table + regime, not raw data |
| 9 | Prediction | ~20k tokens | ~1.5k tokens | 93% | [ ] | Check response is scenario table + levels, not raw model output |
| 10 | Backtesting | ~4k tokens | ~500 tokens | 88% | [ ] | Check response is metrics table + assessment, not raw trades |

---

## Concurrency Verification

| # | Test | Expected Behavior | Verified | Notes |
|---|------|-------------------|:--------:|-------|
| 1 | TA sub-agent: all 10 tools | Tools called in parallel (visible in timing -- should take ~1-3s, not 10x sequential) | [ ] | |
| 2 | Prediction sub-agent: tool categories | Independent categories called in parallel | [ ] | |
| 3 | Filings sub-agent: sequential | get_filings completes before get_filing_items starts | [ ] | |
| 4 | Discovery sub-agent: sequential then parallel | screen_stocks completes first, then per-stock analysis in parallel | [ ] | |
| 5 | Browser sub-agent: sequential | navigate -> snapshot -> act -> read -> close in order | [ ] | |
| 6 | Multiple sub-agents in parallel | "Compare AAPL and MSFT with TA" spawns Comparative + TA simultaneously | [ ] | |

---

## Disclaimer Verification

| # | Sub-Agent | Disclaimer Required | Key Phrases to Check | Verified | Notes |
|---|-----------|:------------------:|---------------------|:--------:|-------|
| 1 | TA | Yes | "Not financial advice", "historical patterns" | [ ] | |
| 2 | Comparative | No | N/A | [ ] | |
| 3 | Filings | No | N/A | [ ] | |
| 4 | Discovery | Yes | "Not financial advice", "always verify" | [ ] | |
| 5 | Browser | No | N/A | [ ] | |
| 6 | Options | Yes | "Not financial advice", "not guaranteed outcomes" | [ ] | |
| 7 | Sentiment | No | N/A | [ ] | |
| 8 | Macro | No | N/A | [ ] | |
| 9 | Prediction | Yes | "probabilistic estimates", "NOT certainties", "cannot predict regime changes" | [ ] | |
| 10 | Backtesting | Yes | "do NOT equal future performance", "costs, slippage" | [ ] | |

---

## Output Format Verification

| # | Sub-Agent | Expected Format Element | Verified | Notes |
|---|-----------|------------------------|:--------:|-------|
| 1 | TA | Signal summary table with Signal/Value/Interpretation columns | [ ] | |
| 2 | Comparative | Comparison table with Metric column and ticker columns | [ ] | |
| 3 | Filings | Key Findings numbered list with quotes, Notable Risks bullets | [ ] | |
| 4 | Discovery | Ranked table with #/Ticker/Price/Pattern/Entry/Stop/Target columns | [ ] | |
| 5 | Browser | Source URL + structured extracted data | [ ] | |
| 6 | Options | Metrics table with Metric/Value/Signal columns, Unusual Flow section | [ ] | |
| 7 | Sentiment | Source table with Source/Score/Direction/Key Driver columns | [ ] | |
| 8 | Macro | Factor table with Factor/Current/Trend/Signal columns | [ ] | |
| 9 | Prediction | Scenario table with Scenario/Price/Probability/Key Driver columns | [ ] | |
| 10 | Backtesting | Metrics table with Metric/Value columns, Sample Size note | [ ] | |

---

## Prediction Logging Verification

| # | Test | Expected Behavior | Verified | Notes |
|---|------|-------------------|:--------:|-------|
| 1 | Run prediction query | JSON file created at ~/.zaza/predictions/{TICKER}_{date}_{horizon}d.json | [ ] | |
| 2 | Check prediction file schema | File contains: ticker, prediction_date, horizon_days, target_date, current_price, predicted_range, confidence_interval, model_weights, key_factors | [ ] | |
| 3 | Re-run prediction for same ticker/date | Existing file overwritten with updated prediction | [ ] | |
| 4 | Score past predictions | get_prediction_score returns directional_accuracy, MAE, MAPE, bias, range_accuracy | [ ] | |
| 5 | Log rotation | Predictions older than 1 year moved to archive/ subdirectory | [ ] | |

---

## Sign-off

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Reviewer | | | |
