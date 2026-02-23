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
  <verify>uv run python -m zaza.server --check</verify>
</commands>

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

<rtk-instructions>
  # RTK (Rust Token Killer) - Token-Optimized Commands

  ## Golden Rule

  **Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

  **Important**: Even in command chains with `&&`, use `rtk`:
  ```bash
  # ❌ Wrong
  git add . && git commit -m "msg" && git push

  # ✅ Correct
  rtk git add . && rtk git commit -m "msg" && rtk git push
  ```

  ## RTK Commands by Workflow

  ### Git
  ```bash
  rtk git status          # Compact status
  rtk git log             # Compact log (works with all git flags)
  rtk git diff            # Compact diff (80%)
  rtk git show            # Compact show (80%)
  rtk git add             # Ultra-compact confirmations (59%)
  rtk git commit          # Ultra-compact confirmations (59%)
  rtk git push            # Ultra-compact confirmations
  rtk git pull            # Ultra-compact confirmations
  rtk git branch          # Compact branch list
  rtk git fetch           # Compact fetch
  rtk git stash           # Compact stash
  rtk git worktree        # Compact worktree
  ```

  Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

  ### GitHub
  ```bash
  rtk gh pr view <num>    # Compact PR view (87%)
  rtk gh pr checks        # Compact PR checks (79%)
  rtk gh run list         # Compact workflow runs (82%)
  rtk gh issue list       # Compact issue list (80%)
  rtk gh api              # Compact API responses (26%)
  ```

  ### Files & Search
  ```bash
  rtk ls <path>           # Tree format, compact (65%)
  rtk read <file>         # Code reading with filtering (60%)
  rtk grep <pattern>      # Search grouped by file (75%)
  rtk find <pattern>      # Find grouped by directory (70%)
  ```

  ### Analysis & Debug
  ```bash
  rtk err <cmd>           # Filter errors only from any command
  rtk log <file>          # Deduplicated logs with counts
  rtk json <file>         # JSON structure without values
  rtk deps                # Dependency overview
  rtk env                 # Environment variables compact
  rtk summary <cmd>       # Smart summary of command output
  rtk diff                # Ultra-compact diffs
  ```

  ### Infrastructure
  ```bash
  rtk docker ps           # Compact container list
  rtk docker images       # Compact image list
  rtk docker logs <c>     # Deduplicated logs
  ```

  ### Python Tooling
  ```bash
  rtk uv sync             # Compact dependency sync output
  rtk uv sync --dev       # Works with all uv sync flags
  rtk uv run pytest       # Pytest failures only (90%)
  rtk uv run pytest -x    # Works with all pytest flags
  rtk uv run ruff check   # Ruff lint violations grouped (80%)
  rtk uv run ruff format  # Ruff format output compact (70%)
  rtk uv run uvicorn      # Compact server startup output
  rtk uv pip list         # Compact package list
  rtk uv pip install      # Compact install output
  ```

  ### Network
  ```bash
  rtk curl <url>          # Compact HTTP responses (70%)
  rtk wget <url>          # Compact download output (65%)
  ```

  ### Meta Commands
  ```bash
  rtk gain                # View token savings statistics
  rtk gain --history      # View command history with savings
  rtk discover            # Analyze Claude Code sessions for missed RTK usage
  rtk proxy <cmd>         # Run command without filtering (for debugging)
  rtk init                # Add RTK instructions to CLAUDE.md
  rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
  ```
</rtk-instructions>