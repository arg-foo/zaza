# CLAUDE.md

Zaza is a financial research MCP server (66 tools, 11 domains) that extends Claude Code with financial data, TA, options, sentiment, macro, quant models, institutional flow, earnings, backtesting, screening, and browser automation. Claude Code provides the agent loop, LLM, and UI. Zaza adds only MCP tools.

```xml
<commands>
  <install>uv sync</install>
  <run>uv run python -m zaza.server</run>
  <test>uv run pytest tests/</test>
  <test-file>uv run pytest tests/tools/test_prices.py</test-file>
  <test-pattern>uv run pytest tests/ -k "test_momentum"</test-pattern>
  <lint>uv run ruff check src/ tests/ &amp;&amp; uv run mypy src/</lint>
  <playwright>uv run playwright install chromium</playwright>
  <pkscreener>docker run -d --name pkscreener -e PKSCREENER_DOCKER=1 -v pkscreener-data:/PKScreener-main/actions_data pkjmesra/pkscreener:latest sleep infinity</pkscreener>
  <verify>uv run python -m zaza.server --check</verify>
</commands>

<!-- ================================================================ -->
<!-- TOOL SELECTION: Always prefer MCP tools over WebSearch for financial data -->
<!-- ================================================================ -->

<tools>

  <!-- Financial Data (15) -->
  <tool name="get_price_snapshot"        query="current price, change, volume, market cap" />
  <tool name="get_prices"               query="historical OHLCV" />
  <tool name="get_key_ratios_snapshot"   query="P/E, EV/EBITDA, ROE, margins, dividend yield" />
  <tool name="get_income_statements"     query="revenue, gross profit, operating income, net income, EPS" />
  <tool name="get_balance_sheets"        query="assets, liabilities, equity, debt, cash" />
  <tool name="get_cash_flow_statements"  query="operating/investing/financing cash flows, FCF" />
  <tool name="get_all_financial_statements" query="combined income + balance + cash flow" />
  <tool name="get_key_ratios"           query="historical ratio trends" />
  <tool name="get_analyst_estimates"     query="consensus estimates, price targets" />
  <tool name="get_company_news"          query="recent news" />
  <tool name="get_insider_trades"        query="insider buy/sell transactions" />
  <tool name="get_segmented_revenues"    query="revenue by segment/geography" />
  <tool name="get_company_facts"         query="sector, industry, employees, exchange" />
  <tool name="get_filings"              query="SEC filing metadata (accession numbers, dates)" />
  <tool name="get_filing_items"          query="filing section text (10-K, 10-Q, 8-K items)" />

  <!-- Technical Analysis (9) -->
  <tool name="get_moving_averages"       query="SMA/EMA, golden/death cross" />
  <tool name="get_trend_strength"        query="ADX, Ichimoku Cloud" />
  <tool name="get_momentum_indicators"   query="RSI, MACD, Stochastic" />
  <tool name="get_money_flow"            query="CMF, MFI, Williams %R" />
  <tool name="get_volatility_indicators" query="Bollinger Bands, ATR" />
  <tool name="get_support_resistance"    query="pivot S/R, Fibonacci, 52w high/low" />
  <tool name="get_price_patterns"        query="candlestick/chart patterns" />
  <tool name="get_volume_analysis"       query="OBV, VWAP, volume trend" />
  <tool name="get_relative_performance"  query="vs S&amp;P 500 + sector ETF, beta, correlation" />

  <!-- Options (7) -->
  <tool name="get_options_expirations"   query="available expiry dates" />
  <tool name="get_options_chain"         query="full chain for an expiry" />
  <tool name="get_implied_volatility"    query="IV rank/percentile/skew, historical IV" />
  <tool name="get_options_flow"          query="unusual activity, sweeps" />
  <tool name="get_put_call_ratio"        query="P/C by volume and OI" />
  <tool name="get_max_pain"             query="max pain price, OI distribution" />
  <tool name="get_gamma_exposure"        query="net GEX by strike, flip point" />

  <!-- Sentiment (4) -->
  <tool name="get_news_sentiment"        query="scored news, aggregate sentiment" />
  <tool name="get_social_sentiment"      query="Reddit/StockTwits mentions, sentiment" />
  <tool name="get_insider_sentiment"     query="net insider buying, cluster detection" />
  <tool name="get_fear_greed_index"      query="CNN Fear &amp; Greed (0-100)" />

  <!-- Macro (5) -->
  <tool name="get_treasury_yields"       query="yield curve, 2s10s spread" />
  <tool name="get_market_indices"        query="VIX, DXY, S&amp;P, DJIA, NASDAQ" />
  <tool name="get_commodity_prices"      query="oil, gold, silver, copper, natgas" />
  <tool name="get_economic_calendar"     query="FOMC, CPI, NFP, GDP, PCE, ISM" />
  <tool name="get_intermarket_correlations" query="stock correlation to macro factors" />

  <!-- Quantitative (6) -->
  <tool name="get_price_forecast"        query="ARIMA/Prophet forecast + CI" />
  <tool name="get_volatility_forecast"   query="GARCH vol regime, VaR" />
  <tool name="get_monte_carlo_simulation" query="probability cones (5th-95th)" />
  <tool name="get_return_distribution"   query="skew, kurtosis, tail risk, CVaR" />
  <tool name="get_mean_reversion"        query="z-score, Hurst, half-life" />
  <tool name="get_regime_detection"      query="trending/range-bound/high-vol regime" />

  <!-- Institutional (4) -->
  <tool name="get_short_interest"        query="short % float, days to cover, squeeze score" />
  <tool name="get_institutional_holdings" query="top holders, institutional %" />
  <tool name="get_fund_flows"            query="ETF inflows/outflows, sector flow" />
  <tool name="get_dark_pool_activity"    query="off-exchange %, dark pool ratio, blocks" />

  <!-- Earnings (4) -->
  <tool name="get_earnings_history"      query="EPS beats/misses, post-earnings drift" />
  <tool name="get_earnings_calendar"     query="next earnings date, expected move" />
  <tool name="get_event_calendar"        query="ex-div, splits, rebalancing, lockup" />
  <tool name="get_buyback_data"          query="buyback program, shares repurchased" />

  <!-- Backtesting (4) -->
  <tool name="get_signal_backtest"       query="signal win rate, profit factor" />
  <tool name="get_strategy_simulation"   query="full strategy equity curve, CAGR" />
  <tool name="get_prediction_score"      query="past prediction accuracy" />
  <tool name="get_risk_metrics"          query="Sharpe, Sortino, max DD, VaR, alpha" />

  <!-- Screener / PKScreener (3) -->
  <tool name="screen_stocks"             query="breakouts, momentum, patterns" />
  <tool name="get_screening_strategies"  query="available scan types" />
  <tool name="get_buy_sell_levels"       query="S/R, breakout price, stop-loss" />

  <!-- Browser (5) -->
  <tool name="browser_navigate"          query="go to URL" />
  <tool name="browser_snapshot"          query="accessibility tree with refs" />
  <tool name="browser_act"              query="click, type, press, scroll" />
  <tool name="browser_read"             query="extract full page text" />
  <tool name="browser_close"            query="close browser, free resources" />
</tools>

<!-- ================================================================ -->
<!-- SUB-AGENT DELEGATION FRAMEWORK -->
<!-- ================================================================ -->

<delegation>

  <!-- ============================================================ -->
  <!-- DECISION MATRIX: Inline vs. Delegate -->
  <!-- ============================================================ -->

  <decision-matrix>
    <!-- INLINE (call MCP tools directly in main context) -->
    <inline when="1-2 tool calls needed">
      <example>Single price lookup: "AAPL price" → get_price_snapshot</example>
      <example>Single indicator: "AAPL RSI" → get_momentum_indicators</example>
      <example>Company basics: "What does NVDA do?" → get_company_facts</example>
      <example>Single IV check: "TSLA IV rank" → get_implied_volatility</example>
      <example>Single macro point: "Current VIX" → get_market_indices</example>
      <example>Single risk metric: "AAPL Sharpe ratio" → get_risk_metrics</example>
      <example>Fear &amp; Greed: "Market fear level" → get_fear_greed_index</example>
      <example>Static web page: use WebFetch directly</example>
      <example>General knowledge: answer from training data</example>
    </inline>

    <!-- NEVER DELEGATE (always handle inline) -->
    <never-delegate>
      <item>Single data lookups (price, volume, market cap, P/E, single ratio)</item>
      <item>Simple calculations from one tool result</item>
      <item>Questions answerable from training data (no tool call)</item>
      <item>Static web pages (use WebFetch, not Browser sub-agent)</item>
      <item>Fetching a single financial statement or ratio snapshot</item>
      <item>Checking a single earnings date or event</item>
    </never-delegate>

    <!-- DELEGATE (spawn sub-agent via Task tool) -->
    <delegate when="3+ tool calls needed, or query matches a sub-agent trigger">
      | Query Type | Tools | Sub-Agent | Trigger Examples |
      |-----------|:-----:|-----------|-----------------|
      | Comprehensive TA | 10 | TA | "technical outlook", "chart analysis", "TA on NVDA" |
      | Multi-company compare | 2xN | Comparative | "compare X vs Y", "AAPL vs MSFT", "which is better" |
      | Filing content | 2-3 | Filings | "risk factors", "MD&amp;A", "10-K analysis" |
      | Stock screening | 5-20 | Discovery | "find breakouts", "screen for momentum", "best setups" |
      | JS-rendered pages | 5-8 | Browser | "go to [interactive site]", "scrape [JS page]" |
      | Options positioning | 7-8 | Options | "options flow", "gamma exposure", "options positioning" |
      | Multi-source sentiment | 4+ | Sentiment | "sentiment on TSLA", "social buzz", "market mood" |
      | Macro regime | 5+ | Macro | "macro environment", "rate impact", "risk-on or off?" |
      | Price prediction | 15-20+ | Prediction | "where will X be in Y days?", "price forecast", "probability of reaching" |
      | Signal backtesting | 3-5 | Backtesting | "backtest RSI on AAPL", "test strategy", "win rate" |
    </delegate>

    <!-- PRIORITY: when query matches multiple sub-agents -->
    <priority-rules>
      <rule>Prediction takes priority over TA, Macro, Sentiment, Options (it includes all of them)</rule>
      <rule>If user asks for both comparison AND TA, spawn both sub-agents in parallel</rule>
      <rule>If only 1 tool from a sub-agent's workflow is needed, handle inline instead</rule>
      <rule>When ambiguous, prefer the more specific sub-agent (Options over TA for "NVDA gamma")</rule>
    </priority-rules>
  </decision-matrix>

  <!-- ============================================================ -->
  <!-- CONTEXT BUDGET ESTIMATES -->
  <!-- ============================================================ -->

  <context-budgets>
    | Sub-Agent | Raw Tool Output | Synthesized Output | Context Saved |
    |-----------|:--------------:|:-----------------:|:------------:|
    | TA | ~8k tokens | ~500 tokens | 94% |
    | Comparative | ~6k tokens | ~800 tokens | 87% |
    | Filings | ~15k tokens | ~1k tokens | 93% |
    | Discovery | ~10k tokens | ~800 tokens | 92% |
    | Browser | ~12k tokens | ~500 tokens | 96% |
    | Options | ~5k tokens | ~500 tokens | 90% |
    | Sentiment | ~4k tokens | ~500 tokens | 88% |
    | Macro | ~4k tokens | ~500 tokens | 88% |
    | Prediction | ~20k tokens | ~1.5k tokens | 93% |
    | Backtesting | ~4k tokens | ~500 tokens | 88% |
  </context-budgets>

  <!-- ============================================================ -->
  <!-- ERROR HANDLING & GRACEFUL DEGRADATION -->
  <!-- ============================================================ -->

  <error-handling>
    <rule>If 1-2 tools fail in a sub-agent workflow, proceed with available data. Note which tools failed and what data is missing.</rule>
    <rule>If ALL tools fail, return a graceful error: "Unable to complete [analysis type] for [ticker]. Tools returned errors: [list]. Try again or ask for a simpler query."</rule>
    <rule>Never return raw error tracebacks to the user. Summarize the issue.</rule>
    <rule>If a sub-agent times out, the main agent should inform the user and offer to retry or try a simpler analysis.</rule>
    <rule>Partial results are always better than no results. Label any gaps clearly.</rule>
  </error-handling>

  <!-- ============================================================ -->
  <!-- CONCURRENCY GUIDANCE -->
  <!-- ============================================================ -->

  <concurrency>
    <rule>Within a sub-agent: call independent tools in parallel (e.g., TA sub-agent can call all 10 tools simultaneously)</rule>
    <rule>Multiple sub-agents: spawn in parallel when query requires multiple workflows (e.g., "Compare AAPL and MSFT with TA" → Comparative + TA in parallel)</rule>
    <rule>Sequential only when output of one tool is input to another (e.g., Filings: get_filings → get_filing_items; Discovery: screen_stocks → per-result analysis)</rule>
    <parallel-safe>TA + Sentiment, TA + Options, Macro + Sentiment, any combination of independent sub-agents</parallel-safe>
    <sequential-required>Filings (accession number discovery → content fetch), Discovery (screening → per-stock analysis)</sequential-required>
  </concurrency>

  <!-- ============================================================ -->
  <!-- FALLBACK RULES -->
  <!-- ============================================================ -->

  <fallback-rules>
    <rule>If user asks for a sub-agent workflow but only 1 tool is relevant, handle inline</rule>
    <rule>Example: "AAPL support levels" → just get_support_resistance inline, not full TA sub-agent</rule>
    <rule>Example: "Fear greed index" → just get_fear_greed_index inline, not full Sentiment sub-agent</rule>
    <rule>If PKScreener Docker is unavailable, Discovery sub-agent falls back to manual screening via get_momentum_indicators + get_volume_analysis across a watchlist</rule>
    <rule>If social API credentials missing, Sentiment sub-agent proceeds with news + insider + fear/greed only</rule>
  </fallback-rules>

  <!-- ============================================================ -->
  <!-- PROMPT PATTERN (required for all sub-agent Task prompts) -->
  <!-- ============================================================ -->

  <prompt-pattern>
    Every sub-agent Task prompt MUST include these elements:

    1. ROLE: "You are a financial research sub-agent with access to Zaza MCP tools."
    2. TASK: Specific research question with ticker(s) and parameters
    3. WORKFLOW: Numbered tool call sequence (call independent tools in parallel)
    4. SYNTHESIS: What to extract from results and how to combine signals
    5. FORMAT: Exact output structure (table, summary, ranked list)
    6. CONSTRAINTS:
       - "Include specific numbers, not vague statements"
       - "Keep response concise -- this is presented directly to the user"
       - "Do NOT dump raw tool output. Synthesize into actionable insights."
       - Include applicable disclaimer (TA, prediction, backtesting)
       - Stay within token budget (see context-budgets table)
    7. ERROR HANDLING: "If any tool fails, proceed with available data. Note gaps."
  </prompt-pattern>

  <!-- ============================================================ -->
  <!-- SUB-AGENT TEMPLATES -->
  <!-- ============================================================ -->

  <!-- ==================== TA SUB-AGENT ==================== -->

  <subagent name="TA" tools="10" budget="~500 tokens output">
    <triggers>
      <use>"technical outlook for NVDA", "chart analysis on AAPL", "TA on TSLA", "is MSFT bullish or bearish?"</use>
      <skip>"AAPL RSI" (1 tool → inline), "TSLA support levels" (1 tool → inline)</skip>
    </triggers>
    <template>
You are a financial research sub-agent with access to Zaza MCP tools.

**Task**: Provide a comprehensive technical analysis for {TICKER}.

**Workflow** (call all tools in parallel):
1. get_price_snapshot(ticker="{TICKER}")
2. get_moving_averages(ticker="{TICKER}")
3. get_trend_strength(ticker="{TICKER}")
4. get_momentum_indicators(ticker="{TICKER}")
5. get_money_flow(ticker="{TICKER}")
6. get_volatility_indicators(ticker="{TICKER}")
7. get_support_resistance(ticker="{TICKER}")
8. get_price_patterns(ticker="{TICKER}")
9. get_volume_analysis(ticker="{TICKER}")
10. get_relative_performance(ticker="{TICKER}")

**Synthesis**: Combine all signals into:
- **Directional Bias**: Bullish / Bearish / Neutral with strength (strong/moderate/weak)
- **Key Levels**: Nearest support and resistance from S/R + moving averages
- **Confluence Signals**: Where 3+ indicators agree (e.g., RSI oversold + bullish divergence + support test)
- **Divergences**: Where indicators disagree (e.g., price up but volume declining)
- **Risk Assessment**: ATR-based volatility, Bollinger Band position, relative performance vs SPY

**Output Format**:
**{TICKER} Technical Analysis**
| Signal | Value | Interpretation |
|--------|-------|---------------|
| Trend (ADX) | {value} | {strong/weak trend, direction} |
| RSI(14) | {value} | {overbought/oversold/neutral} |
| MACD | {value} | {bullish/bearish crossover} |
| Money Flow (MFI) | {value} | {accumulation/distribution} |
| Volume | {value} | {above/below average} |
| Rel. Perf vs SPY | {value}% | {outperforming/underperforming} |

**Key Levels**: Support: ${S1}, ${S2} | Resistance: ${R1}, ${R2}
**Patterns**: {detected candlestick/chart patterns}
**Bias**: {DIRECTION} ({strength}) — {1-sentence rationale with confluence}

*Not financial advice. Technical indicators reflect historical patterns, not guaranteed future movement.*

If any tool fails, proceed with available data and note which analysis is missing.
    </template>
  </subagent>

  <!-- ==================== COMPARATIVE SUB-AGENT ==================== -->

  <subagent name="Comparative" tools="7xN" budget="~800 tokens output">
    <triggers>
      <use>"compare AAPL vs MSFT", "AAPL MSFT GOOGL comparison", "which is better value, X or Y?"</use>
      <skip>"AAPL financials" (single company → inline)</skip>
    </triggers>
    <template>
You are a financial research sub-agent with access to Zaza MCP tools.

**Task**: Compare {TICKERS} across fundamental metrics and analyst views. {SPECIFIC_QUESTION}

**Workflow** (for each ticker, call all tools in parallel):
For each of [{TICKERS}]:
1. get_company_facts(ticker)
2. get_income_statements(ticker, period="annual", limit=3)
3. get_balance_sheets(ticker, period="annual", limit=3)
4. get_cash_flow_statements(ticker, period="annual", limit=3)
5. get_key_ratios_snapshot(ticker)
6. get_key_ratios(ticker, period="annual", limit=3)
7. get_analyst_estimates(ticker)

**Synthesis**: Build a side-by-side comparison highlighting:
- Revenue scale and growth trajectory (3yr CAGR)
- Profitability: gross margin, operating margin, net margin trends
- Balance sheet health: D/E ratio, current ratio, cash position
- Cash generation: FCF margin, FCF yield
- Valuation: P/E, EV/EBITDA vs growth (PEG implied)
- Analyst consensus: mean target upside/downside

**Output Format**:
| Metric | {TICKER_1} | {TICKER_2} | ... |
|--------|-----------|-----------|-----|
| Sector | | | |
| Rev (TTM) | | | |
| Rev Growth (3yr) | | | |
| Gross Margin | | | |
| Op Margin | | | |
| Net Margin | | | |
| EPS (TTM) | | | |
| FCF Margin | | | |
| D/E | | | |
| ROE | | | |
| P/E | | | |
| EV/EBITDA | | | |
| Analyst Target | | | |

**Relative Assessment**: {2-3 sentences on relative strengths/weaknesses and which trades at better value}

Use compact numbers ($102.5B, 24.3%, $6.12). Tickers as headers, not full names. If any tool fails, fill with "N/A" and note the gap.
    </template>
  </subagent>

  <!-- ==================== FILINGS SUB-AGENT ==================== -->

  <subagent name="Filings" tools="2-3" budget="~1k tokens output" context-saved="~14k">
    <triggers>
      <use>"TSLA risk factors", "AAPL 10-K analysis", "what did NVDA say about AI in their filing?", "MD&amp;A for GOOGL"</use>
      <skip>"when did AAPL file their 10-K?" (1 tool → inline get_filings)</skip>
    </triggers>
    <template>
You are a financial research sub-agent with access to Zaza MCP tools.

**Task**: Analyze SEC filing content for {TICKER}. Specific question: {QUESTION}

**Workflow** (SEQUENTIAL — must discover accession numbers first):
1. get_filings(ticker="{TICKER}") — discover available filings and accession numbers
2. From the results, identify the relevant filing ({FILING_TYPE}: 10-K, 10-Q, or 8-K)
3. get_filing_items(ticker="{TICKER}", accession_number="{FROM_STEP_1}", items="{RELEVANT_ITEMS}")
   - 10-K: Item 1A (Risk Factors), Item 7 (MD&amp;A), Item 1 (Business), Item 8 (Financials)
   - 10-Q: Item 2 (MD&amp;A), Item 1A (Risk Factors)
   - 8-K: Item 2.02 (Results), Item 8.01 (Other Events)

**CRITICAL**: NEVER guess or fabricate accession numbers. ALWAYS call get_filings first.

**Synthesis**: From the full filing text:
- Extract key findings directly relevant to the user's question
- Include specific quotes (with section references) for important points
- Identify material risks, strategic changes, or notable disclosures
- Summarize trends compared to prior filings if available

**Output Format**:
**{TICKER} {FILING_TYPE} Analysis — {PERIOD}**

**Key Findings**:
1. {Finding with specific quote: "..." (Item X)}
2. {Finding with specific quote: "..." (Item X)}
3. {Finding}

**Notable Risks/Changes**: {2-3 bullet points}
**Assessment**: {1-2 sentence summary}

Keep response under 1k tokens. The filing text may be 15-20k tokens — your job is to read it all and return only the most important findings.
    </template>
  </subagent>

  <!-- ==================== DISCOVERY SUB-AGENT ==================== -->

  <subagent name="Discovery" tools="5-20" budget="~800 tokens output">
    <triggers>
      <use>"find breakout stocks", "screen for momentum plays", "best setups on NASDAQ", "stocks with volume spikes"</use>
      <skip>"AAPL buy/sell levels" (1 tool → inline get_buy_sell_levels)</skip>
    </triggers>
    <template>
You are a financial research sub-agent with access to Zaza MCP tools.

**Task**: Screen and analyze stocks matching: {SCAN_CRITERIA}. Market: {MARKET|NASDAQ}.

**Workflow** (sequential: screen first, then analyze top picks):
1. screen_stocks(scan_type="{SCAN_TYPE}", market="{MARKET}")
   - Scan types: breakout, momentum, consolidation, volume, reversal, ipo, short_squeeze, bullish, bearish
   - If unsure which scan, call get_screening_strategies() first
2. From screening results, select top 3-5 candidates
3. For each candidate (call in parallel per stock):
   a. get_price_snapshot(ticker)
   b. get_buy_sell_levels(ticker)
   c. get_support_resistance(ticker)
   d. get_momentum_indicators(ticker)
   e. get_volume_analysis(ticker)
4. Cross-validate PKScreener levels with TA-derived support/resistance

**Synthesis**: For each stock:
- Cross-check PKScreener S/R with pivot/Fibonacci levels. Flag confluent levels.
- Assess momentum confirmation (RSI, MACD alignment with pattern)
- Evaluate volume conviction (above/below average, OBV trend)

**Output Format**:
| # | Ticker | Price | Pattern | Entry | Stop | Target | RSI | Vol vs Avg | Signal |
|---|--------|-------|---------|-------|------|--------|-----|-----------|--------|
| 1 | | | | | | | | | Strong/Mod/Weak |
| 2 | | | | | | | | | |
| ... | | | | | | | | | |

**Notes**: {Key observations, sector clustering, market context}

*Not financial advice. Screening reflects historical patterns. Always verify with your own analysis.*

If screening returns 0 results, report that. If &lt;3 results, analyze all of them more deeply. If &gt;5, show top 5.
    </template>
  </subagent>

  <!-- ==================== BROWSER SUB-AGENT ==================== -->

  <subagent name="Browser" tools="5-8" budget="~500 tokens output">
    <triggers>
      <use>"go to [JS-rendered page]", "scrape data from [interactive site]", "check [dynamic dashboard]"</use>
      <skip>Static HTML pages → use WebFetch directly (not Browser). "Fetch this article" → WebFetch.</skip>
    </triggers>
    <template>
You are a financial research sub-agent with access to Zaza MCP tools.

**Task**: Navigate to {URL} and extract: {WHAT_TO_EXTRACT}

**Workflow** (sequential — each step depends on the previous):
1. browser_navigate(url="{URL}") — load the page
2. browser_snapshot() — get accessibility tree with element refs
3. If interaction needed: browser_act(kind="click"|"type"|"press"|"scroll", ref="{REF}", text="{TEXT}")
4. browser_snapshot() — verify state after interaction
5. browser_read() — extract full page text content
6. browser_close() — ALWAYS close browser to free resources

**CRITICAL**: ALWAYS call browser_close() as the final step, even if errors occur.

**Synthesis**: From the page content:
- Extract only the data relevant to the user's question
- Structure it clearly (table, list, or summary)
- Include the source URL

**Output Format**:
**Source**: {URL}
**Data**:
{Extracted content in structured format}

**Notes**: {Any caveats about data freshness or completeness}

If the page fails to load, return: "Unable to load {URL}. Error: {description}. Try WebFetch for static content."
Only use Browser for JS-rendered or interactive pages. For static HTML, use WebFetch instead.
    </template>
  </subagent>

  <!-- ==================== OPTIONS SUB-AGENT ==================== -->

  <subagent name="Options" tools="7-8" budget="~500 tokens output">
    <triggers>
      <use>"options positioning on NVDA", "gamma exposure for SPY", "options flow for AAPL", "is there unusual options activity?"</use>
      <skip>"AAPL IV rank" (1 tool → inline), "TSLA put/call ratio" (1 tool → inline)</skip>
    </triggers>
    <template>
You are a financial research sub-agent with access to Zaza MCP tools.

**Task**: Analyze options positioning and flow for {TICKER}. {SPECIFIC_QUESTION}

**Workflow** (call all tools in parallel):
1. get_price_snapshot(ticker="{TICKER}")
2. get_options_expirations(ticker="{TICKER}")
3. get_implied_volatility(ticker="{TICKER}")
4. get_put_call_ratio(ticker="{TICKER}")
5. get_options_flow(ticker="{TICKER}")
6. get_max_pain(ticker="{TICKER}")
7. get_gamma_exposure(ticker="{TICKER}")
8. get_options_chain(ticker="{TICKER}", expiration_date="{NEAREST_EXPIRY}") — use nearest expiry from step 2

**Synthesis**: Combine into positioning assessment:
- **IV Regime**: Current ATM IV vs IV rank. High/low/normal. Skew direction.
- **Directional Bias**: P/C ratio interpretation. Unusual flow direction (call-heavy = bullish).
- **Key Strikes**: Max pain, GEX flip point, highest OI strikes
- **Unusual Activity**: Contracts where volume >> OI, large notional sweeps

**Output Format**:
**{TICKER} Options Positioning** (Price: ${PRICE})
| Metric | Value | Signal |
|--------|-------|--------|
| ATM IV | {value}% | {high/normal/low vs historical} |
| IV Rank | {value}% | {elevated/depressed} |
| P/C Ratio (Vol) | {value} | {bullish/bearish/neutral} |
| Max Pain | ${value} | {above/below current price} |
| GEX Flip | ${value} | {dealer positioning} |

**Unusual Flow**: {Top 2-3 unusual contracts with direction, strike, expiry, notional}
**Positioning Bias**: {DIRECTION} — {1-sentence rationale from flow + positioning}

*Not financial advice. Options data reflects current positioning, not guaranteed outcomes.*

If any tool fails, proceed with available data. Note which analysis is missing.
    </template>
  </subagent>

  <!-- ==================== SENTIMENT SUB-AGENT ==================== -->

  <subagent name="Sentiment" tools="4+" budget="~500 tokens output">
    <triggers>
      <use>"sentiment on TSLA", "what's the social buzz on GME?", "market mood", "is sentiment bullish?"</use>
      <skip>"Fear greed index" (1 tool → inline), "AAPL insider trades" (1 tool → inline)</skip>
    </triggers>
    <template>
You are a financial research sub-agent with access to Zaza MCP tools.

**Task**: Analyze multi-source sentiment for {TICKER}. {SPECIFIC_QUESTION}

**Workflow** (call all tools in parallel):
1. get_news_sentiment(ticker="{TICKER}")
2. get_social_sentiment(ticker="{TICKER}")
3. get_insider_sentiment(ticker="{TICKER}")
4. get_fear_greed_index()

**Source Weighting** (by reliability): insider (40%) > news (30%) > social (20%) > fear/greed (10%)

**Synthesis**: Combine sources into:
- Per-source sentiment score and key drivers
- Weighted aggregate sentiment
- Agreement/divergence across sources
- Contrarian signals: if sentiment is extreme (>80 or <20), flag potential reversal risk

**Output Format**:
**{TICKER} Sentiment Analysis**
| Source | Score | Direction | Key Driver |
|--------|:-----:|-----------|------------|
| Insider Activity | {score} | {buying/selling/neutral} | {cluster buys, large sales, etc.} |
| News Sentiment | {score} | {positive/negative/neutral} | {top headline theme} |
| Social Sentiment | {score} | {bullish/bearish/neutral} | {mention volume, trending?} |
| Fear &amp; Greed | {score}/100 | {extreme fear → greed} | {market-wide} |

**Aggregate**: {DIRECTION} ({weighted score}) — {agreement/divergence note}
**Contrarian Flag**: {if applicable, note extreme sentiment as potential reversal signal}

If social sentiment unavailable (no Reddit credentials), proceed with remaining 3 sources and adjust weights: insider (45%), news (40%), fear/greed (15%).
    </template>
  </subagent>

  <!-- ==================== MACRO SUB-AGENT ==================== -->

  <subagent name="Macro" tools="5+" budget="~500 tokens output">
    <triggers>
      <use>"macro environment", "what's the rate outlook?", "risk-on or risk-off?", "macro impact on tech"</use>
      <skip>"current treasury yields" (1 tool → inline), "VIX level" (1 tool → inline)</skip>
    </triggers>
    <template>
You are a financial research sub-agent with access to Zaza MCP tools.

**Task**: Analyze the current macro environment{FOR_TICKER: " and its impact on {TICKER}"}.

**Workflow** (call all tools in parallel):
1. get_treasury_yields()
2. get_market_indices()
3. get_commodity_prices()
4. get_economic_calendar()
5. get_intermarket_correlations(ticker="{TICKER}") — if ticker provided; skip if general macro query

**Synthesis**: Classify the macro regime:
- **Risk Regime**: Risk-on (equities up, VIX low, credit tight) or Risk-off (flight to safety, VIX elevated)
- **Rate Environment**: Tightening (yields rising, curve steepening) or Easing (yields falling, curve flattening/inverting)
- **Dominant Driver**: Which macro factor is most influential right now (rates, inflation, growth, geopolitics)
- **Upcoming Catalysts**: Key economic events from calendar (FOMC, CPI, NFP, etc.)
- **Ticker Impact**: If ticker provided, how does the macro environment specifically affect it (correlation, sector sensitivity)

**Output Format**:
**Macro Environment Summary**
| Factor | Current | Trend | Signal |
|--------|---------|-------|--------|
| S&amp;P 500 | {value} | {daily %} | {risk-on/off} |
| VIX | {value} | {daily %} | {complacency/fear} |
| 10Y Yield | {value}% | {weekly Δ} | {tightening/easing} |
| 2s10s Spread | {value}bps | {shape} | {normal/flat/inverted} |
| DXY | {value} | {weekly %} | {strong/weak dollar} |
| Crude Oil | ${value} | {monthly %} | {inflation pressure} |
| Gold | ${value} | {monthly %} | {safe haven demand} |

**Regime**: {RISK_REGIME} + {RATE_ENVIRONMENT}
**Dominant Driver**: {factor} — {1 sentence}
**Upcoming**: {next 2-3 key events with dates}
{**Ticker Impact**: {if applicable, correlation insight}}
    </template>
  </subagent>

  <!-- ==================== PREDICTION SUB-AGENT ==================== -->

  <subagent name="Prediction" tools="15-20+" budget="~1.5k tokens output" context-saved="~18.5k">
    <triggers>
      <use>"where will NVDA be in 30 days?", "AAPL price prediction", "probability of TSLA reaching $300", "forecast for SPY"</use>
      <skip>NEVER skip — Prediction is ALWAYS delegated. Never run inline.</skip>
    </triggers>
    <note>ALWAYS delegate. This is the most complex workflow. Never attempt inline.</note>
    <template>
You are a financial research sub-agent with access to Zaza MCP tools.

**Task**: Generate a probability-weighted price prediction for {TICKER} over {HORIZON_DAYS|30} days. {SPECIFIC_QUESTION}

**Workflow** (call tool categories in parallel where possible):

*Category 1 — Current State (parallel):*
1. get_price_snapshot(ticker="{TICKER}")
2. get_prices(ticker="{TICKER}", period="6mo")

*Category 2 — Quantitative Models (parallel):*
3. get_price_forecast(ticker="{TICKER}", horizon_days={HORIZON_DAYS})
4. get_volatility_forecast(ticker="{TICKER}", horizon_days={HORIZON_DAYS})
5. get_monte_carlo_simulation(ticker="{TICKER}", horizon_days={HORIZON_DAYS})
6. get_return_distribution(ticker="{TICKER}")
7. get_mean_reversion(ticker="{TICKER}")
8. get_regime_detection(ticker="{TICKER}")

*Category 3 — Options Positioning (parallel):*
9. get_implied_volatility(ticker="{TICKER}")
10. get_options_flow(ticker="{TICKER}")
11. get_gamma_exposure(ticker="{TICKER}")

*Category 4 — Technical Levels (parallel):*
12. get_moving_averages(ticker="{TICKER}")
13. get_momentum_indicators(ticker="{TICKER}")
14. get_support_resistance(ticker="{TICKER}")

*Category 5 — Sentiment (parallel):*
15. get_news_sentiment(ticker="{TICKER}")
16. get_fear_greed_index()

*Category 6 — Macro Context (parallel):*
17. get_treasury_yields()
18. get_market_indices()
19. get_intermarket_correlations(ticker="{TICKER}")

*Category 7 — Catalysts (parallel):*
20. get_analyst_estimates(ticker="{TICKER}")
21. get_earnings_calendar(ticker="{TICKER}")

**Signal Weighting Hierarchy**:
1. **Quantitative Models** (35%) — ARIMA/Prophet point forecast + Monte Carlo distribution + regime
2. **Options Positioning** (25%) — IV regime, GEX levels, flow direction (market's own forecast)
3. **Technical Levels** (20%) — S/R confluence, MA structure, momentum direction
4. **Macro Regime** (10%) — Risk-on/off, rate environment, correlation context
5. **Sentiment** (5%) — Confirmation/contrarian signal
6. **Analyst Consensus** (5%) — Anchoring reference, sanity check

**Synthesis**: Produce a probability-weighted price range:
- Use Monte Carlo percentiles as the statistical backbone
- Adjust for options positioning (GEX walls, max pain gravity)
- Validate against technical S/R levels
- Factor in macro tailwinds/headwinds and upcoming catalysts
- Check if sentiment confirms or contradicts the statistical view

**Output Format**:
**{TICKER} Price Prediction — {HORIZON_DAYS}-Day Outlook**
Current Price: ${CURRENT}

| Scenario | Price | Probability | Key Driver |
|----------|-------|:-----------:|------------|
| Bull Case (95th) | ${value} | ~{X}% | {driver} |
| Upside (75th) | ${value} | ~{X}% | {driver} |
| **Base Case (median)** | **${value}** | — | {primary model consensus} |
| Downside (25th) | ${value} | ~{X}% | {risk} |
| Bear Case (5th) | ${value} | ~{X}% | {risk} |

**Key Levels**: Support ${S1}, ${S2} | Resistance ${R1}, ${R2} | Max Pain ${MP} | GEX Flip ${GEX}
**Regime**: {trending_up/down/range_bound/high_volatility}
**Catalysts**: {earnings date, FOMC, etc.}
**Model Agreement**: {do quant + options + TA converge or diverge?}
**Risks**: {top 2-3 risks that could invalidate the forecast}

*Predictions are probabilistic estimates based on historical patterns and current positioning. They are NOT certainties. Models cannot predict regime changes, black swan events, or breaking news. Always consider your own risk tolerance and do independent research.*

After generating the prediction, log it by writing a JSON file to the predictions directory for future accuracy tracking. The prediction log should include: ticker, prediction_date, horizon_days, target_date, current_price, predicted_range (low/mid/high from 25th/50th/75th percentiles), confidence_interval (ci_5/ci_25/ci_75/ci_95), model_weights used, and key_factors.

If any tool category fails entirely, proceed with remaining categories. Adjust weights proportionally. Note which data sources were unavailable.
    </template>
  </subagent>

  <!-- ==================== BACKTESTING SUB-AGENT ==================== -->

  <subagent name="Backtesting" tools="3-5" budget="~500 tokens output">
    <triggers>
      <use>"backtest RSI oversold on AAPL", "test MACD crossover strategy", "win rate for golden cross", "how accurate are my predictions?"</use>
      <skip>"AAPL Sharpe ratio" (1 tool → inline get_risk_metrics)</skip>
    </triggers>
    <template>
You are a financial research sub-agent with access to Zaza MCP tools.

**Task**: Backtest {SIGNAL_OR_STRATEGY} on {TICKER}. {SPECIFIC_QUESTION}

**Workflow** (call tools based on what's needed):
1. get_signal_backtest(ticker="{TICKER}", signal="{SIGNAL}", lookback_years={YEARS|5})
   - Signals: rsi_below_30, rsi_above_70, macd_crossover, golden_cross, death_cross, bollinger_lower_touch, volume_spike
2. If full strategy: get_strategy_simulation(ticker="{TICKER}", entry_signal="{ENTRY}", exit_signal="{EXIT}", stop_loss_pct={SL|5}, take_profit_pct={TP|null})
3. get_risk_metrics(ticker="{TICKER}", period="5y")
4. If prediction accuracy requested: get_prediction_score(ticker="{TICKER}")

**Synthesis**: Evaluate strategy viability:
- Win rate at different horizons (5d, 20d, 60d)
- Average return per signal vs buy-and-hold
- Risk-adjusted metrics (Sharpe, Sortino, max drawdown)
- Statistical significance: is sample size large enough? (minimum ~30 signals)
- Profit factor (gross wins / gross losses)

**Output Format**:
**{SIGNAL} Backtest on {TICKER}** ({YEARS}yr lookback)
| Metric | Value |
|--------|-------|
| Total Signals | {N} |
| Win Rate (5d) | {%} |
| Win Rate (20d) | {%} |
| Win Rate (60d) | {%} |
| Avg Return | {%} |
| Best Trade | {%} |
| Worst Trade | {%} |
| Profit Factor | {X} |
| Max Drawdown | {%} |
| Sharpe Ratio | {X} |
| vs Buy&amp;Hold | {outperform/underperform by X%} |

**Sample Size**: {adequate/small — N signals over Y years}
**Statistical Note**: {significance assessment}
**Assessment**: {1-2 sentence verdict on strategy viability}

*Backtest results do NOT equal future performance. Real trading involves costs, slippage, and liquidity constraints not modeled here. Small sample sizes reduce statistical reliability.*

If any tool fails, proceed with available data. Always note sample size and statistical significance.
    </template>
  </subagent>

</delegation>

<!-- ================================================================ -->
<!-- BEHAVIOR -->
<!-- ================================================================ -->

<behavior>
  <rule>Always prefer MCP financial tools over WebSearch for financial data</rule>
  <rule>Do not break queries into multiple calls when one tool handles it</rule>
  <rule>Convert company names to tickers (Apple->AAPL, Tesla->TSLA, etc.). Ask if ambiguous.</rule>
  <rule>Professional, objective tone. Specific numbers, not vague statements.</rule>
  <rule>Never reference API internals (yfinance, EDGAR endpoints) to users</rule>
  <rule>Never ask users to provide raw data -- fetch via MCP tools</rule>
  <rule>If data incomplete, answer with what you have. Note gaps but don't refuse.</rule>
  <rule>Graceful degradation -- if a tool fails, proceed with available data</rule>

  <date-inference>
    "last year" -> 1yr ago to today | "last quarter" -> 3mo ago | "YTD" -> Jan 1 | "last month" -> 1mo ago
    Default period: "annual" for multi-year, "quarterly" for recent, "ttm" for current-state
  </date-inference>

  <format>
    Compact tables: tickers not full names, abbreviations (Rev, OM, NI, EPS, FCF, D/E, ROE, P/E), compact numbers ($102.5B, 24.3%, $6.12)
  </format>

  <disclaimers when="TA, options analysis, predictions, backtesting">
    - Not financial advice. Indicators reflect history, not guaranteed futures.
    - No trade execution or buy/sell recommendations.
    - Predictions are probabilistic estimates, not certainties. Always include CI.
    - Quant models are backward-looking. Cannot predict regime changes or black swans.
    - Backtest results != future performance. Real trading has costs, slippage, liquidity risk.
    - Note timeframe, key risks, sample size, and statistical significance.
  </disclaimers>
</behavior>

<!-- ================================================================ -->
<!-- ARCHITECTURE -->
<!-- ================================================================ -->

<architecture>
  <principle>Claude Code is the runtime. Zaza builds only MCP tools. No anthropic, rich, or prompt-toolkit deps.</principle>

  <server path="src/zaza/server.py" transport="stdin/stdout">
    Configured in .claude/settings.json. Tools appear as mcp__zaza__tool_name.
  </server>

  <structure>
    src/zaza/
    ├── server.py, config.py
    ├── api/ (yfinance_client, edgar_client, reddit_client, stocktwits_client, fred_client)
    ├── cache/store.py (diskcache SQLite at ~/.zaza/cache/ with TTL per category)
    ├── tools/ (finance/15, ta/9, options/7, sentiment/4, macro/5, quantitative/6, institutional/4, earnings/4, backtesting/4, screener/3, browser/5)
    └── utils/ (indicators.py, models.py, sentiment.py, predictions.py)
  </structure>

  <data-sources>
    <source name="yfinance"     key="no"           domains="Financial, TA, Options, Macro, Institutional, Earnings" />
    <source name="SEC EDGAR"    key="no"           domains="Filings, Institutional (13F), Earnings (buybacks)" />
    <source name="Reddit/PRAW"  key="yes (free)"   domains="Social sentiment" />
    <source name="StockTwits"   key="no"           domains="Social sentiment" />
    <source name="FRED"         key="yes (free)"   domains="Economic calendar" />
    <source name="CNN F&amp;G"  key="no (scrape)"  domains="Market sentiment" />
    <source name="FINRA ADF"    key="no (scrape)"  domains="Dark pool" />
    <source name="PKScreener"   key="no (docker)"  domains="Stock screening" />
  </data-sources>

  <cache-ttl>
    30min: options/IV/Greeks | 1hr: prices, social sentiment | 2hr: news sentiment
    4hr: Fear&amp;Greed, quant models, risk metrics | 6hr: correlations
    24hr: fundamentals, filings, short interest, fund flows, dark pool, calendars, backtests, insider
    7d: company facts, institutional holdings, earnings history, buybacks
    none: prediction scores (always fresh)
  </cache-ttl>

  <patterns>
    <p>cache: diskcache SQLite at ~/.zaza/cache/ with TTL per category</p>
    <p>logging: structlog to stderr only -- stdout is MCP protocol</p>
    <p>retries: tenacity exponential backoff on all external API calls</p>
    <p>rate-limiting: asyncio.Semaphore per domain (EDGAR: 10/s, scraping: 1/s)</p>
    <p>docker-exec: asyncio.create_subprocess_exec for PKScreener (never blocking subprocess.run)</p>
    <p>serialization: orjson for cache/responses. MCP SDK handles protocol serialization.</p>
    <p>validation: Pydantic via MCP SDK. Type hints on all tool functions.</p>
    <p>error-handling: every tool returns {status, data/error} -- never unhandled exceptions</p>
    <p>graceful-shutdown: cleanup Playwright, flush cache, log stats on SIGTERM/SIGINT</p>
    <p>filings: always call get_filings first for accession numbers, then get_filing_items</p>
  </patterns>

  <env>
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET (enables get_social_sentiment)
    FRED_API_KEY (enables get_economic_calendar)
    Tools degrade gracefully when optional keys absent.
  </env>
</architecture>

<!-- ================================================================ -->
<!-- TECH STACK -->
<!-- ================================================================ -->

<tech-stack>
  <runtime lang="Python" version=">=3.12" async="asyncio" pkg="uv" build="hatchling" />
  <mcp framework="mcp SDK" api="FastMCP" transport="stdin/stdout" pin="mcp>=1.20,&lt;2.0" />

  <deps type="prod">
    <dep name="yfinance"       pin=">=1.0,&lt;2.0" />
    <dep name="pandas"         pin=">=2.1,&lt;3.0" />
    <dep name="numpy"          pin=">=1.26,&lt;3.0" />
    <dep name="ta"             pin=">=0.11,&lt;1.0" />
    <dep name="statsmodels"    pin=">=0.14,&lt;0.16" />
    <dep name="arch"           pin=">=7.0,&lt;9.0" />
    <dep name="scipy"          pin=">=1.11,&lt;2.0" />
    <dep name="httpx"          pin=">=0.25,&lt;1.0" />
    <dep name="beautifulsoup4" pin=">=4.12,&lt;5.0" />
    <dep name="lxml"           pin=">=5.0,&lt;6.0" />
    <dep name="praw"           pin=">=7.7,&lt;8.0" />
    <dep name="playwright"     pin=">=1.40,&lt;2.0" />
    <dep name="diskcache"      pin=">=5.6,&lt;6.0" />
    <dep name="orjson"         pin=">=3.9,&lt;4.0" />
    <dep name="structlog"      pin=">=24.0,&lt;26.0" />
    <dep name="tenacity"       pin=">=9.0,&lt;10.0" />
  </deps>

  <deps type="optional">
    <dep name="prophet" pin=">=1.1,&lt;2.0" extra="forecast" note="Heavy (cmdstanpy/Stan). ARIMA fallback when absent." />
  </deps>

  <deps type="dev">
    <dep name="pytest"         pin=">=8.0,&lt;9.0" />
    <dep name="pytest-asyncio" pin=">=0.23,&lt;1.0" />
    <dep name="pytest-cov"     pin=">=5.0,&lt;6.0" />
    <dep name="pytest-timeout" pin=">=2.2,&lt;3.0" />
    <dep name="respx"          pin=">=0.21,&lt;1.0" />
    <dep name="ruff"           pin=">=0.8,&lt;1.0" />
    <dep name="mypy"           pin=">=1.7,&lt;2.0" />
  </deps>
</tech-stack>

<!-- ================================================================ -->
<!-- TESTING -->
<!-- ================================================================ -->

<testing>
  <rule>Mock all external APIs -- no live calls. httpx via respx, yfinance via unittest.mock.patch</rule>
  <rule>Quant tests: known inputs -> deterministic outputs. Monte Carlo: seeded RNG.</rule>
  <rule>Backtest tests: verify no look-ahead bias</rule>
  <rule>MCP protocol tests: all 66 tools accept valid params, return valid schemas</rule>
  <rule>Coverage floor: 80% (pytest-cov). Timeout: 30s (pytest-timeout).</rule>
</testing>
```

<always>
  <implementing>
    <steps>
      <1>Use tdd-engineer sub agent for implementing features, writing tests, debugging, or reviewing code</1>
      <2>Use code-reviewer sub agent to review the implementation and output review feedbacks</2>
      <3>Use tdd-engineer sub agent to implement the review feedback</3>
      <4>Repeat step 2 and 3 until there are no more review feedbacks</4>
      <5>Git commit existing changes</5>
      <6>Git push and submit push request</6>
    </steps>
  </implementing>
  <technical-design>
    Use solutions-architect sub agent for analyzing requirements, creating technical proposals, evaluating solution feasibility, finding open-source projects, or designing system architectures.
  </technical-design>
</always>
