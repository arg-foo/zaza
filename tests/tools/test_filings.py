"""Tests for SEC filings MCP tools (TASK-014)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zaza.cache.store import FileCache


@pytest.fixture
def cache(tmp_path):
    return FileCache(cache_dir=tmp_path)


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

SAMPLE_SUBMISSIONS = {
    "cik": "0000320193",
    "entityType": "operating",
    "name": "Apple Inc.",
    "tickers": ["AAPL"],
    "recentFilings": {
        "accessionNumber": [
            "0000320193-24-000081",
            "0000320193-24-000070",
            "0000320193-24-000060",
        ],
        "filingDate": ["2024-11-01", "2024-08-02", "2024-05-03"],
        "form": ["10-K", "10-Q", "10-Q"],
        "primaryDocument": ["aapl-20240928.htm", "aapl-20240629.htm", "aapl-20240330.htm"],
    },
}


SAMPLE_FILING_HTML = """
<html><body>
<h2>Item 1. Business</h2>
<p>Apple Inc. designs, manufactures, and markets smartphones, personal computers,
tablets, wearables, and accessories worldwide.</p>
<h2>Item 1A. Risk Factors</h2>
<p>The Company's operations and performance depend significantly on worldwide economic
conditions and their impact on levels of consumer spending.</p>
<h2>Item 7. Management's Discussion and Analysis</h2>
<p>The following discussion should be read in conjunction with the Company's consolidated
financial statements and accompanying notes.</p>
</body></html>
"""


def _capture_tools_with_mock_edgar(mock_edgar):
    """Register filings tools with a mocked EdgarClient, returning tool functions."""
    mcp = MagicMock()
    tool_funcs = {}

    def capture_tool():
        def decorator(func):
            tool_funcs[func.__name__] = func
            return func
        return decorator

    mcp.tool = capture_tool

    with patch("zaza.tools.finance.filings.EdgarClient", return_value=mock_edgar):
        with patch("zaza.tools.finance.filings.FileCache"):
            from zaza.tools.finance.filings import register
            register(mcp)

    return tool_funcs


# ---------------------------------------------------------------------------
# get_filings tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_filings_returns_metadata(cache):
    """get_filings returns filing metadata with accession numbers, dates, and types."""
    mock_edgar = AsyncMock()
    mock_edgar.ticker_to_cik.return_value = "0000320193"
    mock_edgar.get_submissions.return_value = SAMPLE_SUBMISSIONS

    tools = _capture_tools_with_mock_edgar(mock_edgar)
    result_str = await tools["get_filings"]("AAPL")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    assert result["ticker"] == "AAPL"
    assert len(result["data"]["filings"]) == 3
    assert result["data"]["filings"][0]["accession_number"] == "0000320193-24-000081"
    assert result["data"]["filings"][0]["form"] == "10-K"


@pytest.mark.asyncio
async def test_get_filings_filters_by_type(cache):
    """get_filings filters filings by filing_type when provided."""
    mock_edgar = AsyncMock()
    mock_edgar.ticker_to_cik.return_value = "0000320193"
    mock_edgar.get_submissions.return_value = SAMPLE_SUBMISSIONS

    tools = _capture_tools_with_mock_edgar(mock_edgar)
    result_str = await tools["get_filings"]("AAPL", filing_type="10-K")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    assert len(result["data"]["filings"]) == 1
    assert result["data"]["filings"][0]["form"] == "10-K"


@pytest.mark.asyncio
async def test_get_filings_respects_limit(cache):
    """get_filings respects the limit parameter."""
    mock_edgar = AsyncMock()
    mock_edgar.ticker_to_cik.return_value = "0000320193"
    mock_edgar.get_submissions.return_value = SAMPLE_SUBMISSIONS

    tools = _capture_tools_with_mock_edgar(mock_edgar)
    result_str = await tools["get_filings"]("AAPL", limit=2)
    result = json.loads(result_str)

    assert result["status"] == "ok"
    assert len(result["data"]["filings"]) == 2


@pytest.mark.asyncio
async def test_get_filings_error_handling(cache):
    """get_filings returns error dict when EdgarClient raises."""
    mock_edgar = AsyncMock()
    mock_edgar.ticker_to_cik.side_effect = ValueError("Ticker INVALID not found")

    tools = _capture_tools_with_mock_edgar(mock_edgar)
    result_str = await tools["get_filings"]("INVALID")
    result = json.loads(result_str)

    assert "error" in result


@pytest.mark.asyncio
async def test_get_filings_empty_submissions(cache):
    """get_filings handles empty submissions gracefully."""
    mock_edgar = AsyncMock()
    mock_edgar.ticker_to_cik.return_value = "0000320193"
    mock_edgar.get_submissions.return_value = {}

    tools = _capture_tools_with_mock_edgar(mock_edgar)
    result_str = await tools["get_filings"]("AAPL")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    assert len(result["data"]["filings"]) == 0


# ---------------------------------------------------------------------------
# get_filing_items tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_filing_items_with_accession(cache):
    """get_filing_items returns parsed sections for a given accession number."""
    mock_edgar = AsyncMock()
    mock_edgar.ticker_to_cik.return_value = "0000320193"
    mock_edgar.get_filing_content.return_value = SAMPLE_FILING_HTML

    tools = _capture_tools_with_mock_edgar(mock_edgar)
    result_str = await tools["get_filing_items"](
        "AAPL", "10-K", accession_number="0000320193-24-000081"
    )
    result = json.loads(result_str)

    assert result["status"] == "ok"
    assert "items" in result["data"]
    assert len(result["data"]["items"]) > 0


@pytest.mark.asyncio
async def test_get_filing_items_self_healing(cache):
    """get_filing_items resolves accession_number from submissions when not provided."""
    mock_edgar = AsyncMock()
    mock_edgar.ticker_to_cik.return_value = "0000320193"
    mock_edgar.get_submissions.return_value = SAMPLE_SUBMISSIONS
    mock_edgar.get_filing_content.return_value = SAMPLE_FILING_HTML

    tools = _capture_tools_with_mock_edgar(mock_edgar)
    result_str = await tools["get_filing_items"]("AAPL", "10-K")
    result = json.loads(result_str)

    assert result["status"] == "ok"
    # Should have called get_submissions to resolve the accession number
    mock_edgar.get_submissions.assert_called_once()
    # The resolved accession should be the first 10-K in the list
    mock_edgar.get_filing_content.assert_called_once_with(
        "0000320193", "0000320193-24-000081"
    )


@pytest.mark.asyncio
async def test_get_filing_items_self_healing_no_match(cache):
    """get_filing_items returns error when self-healing cannot find matching filing type."""
    mock_edgar = AsyncMock()
    mock_edgar.ticker_to_cik.return_value = "0000320193"
    mock_edgar.get_submissions.return_value = SAMPLE_SUBMISSIONS

    tools = _capture_tools_with_mock_edgar(mock_edgar)
    result_str = await tools["get_filing_items"]("AAPL", "8-K")
    result = json.loads(result_str)

    assert "error" in result


@pytest.mark.asyncio
async def test_get_filing_items_filters_items(cache):
    """get_filing_items filters to specific items when items parameter is provided."""
    mock_edgar = AsyncMock()
    mock_edgar.ticker_to_cik.return_value = "0000320193"
    mock_edgar.get_filing_content.return_value = SAMPLE_FILING_HTML

    tools = _capture_tools_with_mock_edgar(mock_edgar)
    result_str = await tools["get_filing_items"](
        "AAPL", "10-K",
        accession_number="0000320193-24-000081",
        items=["Item 1A"],
    )
    result = json.loads(result_str)

    assert result["status"] == "ok"
    # Only "Item 1A" should be present
    item_names = [item["item"] for item in result["data"]["items"]]
    for name in item_names:
        assert "1A" in name or "1a" in name.lower()


@pytest.mark.asyncio
async def test_get_filing_items_error_handling(cache):
    """get_filing_items returns error dict on exception."""
    mock_edgar = AsyncMock()
    mock_edgar.ticker_to_cik.side_effect = ValueError("Ticker INVALID not found")

    tools = _capture_tools_with_mock_edgar(mock_edgar)
    result_str = await tools["get_filing_items"]("INVALID", "10-K")
    result = json.loads(result_str)

    assert "error" in result
