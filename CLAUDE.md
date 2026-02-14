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
<!-- SUB-AGENT DELEGATION -->
<!-- ================================================================ -->

<delegation>
  <!-- Inline (1-2 calls): call MCP tools directly -->
  <!-- Delegate (3+ calls): spawn sub-agent via Task tool -->

  <inline examples="single price, single indicator, single company fundamentals, single IV check, single macro point, single risk metric, Fear &amp; Greed, static web page, general knowledge" />

  <subagent name="TA" trigger="technical outlook, chart analysis" tools="10">
    <step>get_price_snapshot</step>
    <step>get_moving_averages</step>
    <step>get_trend_strength</step>
    <step>get_momentum_indicators</step>
    <step>get_money_flow</step>
    <step>get_volatility_indicators</step>
    <step>get_support_resistance</step>
    <step>get_price_patterns</step>
    <step>get_volume_analysis</step>
    <step>get_relative_performance</step>
    <step>Synthesize signals into directional bias + key levels + confluence + risk. Include TA disclaimer.</step>
  </subagent>

  <subagent name="Comparative" trigger="compare X vs Y, multi-company" tools="2xN">
    <step>For each ticker: get_income_statements, get_balance_sheets, get_cash_flow_statements, get_key_ratios_snapshot, get_key_ratios, get_analyst_estimates, get_company_facts</step>
    <step>Build comparison table with trends and relative strengths/weaknesses</step>
  </subagent>

  <subagent name="Filings" trigger="risk factors, MD&amp;A, SEC filing content" tools="2-3" context-saved="10-20k -> 1-2k">
    <step>get_filings -- discover filings, get accession numbers</step>
    <step>get_filing_items -- fetch section text</step>
    <step>Summarize key findings with specific quotes</step>
    <note>Always call get_filings first. Never guess accession numbers.</note>
  </subagent>

  <subagent name="Discovery" trigger="find stocks, screen for, breakouts" tools="5-20">
    <step>get_screening_strategies or screen_stocks</step>
    <step>For top 3-5: get_buy_sell_levels, get_price_snapshot, get_support_resistance, get_momentum_indicators, get_volume_analysis</step>
    <step>Cross-validate PKScreener levels with TA-derived S/R</step>
    <step>Ranked list: entry, stop-loss, target, pattern, signal strength. Include TA disclaimer.</step>
  </subagent>

  <subagent name="Browser" trigger="JS-rendered pages, interactive sites" tools="5-8">
    <step>browser_navigate -> browser_snapshot -> browser_act -> browser_snapshot -> browser_read -> browser_close</step>
    <note>Use WebFetch for static pages. Browser only for JS-rendered or interactive.</note>
  </subagent>

  <subagent name="Options" trigger="options flow/positioning, gamma exposure" tools="7-8">
    <step>get_options_expirations, get_options_chain, get_implied_volatility, get_put_call_ratio, get_options_flow, get_max_pain, get_gamma_exposure, get_price_snapshot</step>
    <step>Synthesize: directional bias from positioning, GEX levels, IV regime. Include TA disclaimer.</step>
  </subagent>

  <subagent name="Sentiment" trigger="sentiment, social buzz, mood" tools="4+">
    <step>get_news_sentiment, get_social_sentiment, get_insider_sentiment, get_fear_greed_index</step>
    <step>Weight sources, identify agreement/divergence, flag contrarian signals</step>
  </subagent>

  <subagent name="Macro" trigger="macro environment, market regime, rate impact" tools="5+">
    <step>get_treasury_yields, get_market_indices, get_commodity_prices, get_economic_calendar, get_intermarket_correlations</step>
    <step>Classify regime (risk-on/off, tightening/easing), dominant driver, upcoming catalysts</step>
  </subagent>

  <subagent name="Prediction" trigger="price prediction, forecast, probability of reaching" tools="15-20+" context-saved="15-25k -> 1-2k">
    <step>Current: get_price_snapshot, get_prices</step>
    <step>Quant: get_price_forecast, get_volatility_forecast, get_monte_carlo_simulation, get_return_distribution, get_mean_reversion, get_regime_detection</step>
    <step>Options: get_implied_volatility, get_options_flow, get_gamma_exposure</step>
    <step>TA: get_moving_averages, get_momentum_indicators, get_support_resistance</step>
    <step>Sentiment: get_news_sentiment, get_fear_greed_index</step>
    <step>Macro: get_treasury_yields, get_market_indices, get_intermarket_correlations</step>
    <step>Catalysts: get_analyst_estimates, get_earnings_calendar</step>
    <step>Synthesize: probability-weighted range + CI + key levels + risks + catalysts. Include prediction disclaimer.</step>
    <weights>1-Quant models, 2-Options positioning, 3-Technical levels, 4-Macro regime, 5-Sentiment, 6-Analyst consensus</weights>
    <note>ALWAYS delegate. Never run inline.</note>
  </subagent>

  <subagent name="Backtesting" trigger="backtest, win rate, test strategy" tools="3-5">
    <step>get_signal_backtest, get_strategy_simulation, get_risk_metrics, get_prediction_score</step>
    <step>Results: win rate, P&amp;L, Sharpe, max DD, vs buy-and-hold, stat significance, overfitting risk</step>
  </subagent>

  <prompt-pattern>
    Include in every sub-agent Task prompt:
    1. Specific research question
    2. Ticker(s) and parameters
    3. Expected output format (table, summary, ranked list)
    4. "Include specific numbers, not vague statements"
    5. "Include TA/prediction disclaimer if applicable"
    6. "Keep response concise -- presented to user directly"
  </prompt-pattern>
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
    └── utils/ (indicators.py, models.py, sentiment.py)
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
