# Zaza Task Index

## Summary

| Metric | Value |
|--------|-------|
| **Total Tasks** | 28 |
| **Small** | 7 (13-20h) |
| **Medium** | 14 (60-96h) |
| **Large** | 7 (66-100h) |
| **Estimated Total** | ~139-216 hours |
| **Status** | All PENDING |

---

## Phase 1: Core Infrastructure

Foundation tasks that everything else depends on.

| ID | Title | File | Complexity | Hours | Dependencies |
|----|-------|------|:----------:|:-----:|:------------:|
| TASK-001 | Project Scaffolding & Package Configuration | [TASK-001](TASK-001-project-scaffolding.md) | Small | 2-3h | None |
| TASK-002 | Configuration Module | [TASK-002](TASK-002-configuration-module.md) | Small | 1-2h | TASK-001 |
| TASK-003 | File-Based Cache System | [TASK-003](TASK-003-file-based-cache.md) | Small | 2-3h | TASK-001, TASK-002 |
| TASK-004 | yfinance API Client | [TASK-004](TASK-004-yfinance-client.md) | Medium | 4-6h | TASK-001, TASK-003 |
| TASK-005 | SEC EDGAR API Client | [TASK-005](TASK-005-edgar-client.md) | Medium | 4-6h | TASK-001, TASK-002, TASK-003 |
| TASK-006 | MCP Server Entry Point | [TASK-006](TASK-006-mcp-server-entry-point.md) | Small | 2-3h | TASK-001, TASK-002 |

**Phase 1 Total: ~15-23 hours**

---

## Phase 2: API Clients & Shared Utilities

Additional data source clients and reusable computation modules.

| ID | Title | File | Complexity | Hours | Dependencies |
|----|-------|------|:----------:|:-----:|:------------:|
| TASK-007 | Reddit & StockTwits API Clients | [TASK-007](TASK-007-social-api-clients.md) | Small | 3-4h | TASK-001, TASK-002, TASK-003 |
| TASK-008 | FRED API Client | [TASK-008](TASK-008-fred-client.md) | Small | 2-3h | TASK-001, TASK-002, TASK-003 |
| TASK-009 | Shared TA Computation Utilities | [TASK-009](TASK-009-ta-utilities.md) | Medium | 6-8h | TASK-001 |
| TASK-010 | Shared Quantitative Model Utilities | [TASK-010](TASK-010-quant-utilities.md) | Medium | 6-8h | TASK-001 |
| TASK-011 | Shared NLP/Sentiment Scoring Utilities | [TASK-011](TASK-011-sentiment-utilities.md) | Small | 3-4h | TASK-001 |

**Phase 2 Total: ~20-27 hours**

---

## Phase 3: Tool Implementation

All 66 MCP tools organized by domain.

