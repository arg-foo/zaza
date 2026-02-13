"""Tests for the SEC EDGAR API client."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx
from tenacity import wait_none

from zaza.api.edgar_client import ARCHIVES_URL, BASE_URL, TICKERS_URL, EdgarClient
from zaza.cache.store import FileCache


@pytest.fixture
def cache(tmp_path):
    """Create a temporary FileCache for test isolation."""
    return FileCache(cache_dir=tmp_path)


@pytest.fixture
def client(cache):
    """Create an EdgarClient with a temporary cache."""
    return EdgarClient(cache)


# ---------------------------------------------------------------------------
# ticker_to_cik
# ---------------------------------------------------------------------------


@respx.mock
async def test_ticker_to_cik_resolves_correctly(client):
    """ticker_to_cik returns a zero-padded 10-digit CIK for a known ticker."""
    respx.get(TICKERS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
                "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
            },
        )
    )
    cik = await client.ticker_to_cik("AAPL")
    assert cik == "0000320193"


@respx.mock
async def test_ticker_to_cik_raises_for_unknown_ticker(client):
    """ticker_to_cik raises ValueError for a ticker not in the SEC database."""
    respx.get(TICKERS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
            },
        )
    )
    with pytest.raises(ValueError, match="not found"):
        await client.ticker_to_cik("INVALID")


@respx.mock
async def test_ticker_to_cik_is_case_insensitive(client):
    """ticker_to_cik resolves lowercase ticker input."""
    respx.get(TICKERS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
            },
        )
    )
    cik = await client.ticker_to_cik("aapl")
    assert cik == "0000320193"


@respx.mock
async def test_ticker_to_cik_caches_ticker_map(client):
    """ticker_to_cik fetches the ticker map only once, then uses cache."""
    route = respx.get(TICKERS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
                "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
            },
        )
    )
    await client.ticker_to_cik("AAPL")
    await client.ticker_to_cik("MSFT")
    # Only one HTTP call because the map is cached in memory
    assert route.call_count == 1


@respx.mock
async def test_ticker_to_cik_uses_disk_cache(cache):
    """A new EdgarClient instance uses the disk-cached ticker map."""
    route = respx.get(TICKERS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
            },
        )
    )
    # First client populates disk cache
    client1 = EdgarClient(cache)
    await client1.ticker_to_cik("AAPL")
    assert route.call_count == 1

    # Second client should read from disk cache, not HTTP
    client2 = EdgarClient(cache)
    cik = await client2.ticker_to_cik("AAPL")
    assert cik == "0000320193"
    assert route.call_count == 1


# ---------------------------------------------------------------------------
# get_submissions
# ---------------------------------------------------------------------------


@respx.mock
async def test_get_submissions_returns_data(client):
    """get_submissions returns filing metadata for a valid CIK."""
    respx.get(f"{BASE_URL}/submissions/CIK0000320193.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "cik": "0000320193",
                "entityType": "operating",
                "name": "Apple Inc.",
                "recentFilings": {
                    "accessionNumber": ["0000320193-24-000081"]
                },
            },
        )
    )
    data = await client.get_submissions("320193")
    assert data["name"] == "Apple Inc."
    assert data["cik"] == "0000320193"


@respx.mock
async def test_get_submissions_zero_pads_cik(client):
    """get_submissions zero-pads short CIK values to 10 digits."""
    route = respx.get(f"{BASE_URL}/submissions/CIK0000000001.json").mock(
        return_value=httpx.Response(200, json={"name": "Test Corp"})
    )
    data = await client.get_submissions("1")
    assert route.called
    assert data["name"] == "Test Corp"


@respx.mock
async def test_get_submissions_caches_response(client):
    """get_submissions returns cached data on subsequent calls."""
    route = respx.get(f"{BASE_URL}/submissions/CIK0000320193.json").mock(
        return_value=httpx.Response(200, json={"name": "Apple Inc."})
    )
    await client.get_submissions("320193")
    await client.get_submissions("320193")
    assert route.call_count == 1


@respx.mock
async def test_get_submissions_returns_empty_on_error(client):
    """get_submissions returns empty dict on HTTP error after retries."""
    respx.get(f"{BASE_URL}/submissions/CIK0000000001.json").mock(
        return_value=httpx.Response(404)
    )
    # Patch retry wait to zero so the test does not sleep
    with patch.object(client._get.retry, "wait", wait_none()):
        data = await client.get_submissions("1")
    assert data == {}


# ---------------------------------------------------------------------------
# get_company_facts
# ---------------------------------------------------------------------------


@respx.mock
async def test_get_company_facts_returns_data(client):
    """get_company_facts returns XBRL facts for a valid CIK."""
    respx.get(f"{BASE_URL}/api/xbrl/companyfacts/CIK0000320193.json").mock(
        return_value=httpx.Response(
            200, json={"entityName": "APPLE INC", "facts": {"us-gaap": {}}}
        )
    )
    data = await client.get_company_facts("320193")
    assert data["entityName"] == "APPLE INC"
    assert "facts" in data


@respx.mock
async def test_get_company_facts_caches_response(client):
    """get_company_facts returns cached data on subsequent calls."""
    route = respx.get(
        f"{BASE_URL}/api/xbrl/companyfacts/CIK0000320193.json"
    ).mock(
        return_value=httpx.Response(
            200, json={"entityName": "APPLE INC", "facts": {}}
        )
    )
    await client.get_company_facts("320193")
    await client.get_company_facts("320193")
    assert route.call_count == 1


@respx.mock
async def test_get_company_facts_returns_empty_on_error(client):
    """get_company_facts returns empty dict on HTTP error."""
    respx.get(f"{BASE_URL}/api/xbrl/companyfacts/CIK0000000099.json").mock(
        return_value=httpx.Response(500)
    )
    with patch.object(client._get.retry, "wait", wait_none()):
        data = await client.get_company_facts("99")
    assert data == {}


# ---------------------------------------------------------------------------
# get_filing_content
# ---------------------------------------------------------------------------


@respx.mock
async def test_get_filing_content_returns_html(client):
    """get_filing_content fetches and returns filing HTML content."""
    cik = "320193"
    accession = "0000320193-24-000081"
    # CIK is stripped of leading zeros: "320193"
    # Accession cleaned: "000032019324000081"
    expected_url = (
        f"{ARCHIVES_URL}/320193/000032019324000081/"
        f"{accession}-index.htm"
    )
    respx.get(expected_url).mock(
        return_value=httpx.Response(200, text="<html>Filing content</html>")
    )
    content = await client.get_filing_content(cik, accession)
    assert content == "<html>Filing content</html>"


@respx.mock
async def test_get_filing_content_caches_response(client):
    """get_filing_content returns cached content on subsequent calls."""
    cik = "320193"
    accession = "0000320193-24-000081"
    expected_url = (
        f"{ARCHIVES_URL}/320193/000032019324000081/"
        f"{accession}-index.htm"
    )
    route = respx.get(expected_url).mock(
        return_value=httpx.Response(200, text="<html>Cached</html>")
    )
    await client.get_filing_content(cik, accession)
    content = await client.get_filing_content(cik, accession)
    assert content == "<html>Cached</html>"
    assert route.call_count == 1


@respx.mock
async def test_get_filing_content_returns_empty_on_error(client):
    """get_filing_content returns empty string on HTTP error."""
    cik = "320193"
    accession = "0000320193-24-000099"
    expected_url = (
        f"{ARCHIVES_URL}/320193/000032019324000099/"
        f"{accession}-index.htm"
    )
    respx.get(expected_url).mock(return_value=httpx.Response(404))
    with patch.object(client._get.retry, "wait", wait_none()):
        content = await client.get_filing_content(cik, accession)
    assert content == ""


@respx.mock
async def test_get_filing_content_handles_cik_zero_padding(client):
    """get_filing_content strips leading zeros from CIK for the URL path."""
    cik = "0000000042"
    accession = "0000000042-24-000001"
    # lstrip("0") on "0000000042" -> "42"
    expected_url = (
        f"{ARCHIVES_URL}/42/000000004224000001/"
        f"{accession}-index.htm"
    )
    respx.get(expected_url).mock(
        return_value=httpx.Response(200, text="<html>Small CIK</html>")
    )
    content = await client.get_filing_content(cik, accession)
    assert content == "<html>Small CIK</html>"


# ---------------------------------------------------------------------------
# _get retry behavior
# ---------------------------------------------------------------------------


@respx.mock
async def test_get_retries_on_transient_error(client):
    """_get retries on HTTPStatusError and succeeds on a subsequent attempt."""
    route = respx.get(f"{BASE_URL}/submissions/CIK0000320193.json").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"name": "Apple Inc."}),
        ]
    )
    with patch.object(client._get.retry, "wait", wait_none()):
        data = await client.get_submissions("320193")
    assert data["name"] == "Apple Inc."
    assert route.call_count == 2


# ---------------------------------------------------------------------------
# _headers
# ---------------------------------------------------------------------------


def test_headers_include_user_agent(client):
    """_headers returns the configured EDGAR User-Agent."""
    headers = client._headers()
    assert "User-Agent" in headers
    assert "Zaza" in headers["User-Agent"]
    assert headers["Accept"] == "application/json"
