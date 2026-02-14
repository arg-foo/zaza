"""Tests for sub-agent output format validation (TASK-037).

Validates that CLAUDE.md sub-agent templates specify proper output format
structures per the prompt-pattern requirements:

1. ROLE: "You are a financial research sub-agent with access to Zaza MCP tools."
2. TASK: Specific research question with ticker(s) and parameters
3. WORKFLOW: Numbered tool call sequence
4. SYNTHESIS: What to extract from results and how to combine signals
5. FORMAT: Exact output structure (table, summary, ranked list)
6. CONSTRAINTS: Specific numbers, concise response, no raw dumps, disclaimers
7. ERROR HANDLING: "If any tool fails, proceed with available data. Note gaps."

All tests are pure parsing/validation -- no external API calls needed.
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


def _extract_delegation_section(content: str) -> str:
    """Extract the <delegation> section from CLAUDE.md."""
    match = re.search(r"<delegation>(.*?)</delegation>", content, re.DOTALL)
    assert match, "Could not find <delegation> section in CLAUDE.md"
    return match.group(1)


def _extract_prompt_pattern(delegation_section: str) -> str:
    """Extract the <prompt-pattern> block from the delegation section."""
    match = re.search(
        r"<prompt-pattern>(.*?)</prompt-pattern>", delegation_section, re.DOTALL
    )
    assert match, "Could not find <prompt-pattern> in delegation section"
    return match.group(1)


def _extract_subagent_templates(delegation_section: str) -> dict[str, str]:
    """Extract individual sub-agent template blocks.

    Returns a dict mapping sub-agent name to its full <subagent> block.
    """
    templates: dict[str, str] = {}
    pattern = r'<subagent\s+name="(\w+)"[^>]*>(.*?)</subagent>'
    for match in re.finditer(pattern, delegation_section, re.DOTALL):
        name = match.group(1)
        body = match.group(2)
        templates[name] = body
    return templates


def _extract_template_text(subagent_block: str) -> str:
    """Extract just the <template> content from a sub-agent block."""
    match = re.search(r"<template>(.*?)</template>", subagent_block, re.DOTALL)
    if match:
        return match.group(1)
    return subagent_block


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def claude_md_content() -> str:
    """Load CLAUDE.md content once per module."""
    return _read_claude_md()


@pytest.fixture(scope="module")
def delegation_section(claude_md_content: str) -> str:
    """Extract <delegation> section."""
    return _extract_delegation_section(claude_md_content)


@pytest.fixture(scope="module")
def prompt_pattern(delegation_section: str) -> str:
    """Extract <prompt-pattern> block."""
    return _extract_prompt_pattern(delegation_section)


@pytest.fixture(scope="module")
def subagent_templates(delegation_section: str) -> dict[str, str]:
    """Map of sub-agent name to full subagent block."""
    return _extract_subagent_templates(delegation_section)


@pytest.fixture(scope="module")
def template_texts(subagent_templates: dict[str, str]) -> dict[str, str]:
    """Map of sub-agent name to just the template text."""
    return {
        name: _extract_template_text(block)
        for name, block in subagent_templates.items()
    }


# ---------------------------------------------------------------------------
# Tests: Prompt pattern specification exists
# ---------------------------------------------------------------------------


class TestPromptPatternSpec:
    """Verify the prompt-pattern section defines all required elements."""

    def test_prompt_pattern_exists(self, prompt_pattern: str) -> None:
        """The prompt-pattern section exists in the delegation block."""
        assert len(prompt_pattern.strip()) > 0

    def test_prompt_pattern_requires_role(self, prompt_pattern: str) -> None:
        """Prompt pattern specifies a ROLE requirement."""
        assert re.search(r"ROLE", prompt_pattern, re.IGNORECASE), (
            "Prompt pattern should require a ROLE element"
        )

    def test_prompt_pattern_requires_task(self, prompt_pattern: str) -> None:
        """Prompt pattern specifies a TASK requirement."""
        assert re.search(r"TASK", prompt_pattern, re.IGNORECASE), (
            "Prompt pattern should require a TASK element"
        )

    def test_prompt_pattern_requires_workflow(self, prompt_pattern: str) -> None:
        """Prompt pattern specifies a WORKFLOW requirement."""
        assert re.search(r"WORKFLOW", prompt_pattern, re.IGNORECASE), (
            "Prompt pattern should require a WORKFLOW element"
        )

    def test_prompt_pattern_requires_synthesis(self, prompt_pattern: str) -> None:
        """Prompt pattern specifies a SYNTHESIS requirement."""
        assert re.search(r"SYNTHESIS", prompt_pattern, re.IGNORECASE), (
            "Prompt pattern should require a SYNTHESIS element"
        )

    def test_prompt_pattern_requires_format(self, prompt_pattern: str) -> None:
        """Prompt pattern specifies a FORMAT requirement."""
        assert re.search(r"FORMAT", prompt_pattern, re.IGNORECASE), (
            "Prompt pattern should require a FORMAT element"
        )

    def test_prompt_pattern_requires_constraints(self, prompt_pattern: str) -> None:
        """Prompt pattern specifies a CONSTRAINTS requirement."""
        assert re.search(r"CONSTRAINTS", prompt_pattern, re.IGNORECASE), (
            "Prompt pattern should require a CONSTRAINTS element"
        )

    def test_prompt_pattern_requires_error_handling(
        self, prompt_pattern: str
    ) -> None:
        """Prompt pattern specifies an ERROR HANDLING requirement."""
        assert re.search(r"ERROR.HANDLING", prompt_pattern, re.IGNORECASE), (
            "Prompt pattern should require an ERROR HANDLING element"
        )


# ---------------------------------------------------------------------------
# Tests: Each template has required sections (Role, Task, Workflow, etc.)
# ---------------------------------------------------------------------------


class TestTemplateRequiredSections:
    """Verify each sub-agent template contains all required sections."""

    @pytest.mark.parametrize("subagent_name", EXPECTED_SUBAGENTS)
    def test_template_has_role(
        self,
        subagent_name: str,
        template_texts: dict[str, str],
    ) -> None:
        """Each template starts with the role statement."""
        text = template_texts.get(subagent_name, "")
        if not text:
            pytest.skip(f"Sub-agent '{subagent_name}' not found")

        assert re.search(
            r"(financial research sub-agent|sub-agent.*MCP tools)",
            text,
            re.IGNORECASE,
        ), (
            f"Sub-agent '{subagent_name}' template missing role statement "
            f"('You are a financial research sub-agent with access to Zaza MCP tools')"
        )

    @pytest.mark.parametrize("subagent_name", EXPECTED_SUBAGENTS)
    def test_template_has_task(
        self,
        subagent_name: str,
        template_texts: dict[str, str],
    ) -> None:
        """Each template defines a Task section."""
        text = template_texts.get(subagent_name, "")
        if not text:
            pytest.skip(f"Sub-agent '{subagent_name}' not found")

        assert re.search(r"\*\*Task\*\*", text), (
            f"Sub-agent '{subagent_name}' template missing **Task** section"
        )

    @pytest.mark.parametrize("subagent_name", EXPECTED_SUBAGENTS)
    def test_template_has_workflow(
        self,
        subagent_name: str,
        template_texts: dict[str, str],
    ) -> None:
        """Each template defines a Workflow section."""
        text = template_texts.get(subagent_name, "")
        if not text:
            pytest.skip(f"Sub-agent '{subagent_name}' not found")

        assert re.search(r"\*\*Workflow\*\*", text), (
            f"Sub-agent '{subagent_name}' template missing **Workflow** section"
        )

    @pytest.mark.parametrize("subagent_name", EXPECTED_SUBAGENTS)
    def test_template_has_synthesis_or_critical(
        self,
        subagent_name: str,
        template_texts: dict[str, str],
    ) -> None:
        """Each template defines a Synthesis or critical instruction section."""
        text = template_texts.get(subagent_name, "")
        if not text:
            pytest.skip(f"Sub-agent '{subagent_name}' not found")

        # Some templates use Synthesis, some use CRITICAL for special instructions
        has_synthesis = bool(re.search(r"\*\*Synthesis\*\*", text))
        has_critical = bool(re.search(r"\*\*CRITICAL\*\*", text))
        assert has_synthesis or has_critical, (
            f"Sub-agent '{subagent_name}' template missing **Synthesis** or "
            f"**CRITICAL** section"
        )

    @pytest.mark.parametrize("subagent_name", EXPECTED_SUBAGENTS)
    def test_template_has_output_format(
        self,
        subagent_name: str,
        template_texts: dict[str, str],
    ) -> None:
        """Each template defines an Output Format section."""
        text = template_texts.get(subagent_name, "")
        if not text:
            pytest.skip(f"Sub-agent '{subagent_name}' not found")

        assert re.search(r"\*\*Output Format\*\*", text), (
            f"Sub-agent '{subagent_name}' template missing **Output Format** section"
        )

    @pytest.mark.parametrize("subagent_name", EXPECTED_SUBAGENTS)
    def test_template_has_error_handling(
        self,
        subagent_name: str,
        template_texts: dict[str, str],
        subagent_templates: dict[str, str],
    ) -> None:
        """Each template includes error handling or graceful degradation instructions.

        Checks both the <template> text and the full <subagent> block, since
        some sub-agents place error handling guidance outside the template
        (e.g., in the delegation-level <error-handling> section that applies
        to all sub-agents).
        """
        text = template_texts.get(subagent_name, "")
        block = subagent_templates.get(subagent_name, "")
        combined = text + "\n" + block
        if not text:
            pytest.skip(f"Sub-agent '{subagent_name}' not found")

        # Check for error/failure handling patterns including graceful degradation
        # and conditional execution (skip if not applicable)
        error_patterns = [
            r"if.*tool.*fail",
            r"if.*fail",
            r"unable to",
            r"fail.*proceed",
            r"note.*gap",
            r"missing",
            r"unavailable",
            r"returns 0 results",
            r"proceed with",
            r"error",
            r"NEVER.*guess",
            r"N/A",
            r"fill with",
            r"skip if",
            r"if.*provided",
        ]
        has_error_handling = any(
            re.search(pattern, combined, re.IGNORECASE)
            for pattern in error_patterns
        )
        assert has_error_handling, (
            f"Sub-agent '{subagent_name}' template missing error handling, "
            f"graceful degradation, or conditional execution instructions"
        )


# ---------------------------------------------------------------------------
# Tests: Disclaimer requirements
# ---------------------------------------------------------------------------


class TestDisclaimerPresence:
    """Verify disclaimers are present where required."""

    @pytest.mark.parametrize(
        "subagent_name", sorted(SUBAGENTS_REQUIRING_DISCLAIMER)
    )
    def test_disclaimer_present(
        self,
        subagent_name: str,
        template_texts: dict[str, str],
    ) -> None:
        """Sub-agents requiring disclaimers include one in their template."""
        text = template_texts.get(subagent_name, "")
        if not text:
            pytest.skip(f"Sub-agent '{subagent_name}' not found")

        disclaimer_patterns = [
            r"not financial advice",
            r"not.*certainties",
            r"historical patterns",
            r"not guaranteed",
            r"backtest results.*do not",
            r"backtest results.*!=",
            r"probabilistic estimates",
            r"screening reflects",
            r"always verify",
        ]
        has_disclaimer = any(
            re.search(pattern, text, re.IGNORECASE)
            for pattern in disclaimer_patterns
        )
        assert has_disclaimer, (
            f"Sub-agent '{subagent_name}' MUST include a disclaimer but none found. "
            f"Expected patterns: 'Not financial advice', 'not guaranteed', etc."
        )

    def test_no_disclaimer_not_required_for_sentiment(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Sentiment sub-agent does not strictly require a disclaimer.

        This test confirms that our disclaimer requirement list is correct
        and does not inadvertently require disclaimers from sub-agents that
        don't need them.
        """
        assert "Sentiment" not in SUBAGENTS_REQUIRING_DISCLAIMER

    def test_no_disclaimer_not_required_for_macro(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Macro sub-agent does not strictly require a disclaimer."""
        assert "Macro" not in SUBAGENTS_REQUIRING_DISCLAIMER

    def test_no_disclaimer_not_required_for_comparative(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Comparative sub-agent does not strictly require a disclaimer."""
        assert "Comparative" not in SUBAGENTS_REQUIRING_DISCLAIMER


# ---------------------------------------------------------------------------
# Tests: Output format structure validation
# ---------------------------------------------------------------------------


class TestOutputFormatStructure:
    """Verify output format sections contain proper structure elements."""

    @pytest.mark.parametrize("subagent_name", EXPECTED_SUBAGENTS)
    def test_output_format_has_structure(
        self,
        subagent_name: str,
        template_texts: dict[str, str],
    ) -> None:
        """Each output format includes structural elements (table, list, or heading)."""
        text = template_texts.get(subagent_name, "")
        if not text:
            pytest.skip(f"Sub-agent '{subagent_name}' not found")

        # Look for markdown table (|), bullet points (*/-), or headings (**)
        has_table = bool(re.search(r"\|.*\|.*\|", text))
        has_bullets = bool(re.search(r"^[\s]*[-*]\s", text, re.MULTILINE))
        has_headings = bool(re.search(r"\*\*\w+", text))

        assert has_table or has_bullets or has_headings, (
            f"Sub-agent '{subagent_name}' output format lacks structural "
            f"elements (tables, bullet points, or headings)"
        )

    def test_ta_has_signal_table(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """TA sub-agent output format includes a signal summary table."""
        text = template_texts.get("TA", "")
        assert re.search(r"\|\s*Signal\s*\|", text), (
            "TA template should include a signal summary table with '| Signal |' header"
        )

    def test_comparative_has_comparison_table(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Comparative sub-agent output format includes a comparison table."""
        text = template_texts.get("Comparative", "")
        assert re.search(r"\|\s*Metric\s*\|", text), (
            "Comparative template should include a comparison table "
            "with '| Metric |' header"
        )

    def test_prediction_has_scenario_table(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Prediction sub-agent output format includes a scenario table."""
        text = template_texts.get("Prediction", "")
        assert re.search(r"\|\s*Scenario\s*\|", text), (
            "Prediction template should include a scenario table "
            "with '| Scenario |' header"
        )

    def test_discovery_has_ranked_table(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Discovery sub-agent output format includes a ranked results table."""
        text = template_texts.get("Discovery", "")
        assert re.search(r"\|\s*#\s*\|.*Ticker", text), (
            "Discovery template should include a ranked table with '| # | Ticker |' "
            "header"
        )

    def test_options_has_metric_table(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Options sub-agent output format includes a metrics table."""
        text = template_texts.get("Options", "")
        assert re.search(r"\|\s*Metric\s*\|", text), (
            "Options template should include a metrics table "
            "with '| Metric |' header"
        )

    def test_sentiment_has_source_table(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Sentiment sub-agent output format includes a source table."""
        text = template_texts.get("Sentiment", "")
        assert re.search(r"\|\s*Source\s*\|", text), (
            "Sentiment template should include a source table "
            "with '| Source |' header"
        )

    def test_macro_has_factor_table(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Macro sub-agent output format includes a factor table."""
        text = template_texts.get("Macro", "")
        assert re.search(r"\|\s*Factor\s*\|", text), (
            "Macro template should include a factor table "
            "with '| Factor |' header"
        )

    def test_backtesting_has_metric_table(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Backtesting sub-agent output format includes a metrics table."""
        text = template_texts.get("Backtesting", "")
        assert re.search(r"\|\s*Metric\s*\|", text), (
            "Backtesting template should include a metrics table "
            "with '| Metric |' header"
        )


# ---------------------------------------------------------------------------
# Tests: Workflow structure validation
# ---------------------------------------------------------------------------


class TestWorkflowStructure:
    """Verify workflow sections have numbered steps and tool calls."""

    @pytest.mark.parametrize("subagent_name", EXPECTED_SUBAGENTS)
    def test_workflow_has_numbered_steps(
        self,
        subagent_name: str,
        template_texts: dict[str, str],
    ) -> None:
        """Each workflow section contains numbered steps."""
        text = template_texts.get(subagent_name, "")
        if not text:
            pytest.skip(f"Sub-agent '{subagent_name}' not found")

        # Look for numbered list items (1. 2. 3. etc.)
        numbered_steps = re.findall(r"^\s*\d+\.\s", text, re.MULTILINE)
        assert len(numbered_steps) >= 1, (
            f"Sub-agent '{subagent_name}' workflow should have numbered steps"
        )

    @pytest.mark.parametrize("subagent_name", EXPECTED_SUBAGENTS)
    def test_workflow_references_tools(
        self,
        subagent_name: str,
        template_texts: dict[str, str],
    ) -> None:
        """Each workflow section references tool calls."""
        text = template_texts.get(subagent_name, "")
        if not text:
            pytest.skip(f"Sub-agent '{subagent_name}' not found")

        tool_pattern = r"\b(get_\w+|screen_stocks|browser_\w+)\b"
        tools_found = re.findall(tool_pattern, text)
        assert len(tools_found) > 0, (
            f"Sub-agent '{subagent_name}' workflow should reference tool calls"
        )


# ---------------------------------------------------------------------------
# Tests: Concurrency and sequencing guidance
# ---------------------------------------------------------------------------


class TestConcurrencyGuidance:
    """Verify templates that need sequential execution specify it."""

    def test_filings_specifies_sequential(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Filings sub-agent must specify sequential execution."""
        text = template_texts.get("Filings", "")
        has_sequential = bool(
            re.search(r"SEQUENTIAL|sequential|step.*1.*step.*2", text, re.IGNORECASE)
        )
        has_accession_warning = bool(
            re.search(r"NEVER.*guess.*accession|accession.*first", text, re.IGNORECASE)
        )
        assert has_sequential or has_accession_warning, (
            "Filings template must specify sequential execution (get_filings before "
            "get_filing_items) or warn against guessing accession numbers"
        )

    def test_discovery_specifies_sequential(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Discovery sub-agent must specify sequential execution."""
        text = template_texts.get("Discovery", "")
        has_sequential = bool(
            re.search(r"sequential|screen.*first|from.*results", text, re.IGNORECASE)
        )
        assert has_sequential, (
            "Discovery template must specify sequential execution "
            "(screen first, then analyze)"
        )

    def test_browser_specifies_sequential(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Browser sub-agent must specify sequential execution."""
        text = template_texts.get("Browser", "")
        has_sequential = bool(
            re.search(r"sequential|ALWAYS.*close|step.*depends", text, re.IGNORECASE)
        )
        assert has_sequential, (
            "Browser template must specify sequential execution "
            "(navigate -> snapshot -> act -> read -> close)"
        )

    def test_ta_allows_parallel(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """TA sub-agent should allow parallel tool calls."""
        text = template_texts.get("TA", "")
        has_parallel = bool(
            re.search(r"parallel|all tools", text, re.IGNORECASE)
        )
        assert has_parallel, (
            "TA template should specify that tools can be called in parallel"
        )

    def test_prediction_allows_parallel_categories(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Prediction sub-agent should specify parallel execution where possible."""
        text = template_texts.get("Prediction", "")
        has_parallel = bool(
            re.search(r"parallel", text, re.IGNORECASE)
        )
        assert has_parallel, (
            "Prediction template should specify parallel execution for "
            "independent tool categories"
        )


# ---------------------------------------------------------------------------
# Tests: Delegation section structural elements
# ---------------------------------------------------------------------------


class TestDelegationStructure:
    """Verify the delegation section has all required structural elements."""

    def test_decision_matrix_exists(self, delegation_section: str) -> None:
        """The delegation section includes a decision matrix."""
        assert re.search(r"<decision-matrix>", delegation_section), (
            "Delegation section should include a <decision-matrix>"
        )

    def test_context_budgets_exist(self, delegation_section: str) -> None:
        """The delegation section includes context budget estimates."""
        assert re.search(r"<context-budgets>", delegation_section), (
            "Delegation section should include <context-budgets>"
        )

    def test_error_handling_section_exists(self, delegation_section: str) -> None:
        """The delegation section includes error handling rules."""
        assert re.search(r"<error-handling>", delegation_section), (
            "Delegation section should include <error-handling>"
        )

    def test_concurrency_section_exists(self, delegation_section: str) -> None:
        """The delegation section includes concurrency guidance."""
        assert re.search(r"<concurrency>", delegation_section), (
            "Delegation section should include <concurrency>"
        )

    def test_fallback_rules_exist(self, delegation_section: str) -> None:
        """The delegation section includes fallback rules."""
        assert re.search(r"<fallback-rules>", delegation_section), (
            "Delegation section should include <fallback-rules>"
        )

    def test_each_subagent_has_triggers(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """Each sub-agent block includes trigger examples."""
        for name, block in subagent_templates.items():
            has_triggers = bool(re.search(r"<triggers>", block))
            assert has_triggers, (
                f"Sub-agent '{name}' should include <triggers> section"
            )

    def test_each_subagent_has_use_and_skip(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """Each sub-agent trigger section includes use and skip examples."""
        for name, block in subagent_templates.items():
            has_use = bool(re.search(r"<use>", block))
            has_skip = bool(re.search(r"<skip>", block))
            assert has_use, (
                f"Sub-agent '{name}' triggers should include <use> examples"
            )
            assert has_skip, (
                f"Sub-agent '{name}' triggers should include <skip> examples"
            )


# ---------------------------------------------------------------------------
# Tests: Context budget validation
# ---------------------------------------------------------------------------


class TestContextBudgets:
    """Verify context budget specifications."""

    def test_all_subagents_have_budget(
        self,
        delegation_section: str,
    ) -> None:
        """Each sub-agent is listed in the context-budgets table."""
        budgets_match = re.search(
            r"<context-budgets>(.*?)</context-budgets>",
            delegation_section,
            re.DOTALL,
        )
        assert budgets_match, "context-budgets section not found"
        budgets_text = budgets_match.group(1)

        for name in EXPECTED_SUBAGENTS:
            assert re.search(
                rf"\b{name}\b", budgets_text
            ), (
                f"Sub-agent '{name}' missing from context-budgets table"
            )

    def test_budget_attr_on_subagent_tags(
        self,
        subagent_templates: dict[str, str],
        delegation_section: str,
    ) -> None:
        """Each sub-agent tag has a budget attribute."""
        for name in EXPECTED_SUBAGENTS:
            pattern = rf'<subagent\s+name="{name}"[^>]*budget='
            assert re.search(pattern, delegation_section), (
                f"Sub-agent '{name}' tag should have a budget= attribute"
            )


# ---------------------------------------------------------------------------
# Tests: Prediction sub-agent specific requirements
# ---------------------------------------------------------------------------


class TestPredictionSubagentSpecific:
    """Verify Prediction sub-agent has unique required elements."""

    def test_prediction_has_signal_weights(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Prediction template includes signal weighting hierarchy."""
        text = template_texts.get("Prediction", "")
        assert re.search(r"(weight|hierarchy)", text, re.IGNORECASE), (
            "Prediction template should include signal weighting hierarchy"
        )

    def test_prediction_has_confidence_interval(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Prediction template mentions confidence intervals."""
        text = template_texts.get("Prediction", "")
        has_ci = bool(
            re.search(r"(confidence|CI|percentile|probability)", text, re.IGNORECASE)
        )
        assert has_ci, (
            "Prediction template should mention confidence intervals or percentiles"
        )

    def test_prediction_has_logging_instruction(
        self,
        template_texts: dict[str, str],
    ) -> None:
        """Prediction template includes prediction logging instruction."""
        text = template_texts.get("Prediction", "")
        has_logging = bool(
            re.search(r"(log.*prediction|prediction.*log|JSON.*file)", text, re.IGNORECASE)
        )
        assert has_logging, (
            "Prediction template should instruct logging the prediction for "
            "future accuracy tracking"
        )

    def test_prediction_never_inline(
        self,
        subagent_templates: dict[str, str],
    ) -> None:
        """Prediction sub-agent is marked as ALWAYS delegated, never inline."""
        block = subagent_templates.get("Prediction", "")
        has_always_delegate = bool(
            re.search(r"ALWAYS.*delegate|NEVER.*inline|never.*skip", block, re.IGNORECASE)
        )
        assert has_always_delegate, (
            "Prediction sub-agent should be marked as ALWAYS delegated"
        )
