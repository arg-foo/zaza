"""Tests for sub-agent tool name consistency (TASK-037).

Cross-references tool names referenced in agent files (.claude/agents/*.md)
against actual MCP tool registrations in the server. Verifies:
- Every tool name in CLAUDE.md tools section exists in the server registry
- No typos or mismatches between agent file references and actual tool names
- All 10 sub-agent files reference only valid tool names
- The tools section in CLAUDE.md is consistent with the registered tools

All external dependencies are mocked (no live calls).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLAUDE_MD_PATH = PROJECT_ROOT / "CLAUDE.md"
AGENTS_DIR = PROJECT_ROOT / ".claude" / "agents"
TOOLS_DIR = PROJECT_ROOT / "src" / "zaza" / "tools"

# The 10 financial sub-agents defined as .claude/agents/*.md files
# Maps display name (used in tests) to filename stem
EXPECTED_SUBAGENTS = [
    "TA",
    "Comparative",
    "Filings",
    "Discovery",
    "Browser",
    "Options",
    "Sentiment",
    "Macro",
    "Prediction",
    "Backtesting",
]

# Map from display name to agent file stem
SUBAGENT_FILE_MAP: dict[str, str] = {
    "TA": "ta",
    "Comparative": "comparative",
    "Filings": "filings",
    "Discovery": "discovery",
    "Browser": "browser",
    "Options": "options",
    "Sentiment": "sentiment",
    "Macro": "macro",
    "Prediction": "prediction",
    "Backtesting": "backtesting",
}

# Sub-agents that MUST include a disclaimer in their template
SUBAGENTS_REQUIRING_DISCLAIMER = {
    "TA",
    "Options",
    "Prediction",
    "Backtesting",
    "Discovery",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_claude_md() -> str:
    """Read CLAUDE.md content."""
    return CLAUDE_MD_PATH.read_text(encoding="utf-8")


def _extract_tools_section(content: str) -> str:
    """Extract the <tools> section from CLAUDE.md."""
    match = re.search(r"<tools>(.*?)</tools>", content, re.DOTALL)
    assert match, "Could not find <tools> section in CLAUDE.md"
    return match.group(1)


def _extract_tool_names_from_tools_section(tools_section: str) -> set[str]:
    """Extract all tool names from <tool name="..." /> entries."""
    return set(re.findall(r'<tool\s+name="(\w+)"', tools_section))


def _read_agent_file(stem: str) -> str:
    """Read an agent .md file and return its body (after YAML frontmatter)."""
    agent_path = AGENTS_DIR / f"{stem}.md"
    if not agent_path.exists():
        return ""
    content = agent_path.read_text(encoding="utf-8")
    # Strip YAML frontmatter (between --- markers)
    match = re.match(r"^---\s*\n.*?\n---\s*\n(.*)", content, re.DOTALL)
    if match:
        return match.group(1)
    return content


def _extract_subagent_templates() -> dict[str, str]:
    """Read all 10 agent .md files and return a dict mapping display name to body text."""
    templates: dict[str, str] = {}
    for display_name, file_stem in SUBAGENT_FILE_MAP.items():
        body = _read_agent_file(file_stem)
        if body:
            templates[display_name] = body
    return templates


def _extract_tool_names_from_template(template: str) -> set[str]:
    """Extract tool names from a single sub-agent template."""
    tool_pattern = r"\b(get_\w+|screen_stocks|browser_\w+|get_screening_strategies|get_buy_sell_levels)\b"
    raw_names = set(re.findall(tool_pattern, template))
    non_tool_patterns = {"get_history", "get_quote"}
    return raw_names - non_tool_patterns


def _extract_all_agent_tool_names() -> set[str]:
    """Extract all tool names referenced across all agent files."""
    all_tools: set[str] = set()
    for display_name, file_stem in SUBAGENT_FILE_MAP.items():
        body = _read_agent_file(file_stem)
        if body:
            all_tools |= _extract_tool_names_from_template(body)
    return all_tools


def _extract_registered_tool_names_from_source() -> set[str]:
    """Extract actual tool names from source code using @mcp.tool() decorator pattern.

    Scans all .py files under src/zaza/tools/ for functions decorated with
    @mcp.tool(), extracting the function name that follows the decorator.
    """
    tool_names: set[str] = set()
    for py_file in TOOLS_DIR.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        # Pattern: @mcp.tool() followed by async def function_name(
        pattern = r"@mcp\.tool\(\)\s+async\s+def\s+(\w+)\s*\("
        for match in re.finditer(pattern, content):
            tool_names.add(match.group(1))
    return tool_names


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def claude_md_content() -> str:
    """Load CLAUDE.md content once per module."""
    return _read_claude_md()


@pytest.fixture(scope="module")
def tools_section(claude_md_content: str) -> str:
    """Extract <tools> section."""
    return _extract_tools_section(claude_md_content)


@pytest.fixture(scope="module")
def claude_md_tool_names(tools_section: str) -> set[str]:
    """All tool names declared in <tools> section."""
    return _extract_tool_names_from_tools_section(tools_section)


@pytest.fixture(scope="module")
def subagent_templates() -> dict[str, str]:
    """Map of sub-agent display name to template body text from .claude/agents/*.md."""
    return _extract_subagent_templates()


@pytest.fixture(scope="module")
def agent_tool_names() -> set[str]:
    """All tool names referenced across all agent files."""
    return _extract_all_agent_tool_names()


@pytest.fixture(scope="module")
def registered_tool_names() -> set[str]:
    """Actual tool names from source code @mcp.tool() decorators."""
    return _extract_registered_tool_names_from_source()


# ---------------------------------------------------------------------------
# Tests: Tool name consistency between CLAUDE.md and source code
# ---------------------------------------------------------------------------


class TestToolNameConsistency:
    """Verify tool names in CLAUDE.md match actual MCP tool registrations."""

    def test_all_tools_section_names_are_registered(
        self,
        claude_md_tool_names: set[str],
        registered_tool_names: set[str],
    ) -> None:
        """Every tool in CLAUDE.md <tools> section exists in source code."""
        missing = claude_md_tool_names - registered_tool_names
        assert not missing, (
            f"Tools declared in CLAUDE.md <tools> section but NOT found in source code: "
            f"{sorted(missing)}"
        )

    def test_all_registered_tools_documented(
        self,
        claude_md_tool_names: set[str],
        registered_tool_names: set[str],
    ) -> None:
        """Every registered tool appears in CLAUDE.md <tools> section."""
        undocumented = registered_tool_names - claude_md_tool_names
        assert not undocumented, (
            f"Tools registered in source code but NOT documented in CLAUDE.md <tools>: "
            f"{sorted(undocumented)}"
        )

    def test_agent_tool_names_are_registered(
        self,
        agent_tool_names: set[str],
        registered_tool_names: set[str],
    ) -> None:
        """Every tool referenced in agent files exists in source code."""
        missing = agent_tool_names - registered_tool_names
        assert not missing, (
            f"Tools referenced in agent files but NOT registered in source: "
            f"{sorted(missing)}"
        )

    def test_agent_tool_names_in_tools_section(
        self,
        agent_tool_names: set[str],
        claude_md_tool_names: set[str],
    ) -> None:
        """Every tool referenced in agent files also appears in <tools> section."""
        missing = agent_tool_names - claude_md_tool_names
        assert not missing, (
            f"Tools referenced in agent files but NOT in <tools> section: "
            f"{sorted(missing)}"
        )


# ---------------------------------------------------------------------------
# Tests: All 10 sub-agent files reference valid tools
# ---------------------------------------------------------------------------


class TestSubagentTemplateToolNames:
    """Verify each sub-agent template references only valid tool names."""

    def test_all_expected_subagents_present(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """All 10 expected sub-agents have agent files in .claude/agents/."""
        for name in EXPECTED_SUBAGENTS:
            assert name in subagent_templates, (
                f"Sub-agent '{name}' not found in .claude/agents/ "
                f"(expected file: {SUBAGENT_FILE_MAP[name]}.md)"
            )

    def test_subagent_count(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """Exactly 10 sub-agents are defined."""
        assert len(subagent_templates) == 10, (
            f"Expected 10 sub-agents, found {len(subagent_templates)}: "
            f"{sorted(subagent_templates.keys())}"
        )

    @pytest.mark.parametrize("subagent_name", EXPECTED_SUBAGENTS)
    def test_subagent_tools_are_valid(
        self,
        subagent_name: str,
        subagent_templates: dict[str, str],
        registered_tool_names: set[str],
    ) -> None:
        """Each sub-agent references only registered tool names."""
        template = subagent_templates.get(subagent_name, "")
        if not template:
            pytest.skip(f"Sub-agent '{subagent_name}' not found")

        template_tools = _extract_tool_names_from_template(template)
        invalid = template_tools - registered_tool_names
        assert not invalid, (
            f"Sub-agent '{subagent_name}' references unregistered tools: "
            f"{sorted(invalid)}"
        )

    @pytest.mark.parametrize("subagent_name", EXPECTED_SUBAGENTS)
    def test_subagent_has_tools(
        self,
        subagent_name: str,
        subagent_templates: dict[str, str],
    ) -> None:
        """Each sub-agent template references at least one tool."""
        template = subagent_templates.get(subagent_name, "")
        if not template:
            pytest.skip(f"Sub-agent '{subagent_name}' not found")

        template_tools = _extract_tool_names_from_template(template)
        assert len(template_tools) > 0, (
            f"Sub-agent '{subagent_name}' references zero tools"
        )


# ---------------------------------------------------------------------------
# Tests: Specific sub-agent tool expectations
# ---------------------------------------------------------------------------


class TestSubagentSpecificTools:
    """Verify specific sub-agents reference their expected tools."""

    def test_ta_subagent_has_10_tools(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """TA sub-agent should reference 10 specific tools."""
        expected = {
            "get_price_snapshot",
            "get_moving_averages",
            "get_trend_strength",
            "get_momentum_indicators",
            "get_money_flow",
            "get_volatility_indicators",
            "get_support_resistance",
            "get_price_patterns",
            "get_volume_analysis",
            "get_relative_performance",
        }
        template = subagent_templates["TA"]
        actual = _extract_tool_names_from_template(template)
        missing = expected - actual
        assert not missing, f"TA sub-agent missing tools: {sorted(missing)}"

    def test_comparative_subagent_tools(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """Comparative sub-agent should reference fundamental analysis tools."""
        expected = {
            "get_company_facts",
            "get_income_statements",
            "get_balance_sheets",
            "get_cash_flow_statements",
            "get_key_ratios_snapshot",
            "get_key_ratios",
            "get_analyst_estimates",
        }
        template = subagent_templates["Comparative"]
        actual = _extract_tool_names_from_template(template)
        missing = expected - actual
        assert not missing, f"Comparative sub-agent missing tools: {sorted(missing)}"

    def test_filings_subagent_tools(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """Filings sub-agent must reference get_filings and get_filing_items."""
        expected = {"get_filings", "get_filing_items"}
        template = subagent_templates["Filings"]
        actual = _extract_tool_names_from_template(template)
        missing = expected - actual
        assert not missing, f"Filings sub-agent missing tools: {sorted(missing)}"

    def test_options_subagent_tools(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """Options sub-agent should reference all options tools plus price snapshot."""
        expected = {
            "get_price_snapshot",
            "get_options_expirations",
            "get_implied_volatility",
            "get_put_call_ratio",
            "get_options_flow",
            "get_max_pain",
            "get_gamma_exposure",
            "get_options_chain",
        }
        template = subagent_templates["Options"]
        actual = _extract_tool_names_from_template(template)
        missing = expected - actual
        assert not missing, f"Options sub-agent missing tools: {sorted(missing)}"

    def test_sentiment_subagent_tools(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """Sentiment sub-agent should reference all 4 sentiment tools."""
        expected = {
            "get_news_sentiment",
            "get_social_sentiment",
            "get_insider_sentiment",
            "get_fear_greed_index",
        }
        template = subagent_templates["Sentiment"]
        actual = _extract_tool_names_from_template(template)
        missing = expected - actual
        assert not missing, f"Sentiment sub-agent missing tools: {sorted(missing)}"

    def test_macro_subagent_tools(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """Macro sub-agent should reference all 5 macro tools."""
        expected = {
            "get_treasury_yields",
            "get_market_indices",
            "get_commodity_prices",
            "get_economic_calendar",
            "get_intermarket_correlations",
        }
        template = subagent_templates["Macro"]
        actual = _extract_tool_names_from_template(template)
        missing = expected - actual
        assert not missing, f"Macro sub-agent missing tools: {sorted(missing)}"

    def test_prediction_subagent_tools(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """Prediction sub-agent should reference tools from multiple categories."""
        expected = {
            # Current state
            "get_price_snapshot",
            "get_prices",
            # Quant
            "get_price_forecast",
            "get_volatility_forecast",
            "get_monte_carlo_simulation",
            "get_return_distribution",
            "get_mean_reversion",
            "get_regime_detection",
            # Options
            "get_implied_volatility",
            "get_options_flow",
            "get_gamma_exposure",
            # TA
            "get_moving_averages",
            "get_momentum_indicators",
            "get_support_resistance",
            # Sentiment
            "get_news_sentiment",
            "get_fear_greed_index",
            # Macro
            "get_treasury_yields",
            "get_market_indices",
            "get_intermarket_correlations",
            # Catalysts
            "get_analyst_estimates",
            "get_earnings_calendar",
        }
        template = subagent_templates["Prediction"]
        actual = _extract_tool_names_from_template(template)
        missing = expected - actual
        assert not missing, f"Prediction sub-agent missing tools: {sorted(missing)}"

    def test_backtesting_subagent_tools(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """Backtesting sub-agent should reference backtest-related tools."""
        expected = {
            "get_signal_backtest",
            "get_strategy_simulation",
            "get_risk_metrics",
            "get_prediction_score",
        }
        template = subagent_templates["Backtesting"]
        actual = _extract_tool_names_from_template(template)
        missing = expected - actual
        assert not missing, f"Backtesting sub-agent missing tools: {sorted(missing)}"

    def test_discovery_subagent_tools(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """Discovery sub-agent should reference screener and analysis tools."""
        expected = {
            "screen_stocks",
            "get_buy_sell_levels",
            "get_price_snapshot",
            "get_support_resistance",
            "get_momentum_indicators",
            "get_volume_analysis",
        }
        template = subagent_templates["Discovery"]
        actual = _extract_tool_names_from_template(template)
        missing = expected - actual
        assert not missing, f"Discovery sub-agent missing tools: {sorted(missing)}"

    def test_browser_subagent_tools(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """Browser sub-agent should reference all browser tools."""
        expected = {
            "browser_navigate",
            "browser_snapshot",
            "browser_act",
            "browser_read",
            "browser_close",
        }
        template = subagent_templates["Browser"]
        actual = _extract_tool_names_from_template(template)
        missing = expected - actual
        assert not missing, f"Browser sub-agent missing tools: {sorted(missing)}"


# ---------------------------------------------------------------------------
# Tests: Tool count validation
# ---------------------------------------------------------------------------


class TestToolCounts:
    """Verify tool counts match expectations."""

    def test_registered_tool_count(
        self,
        registered_tool_names: set[str],
    ) -> None:
        """Total registered tools should match the expected count (66)."""
        assert len(registered_tool_names) == 66, (
            f"Expected 66 registered tools, found {len(registered_tool_names)}: "
            f"{sorted(registered_tool_names)}"
        )

    def test_tools_section_count(
        self,
        claude_md_tool_names: set[str],
    ) -> None:
        """CLAUDE.md <tools> section should list all 66 tools."""
        assert len(claude_md_tool_names) == 66, (
            f"Expected 66 tools in <tools> section, found {len(claude_md_tool_names)}: "
            f"{sorted(claude_md_tool_names)}"
        )

    def test_finance_domain_count(
        self,
        claude_md_tool_names: set[str],
    ) -> None:
        """Finance domain should have 15 tools."""
        finance_tools = {
            "get_price_snapshot",
            "get_prices",
            "get_key_ratios_snapshot",
            "get_income_statements",
            "get_balance_sheets",
            "get_cash_flow_statements",
            "get_all_financial_statements",
            "get_key_ratios",
            "get_analyst_estimates",
            "get_company_news",
            "get_insider_trades",
            "get_segmented_revenues",
            "get_company_facts",
            "get_filings",
            "get_filing_items",
        }
        missing = finance_tools - claude_md_tool_names
        assert not missing, f"Finance tools missing from CLAUDE.md: {sorted(missing)}"
        assert len(finance_tools) == 15

    def test_ta_domain_count(
        self,
        claude_md_tool_names: set[str],
    ) -> None:
        """TA domain should have 9 tools."""
        ta_tools = {
            "get_moving_averages",
            "get_trend_strength",
            "get_momentum_indicators",
            "get_money_flow",
            "get_volatility_indicators",
            "get_support_resistance",
            "get_price_patterns",
            "get_volume_analysis",
            "get_relative_performance",
        }
        missing = ta_tools - claude_md_tool_names
        assert not missing, f"TA tools missing from CLAUDE.md: {sorted(missing)}"
        assert len(ta_tools) == 9

    def test_options_domain_count(
        self,
        claude_md_tool_names: set[str],
    ) -> None:
        """Options domain should have 7 tools."""
        options_tools = {
            "get_options_expirations",
            "get_options_chain",
            "get_implied_volatility",
            "get_options_flow",
            "get_put_call_ratio",
            "get_max_pain",
            "get_gamma_exposure",
        }
        missing = options_tools - claude_md_tool_names
        assert not missing, f"Options tools missing from CLAUDE.md: {sorted(missing)}"
        assert len(options_tools) == 7

    def test_browser_domain_count(
        self,
        claude_md_tool_names: set[str],
    ) -> None:
        """Browser domain should have 5 tools."""
        browser_tools = {
            "browser_navigate",
            "browser_snapshot",
            "browser_act",
            "browser_read",
            "browser_close",
        }
        missing = browser_tools - claude_md_tool_names
        assert not missing, f"Browser tools missing from CLAUDE.md: {sorted(missing)}"
        assert len(browser_tools) == 5
