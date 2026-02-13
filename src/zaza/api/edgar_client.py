"""Async HTTP client for SEC EDGAR APIs."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from zaza.cache.store import FileCache
from zaza.config import EDGAR_USER_AGENT

logger = structlog.get_logger(__name__)

BASE_URL = "https://data.sec.gov"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


class EdgarClient:
    """Async client for SEC EDGAR with rate limiting and caching.

    Provides access to SEC EDGAR APIs for company filings, XBRL facts,
    and ticker-to-CIK resolution. All responses are cached using FileCache
    with category-based TTL. HTTP requests are rate-limited to 10 concurrent
    requests via an asyncio semaphore and retried up to 3 times on transient
    failures.
    """

    def __init__(self, cache: FileCache) -> None:
        self.cache = cache
        self._semaphore = asyncio.Semaphore(10)  # 10 req/s rate limit
        self._ticker_map: dict[str, str] | None = None

    def _headers(self) -> dict[str, str]:
        """Return HTTP headers required by SEC EDGAR."""
        return {"User-Agent": EDGAR_USER_AGENT, "Accept": "application/json"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
    )
    async def _get(self, url: str) -> httpx.Response:
        """Rate-limited GET with retry.

        Acquires the semaphore before making the request to enforce
        the 10-concurrent-request rate limit. Retries up to 3 times
        with exponential backoff on HTTP errors and connection failures.
        """
        async with self._semaphore:
            async with httpx.AsyncClient(
                headers=self._headers(), timeout=30.0
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp

    async def ticker_to_cik(self, ticker: str) -> str:
        """Resolve ticker symbol to zero-padded 10-digit CIK.

        Downloads and caches the full SEC ticker-to-CIK mapping on first call.
        Subsequent calls use the in-memory map (and on-disk cache after restart).

        Args:
            ticker: Stock ticker symbol (case-insensitive).

        Returns:
            10-digit zero-padded CIK string.

        Raises:
            ValueError: If the ticker is not found in the SEC database.
        """
        if self._ticker_map is None:
            cache_key = self.cache.make_key("company_tickers")
            cached = self.cache.get(cache_key, "company_facts")
            if cached is not None:
                self._ticker_map = cached
            else:
                resp = await self._get(TICKERS_URL)
                data = resp.json()
                self._ticker_map = {
                    entry["ticker"].upper(): str(entry["cik_str"]).zfill(10)
                    for entry in data.values()
                }
                self.cache.set(cache_key, "company_facts", self._ticker_map)

        cik = self._ticker_map.get(ticker.upper())
        if not cik:
            raise ValueError(f"Ticker {ticker} not found in SEC database")
        return cik

    async def get_submissions(self, cik: str) -> dict[str, Any]:
        """Get filing metadata for a CIK.

        Returns the company's filing history including recent filings,
        entity information, and filing counts.

        Args:
            cik: Central Index Key (zero-padded to 10 digits internally).

        Returns:
            Filing metadata dict, or empty dict on error.
        """
        cik = cik.zfill(10)
        cache_key = self.cache.make_key("submissions", cik=cik)
        cached = self.cache.get(cache_key, "filings_meta")
        if cached is not None:
            return cached
        try:
            resp = await self._get(f"{BASE_URL}/submissions/CIK{cik}.json")
            data = resp.json()
            self.cache.set(cache_key, "filings_meta", data)
            return data
        except Exception as e:
            logger.warning("edgar_error", cik=cik, error=str(e))
            return {}

    async def get_company_facts(self, cik: str) -> dict[str, Any]:
        """Get XBRL company facts.

        Returns structured financial data extracted from the company's
        XBRL filings, organized by taxonomy and concept.

        Args:
            cik: Central Index Key (zero-padded to 10 digits internally).

        Returns:
            Company facts dict, or empty dict on error.
        """
        cik = cik.zfill(10)
        cache_key = self.cache.make_key("company_facts", cik=cik)
        cached = self.cache.get(cache_key, "company_facts")
        if cached is not None:
            return cached
        try:
            resp = await self._get(
                f"{BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"
            )
            data = resp.json()
            self.cache.set(cache_key, "company_facts", data)
            return data
        except Exception as e:
            logger.warning("edgar_error", cik=cik, error=str(e))
            return {}

    async def get_filing_content(self, cik: str, accession: str) -> str:
        """Get full filing text content.

        Fetches the filing index page for the given accession number.
        The CIK is stripped of leading zeros for the EDGAR archives URL.

        Args:
            cik: Central Index Key.
            accession: Accession number (e.g., '0000320193-24-000081').

        Returns:
            Filing HTML content as string, or empty string on error.
        """
        cik = cik.zfill(10).lstrip("0") or "0"
        # Convert accession: 0000320193-24-000081 -> 000032019324000081
        acc_clean = accession.replace("-", "")
        cache_key = self.cache.make_key(
            "filing_content", cik=cik, accession=accession
        )
        cached = self.cache.get(cache_key, "company_facts")
        if cached is not None:
            return cached.get("content", "")
        try:
            # Fetch the filing document index page
            index_url = (
                f"{ARCHIVES_URL}/{cik}/{acc_clean}/{accession}-index.htm"
            )
            resp = await self._get(index_url)
            # Cache the content wrapped in a dict for FileCache compatibility
            self.cache.set(
                cache_key, "company_facts", {"content": resp.text}
            )
            return resp.text
        except Exception as e:
            logger.warning(
                "edgar_filing_error",
                cik=cik,
                accession=accession,
                error=str(e),
            )
            return ""
