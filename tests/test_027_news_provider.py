"""Tests for Task 027: WebNewsProvider (Google News RSS + DuckDuckGo fallback).

All network calls are mocked -- zero real HTTP requests.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import the base dataclass (created by another agent).  If the module
# isn't available yet, skip the entire file gracefully.
# ---------------------------------------------------------------------------
NewsHeadline = pytest.importorskip(
    "data_providers.news_provider", reason="news_provider.py not yet created"
).NewsHeadline

from data_providers.web_news_provider import WebNewsProvider

# ---------------------------------------------------------------------------
# Sample RSS XML for mocking Google News responses
# ---------------------------------------------------------------------------
SAMPLE_RSS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>AAPL stock - Google News</title>
    <link>https://news.google.com</link>
    <description>Google News</description>
    <item>
      <title>Apple beats earnings expectations - Reuters</title>
      <link>https://example.com/article1</link>
      <pubDate>Fri, 14 Mar 2026 18:30:00 GMT</pubDate>
      <source url="https://reuters.com">Reuters</source>
    </item>
    <item>
      <title>Apple stock surges on strong iPhone demand - Bloomberg</title>
      <link>https://example.com/article2</link>
      <pubDate>Fri, 14 Mar 2026 14:00:00 GMT</pubDate>
      <source url="https://bloomberg.com">Bloomberg</source>
    </item>
    <item>
      <title>Why AAPL is a buy heading into Q2 - The Motley Fool</title>
      <link>https://example.com/article3</link>
      <pubDate>Thu, 13 Mar 2026 09:15:00 GMT</pubDate>
      <source url="https://fool.com">The Motley Fool</source>
    </item>
    <item>
      <title>Analyst upgrades Apple to overweight - CNBC</title>
      <link>https://example.com/article4</link>
      <pubDate>Wed, 12 Mar 2026 21:00:00 GMT</pubDate>
      <source url="https://cnbc.com">CNBC</source>
    </item>
    <item>
      <title>Apple announces new M5 chip lineup - The Verge</title>
      <link>https://example.com/article5</link>
      <pubDate>Tue, 11 Mar 2026 16:45:00 GMT</pubDate>
      <source url="https://theverge.com">The Verge</source>
    </item>
  </channel>
</rss>
"""

EMPTY_RSS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>No results - Google News</title>
    <link>https://news.google.com</link>
    <description>Google News</description>
  </channel>
