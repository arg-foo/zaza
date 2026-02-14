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
  <!-- SUB-AGENT FILES (in .claude/agents/) -->
  <!-- ============================================================ -->

  <!-- Agent prompt templates are stored as .md files in .claude/agents/.
       Each file has YAML frontmatter (name, description, model, color)
       and a markdown body with the system prompt.

       | Agent File       | Name        | Model  | Tools  | Triggers |
       |-----------------|-------------|--------|--------|----------|
       | ta.md           | ta          | sonnet | 10     | "technical outlook", "chart analysis", "TA on X" |
       | comparative.md  | comparative | sonnet | 7xN    | "compare X vs Y", "which is better value" |
       | filings.md      | filings     | sonnet | 2-3    | "risk factors", "MD&A", "10-K analysis" |
       | discovery.md    | discovery   | sonnet | 5-20   | "find breakouts", "screen for momentum" |
       | browser.md      | browser     | sonnet | 5-8    | "go to [JS page]", "scrape [interactive site]" |
       | options.md      | options     | sonnet | 7-8    | "options flow", "gamma exposure" |
       | sentiment.md    | sentiment   | sonnet | 4+     | "sentiment on X", "social buzz", "market mood" |
       | macro.md        | macro       | sonnet | 5+     | "macro environment", "risk-on or off?" |
       | prediction.md   | prediction  | opus   | 15-20+ | "price prediction", "where will X be in Y days?" |
       | backtesting.md  | backtesting | sonnet | 3-5    | "backtest RSI on X", "test strategy" |
  -->

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