| ID | Title | File | Tools | Complexity | Hours | Dependencies |
|----|-------|------|:-----:|:----------:|:-----:|:------------:|
| TASK-012 | Financial Tools — Prices & Company | [TASK-012](TASK-012-finance-prices-company.md) | 5 | Medium | 4-6h | TASK-001, TASK-003, TASK-004, TASK-006 |
| TASK-013 | Financial Tools — Statements & Ratios | [TASK-013](TASK-013-finance-statements-ratios.md) | 8 | Medium | 6-8h | TASK-001, TASK-003, TASK-004, TASK-005, TASK-006 |
| TASK-014 | Financial Tools — SEC Filings | [TASK-014](TASK-014-finance-filings.md) | 2 | Medium | 6-8h | TASK-001, TASK-003, TASK-005, TASK-006 |
| TASK-015 | Technical Analysis Tools | [TASK-015](TASK-015-ta-tools.md) | 9 | Large | 10-14h | TASK-001, TASK-003, TASK-004, TASK-006, TASK-009 |
| TASK-016 | Options & Derivatives Tools | [TASK-016](TASK-016-options-tools.md) | 7 | Large | 10-14h | TASK-001, TASK-003, TASK-004, TASK-006 |
| TASK-017 | Sentiment Analysis Tools | [TASK-017](TASK-017-sentiment-tools.md) | 4 | Medium | 6-8h | TASK-001, TASK-003, TASK-004, TASK-006, TASK-007, TASK-011 |
| TASK-018 | Macro & Cross-Asset Tools | [TASK-018](TASK-018-macro-tools.md) | 5 | Medium | 6-8h | TASK-001, TASK-003, TASK-004, TASK-006, TASK-008 |
| TASK-019 | Quantitative Model Tools | [TASK-019](TASK-019-quant-tools.md) | 6 | Large | 10-14h | TASK-001, TASK-003, TASK-004, TASK-006, TASK-010 |
| TASK-020 | Institutional Flow Tools | [TASK-020](TASK-020-institutional-tools.md) | 4 | Medium | 6-8h | TASK-001, TASK-003, TASK-004, TASK-005, TASK-006 |
| TASK-021 | Earnings & Events Tools | [TASK-021](TASK-021-earnings-tools.md) | 4 | Medium | 6-8h | TASK-001, TASK-003, TASK-004, TASK-005, TASK-006 |
| TASK-022 | Backtesting & Validation Tools | [TASK-022](TASK-022-backtesting-tools.md) | 4 | Large | 10-14h | TASK-001, TASK-003, TASK-004, TASK-006, TASK-009, TASK-010 |
| TASK-023 | PKScreener Docker & Screener Tools | [TASK-023](TASK-023-screener-tools.md) | 3 | Medium | 4-6h | TASK-001, TASK-006 |
| TASK-024 | Browser Automation Tools | [TASK-024](TASK-024-browser-tools.md) | 5 | Medium | 6-8h | TASK-001, TASK-006 |

**Phase 3 Total: 66 tools, ~85-126 hours**

---

## Phase 4: Integration & Production Readiness

Wiring, behavioral config, setup, and testing.

| ID | Title | File | Complexity | Hours | Dependencies |
|----|-------|------|:----------:|:-----:|:------------:|
| TASK-025 | MCP Server Tool Registration & Wiring | [TASK-025](TASK-025-server-tool-registration.md) | Medium | 4-6h | TASK-006, TASK-012–024 |
| TASK-026 | CLAUDE.md Behavioral Instructions | [TASK-026](TASK-026-claude-md-instructions.md) | Medium | 4-6h | TASK-012–024 |
| TASK-027 | Setup Script & Environment Config | [TASK-027](TASK-027-setup-script.md) | Small | 2-3h | TASK-001, TASK-006, TASK-025 |
| TASK-028 | Comprehensive Test Suite | [TASK-028](TASK-028-test-suite.md) | Large | 12-16h | TASK-001–024 |

**Phase 4 Total: ~22-31 hours**

---

## Dependency Graph

```
Phase 1 (sequential):
  TASK-001 → TASK-002 → TASK-003 → TASK-004, TASK-005
  TASK-001 → TASK-002 → TASK-006

Phase 2 (parallel after Phase 1):
  TASK-003 → TASK-007, TASK-008
  TASK-001 → TASK-009, TASK-010, TASK-011

Phase 3 (parallel after dependencies):
  TASK-004 + TASK-006 → TASK-012, TASK-013, TASK-016, TASK-018, TASK-020, TASK-021
  TASK-005 + TASK-006 → TASK-013, TASK-014, TASK-020, TASK-021
  TASK-009 + TASK-004 → TASK-015
  TASK-010 + TASK-004 → TASK-019, TASK-022
  TASK-007 + TASK-011 → TASK-017
  TASK-008 → TASK-018
  TASK-006 → TASK-023, TASK-024

Phase 4 (after all Phase 3):
  All Phase 3 → TASK-025 → TASK-027
  All Phase 3 → TASK-026
  All tools → TASK-028
```

## Recommended Implementation Order

**Sprint 1** (core foundation): TASK-001 → 002 → 003 → 004, 005, 006 (parallel)

**Sprint 2** (clients & utils, parallel): TASK-007, 008, 009, 010, 011

**Sprint 3** (financial + TA tools): TASK-012, 013, 014, 015

**Sprint 4** (options + sentiment + macro): TASK-016, 017, 018

**Sprint 5** (quant + institutional + earnings): TASK-019, 020, 021

**Sprint 6** (backtesting + screener + browser): TASK-022, 023, 024

**Sprint 7** (integration): TASK-025, 026, 027, 028