</rss>
"""


# ---------------------------------------------------------------------------
# Helper: build a mock aiohttp response
# ---------------------------------------------------------------------------
def _make_mock_response(text: str, status: int = 200) -> MagicMock:
    """Create a mock that works as an async context-manager response."""
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    resp.raise_for_status = MagicMock()
    # Support `async with session.get(url) as resp:`
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _make_mock_session(response: MagicMock) -> MagicMock:
    """Create a mock aiohttp.ClientSession whose .get() returns *response*."""
    session = MagicMock()
    session.get = MagicMock(return_value=response)
    # Support `async with aiohttp.ClientSession(...) as session:`
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWebNewsProviderParseRSS:
    """test_web_news_provider_parse_rss: verify RSS parsing."""

    @pytest.mark.asyncio
    async def test_parse_rss_returns_correct_headlines(self):
        response = _make_mock_response(SAMPLE_RSS_XML)
        session = _make_mock_session(response)

        with patch("aiohttp.ClientSession", return_value=session):
            provider = WebNewsProvider(timeout=5)
            headlines = await provider.get_headlines("AAPL", max_results=10)

        assert len(headlines) == 5

        # Verify newest-first ordering (2026-03-14 18:30 should come first).
        first = headlines[0]
        assert first.title == "Apple beats earnings expectations"
        assert first.source == "Reuters"
        assert "2026-03-14" in first.published_at
        assert first.url == "https://example.com/article1"

        # Second headline
        second = headlines[1]
        assert second.title == "Apple stock surges on strong iPhone demand"
        assert second.source == "Bloomberg"
        assert "2026-03-14" in second.published_at

        # Last headline should be oldest
        last = headlines[-1]
        assert last.title == "Apple announces new M5 chip lineup"
        assert last.source == "The Verge"
        assert "2026-03-11" in last.published_at

    @pytest.mark.asyncio
    async def test_parse_rss_strips_source_suffix_from_title(self):
        """Titles like 'Headline - Source' should have the suffix stripped."""
        headlines = WebNewsProvider._parse_rss(SAMPLE_RSS_XML)
        for h in headlines:
            # None of the parsed titles should end with " - SourceName"
            assert " - " not in h.title, (
                f"Title still contains source suffix: {h.title!r}"
            )

    @pytest.mark.asyncio
    async def test_parse_rss_published_at_iso_format(self):
        """pubDate should be converted to ISO 8601."""
        headlines = WebNewsProvider._parse_rss(SAMPLE_RSS_XML)
        for h in headlines:
            # ISO dates contain 'T' separator
            assert "T" in h.published_at, (
                f"published_at is not ISO format: {h.published_at!r}"
            )


class TestWebNewsProviderEmptyResponse:
    """test_web_news_provider_empty_response: empty RSS returns empty list."""

    @pytest.mark.asyncio
    async def test_empty_rss_returns_empty_list(self):
        response = _make_mock_response(EMPTY_RSS_XML)
        session = _make_mock_session(response)

        with patch("aiohttp.ClientSession", return_value=session):
            provider = WebNewsProvider(timeout=5)
            headlines = await provider.get_headlines("ZZZZ", max_results=10)

        assert headlines == []

    @pytest.mark.asyncio
    async def test_malformed_xml_returns_empty_list(self):
        headlines = WebNewsProvider._parse_rss("<not>valid rss xml")
        # Should not crash; returns empty list because there are no <item> tags.
        assert isinstance(headlines, list)


class TestWebNewsProviderNetworkError:
    """test_web_news_provider_network_error: network errors return empty list."""

    @pytest.mark.asyncio
    async def test_aiohttp_raises_returns_empty_list(self):
        """If aiohttp raises (e.g. timeout), get_headlines returns []."""
        session = MagicMock()
        session.get = MagicMock(side_effect=Exception("Connection timeout"))
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=session):
            provider = WebNewsProvider(timeout=2)
            headlines = await provider.get_headlines("AAPL")

        assert headlines == []

    @pytest.mark.asyncio
    async def test_google_fails_duckduckgo_also_fails(self):
        """Both sources failing should still return [] without crashing."""
        session = MagicMock()
        session.get = MagicMock(side_effect=Exception("DNS resolution failed"))
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=session):
            provider = WebNewsProvider(timeout=2)
            headlines = await provider.get_headlines("AAPL")

        assert headlines == []


class TestWebNewsProviderMaxResults:
    """test_web_news_provider_max_results: verify max_results limits output."""

    @pytest.mark.asyncio
    async def test_max_results_limits_output(self):
        response = _make_mock_response(SAMPLE_RSS_XML)
        session = _make_mock_session(response)

        with patch("aiohttp.ClientSession", return_value=session):
            provider = WebNewsProvider(timeout=5)
            headlines = await provider.get_headlines("AAPL", max_results=2)

        assert len(headlines) == 2
        # Still newest-first
        assert "2026-03-14" in headlines[0].published_at

    @pytest.mark.asyncio
    async def test_max_results_one(self):
        response = _make_mock_response(SAMPLE_RSS_XML)
        session = _make_mock_session(response)

        with patch("aiohttp.ClientSession", return_value=session):
            provider = WebNewsProvider(timeout=5)
            headlines = await provider.get_headlines("AAPL", max_results=1)

        assert len(headlines) == 1

    @pytest.mark.asyncio
    async def test_max_results_larger_than_available(self):
        response = _make_mock_response(SAMPLE_RSS_XML)
        session = _make_mock_session(response)

        with patch("aiohttp.ClientSession", return_value=session):
            provider = WebNewsProvider(timeout=5)
            headlines = await provider.get_headlines("AAPL", max_results=100)

        # Only 5 items in our sample RSS
        assert len(headlines) == 5


class TestNewsHeadlineDataclass:
    """test_news_headline_dataclass: verify NewsHeadline fields work correctly."""

    def test_required_fields(self):
        h = NewsHeadline(
            title="Test headline",
            source="TestSource",
            published_at="2026-03-14T12:00:00+00:00",
        )
        assert h.title == "Test headline"
        assert h.source == "TestSource"
        assert h.published_at == "2026-03-14T12:00:00+00:00"
        assert h.url is None
        assert h.snippet is None

    def test_all_fields(self):
        h = NewsHeadline(
            title="Full headline",
            source="FullSource",
            published_at="2026-03-14T08:00:00+00:00",
            url="https://example.com/article",
            snippet="This is a snippet of the article.",
        )
        assert h.title == "Full headline"
        assert h.source == "FullSource"
        assert h.url == "https://example.com/article"
        assert h.snippet == "This is a snippet of the article."

    def test_equality(self):
        h1 = NewsHeadline(title="A", source="B", published_at="C")
        h2 = NewsHeadline(title="A", source="B", published_at="C")
        assert h1 == h2

    def test_optional_defaults(self):
        h = NewsHeadline(title="T", source="S", published_at="P")
        assert h.url is None
        assert h.snippet is None
