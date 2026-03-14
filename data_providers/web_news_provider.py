"""Web-based news provider using Google News RSS and DuckDuckGo fallback."""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import aiohttp

from data_providers.news_provider import NewsHeadline, NewsProvider

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search"
    "?q={query}+stock&hl=en-US&gl=US&ceid=US:en"
)

_DUCKDUCKGO_HTML = "https://html.duckduckgo.com/html/?q={query}+stock+news"

# Google News titles often end with " - SourceName".  We strip that suffix
# and use it as the source field.
_TITLE_SOURCE_RE = re.compile(r"^(.*?)\s+-\s+(\S.*)$")


class WebNewsProvider(NewsProvider):
    """Fetch headlines from free web sources (no API key required).

    Primary:  Google News RSS feed.
    Fallback: DuckDuckGo HTML search results.
    """

    def __init__(self, timeout: int = 10) -> None:
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_headlines(
        self, ticker: str, max_results: int = 10
    ) -> list[NewsHeadline]:
        """Return up to *max_results* headlines, newest first."""
        headlines = await self._fetch_google_news(ticker)
        if not headlines:
            logger.info(
                "Google News returned no results for %s; trying DuckDuckGo",
                ticker,
            )
            headlines = await self._fetch_duckduckgo(ticker)

        # Sort newest-first (ISO strings sort lexicographically).
        headlines.sort(key=lambda h: h.published_at, reverse=True)
        return headlines[:max_results]

    # ------------------------------------------------------------------
    # Google News RSS
    # ------------------------------------------------------------------

    async def _fetch_google_news(self, ticker: str) -> list[NewsHeadline]:
        url = _GOOGLE_NEWS_RSS.format(query=ticker)
        try:
            text = await self._http_get(url)
        except Exception:
            logger.warning("Google News request failed for %s", ticker, exc_info=True)
            return []
        return self._parse_rss(text)

    @staticmethod
    def _parse_rss(xml_text: str) -> list[NewsHeadline]:
        """Parse a Google News RSS feed into NewsHeadline objects."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.warning("Failed to parse RSS XML")
            return []

        headlines: list[NewsHeadline] = []
        for item in root.iter("item"):
            raw_title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip() or None
            pub_date_str = (item.findtext("pubDate") or "").strip()
            source_el = item.find("source")
            source_from_tag = (
                source_el.text.strip() if source_el is not None and source_el.text else ""
            )

            # Strip "[Source] - " suffix from title and extract source.
            title = raw_title
            source = source_from_tag
            match = _TITLE_SOURCE_RE.match(raw_title)
            if match:
                title = match.group(1).strip()
                if not source:
                    source = match.group(2).strip()

            # Parse RFC-2822 date -> ISO 8601
            published_at = ""
            if pub_date_str:
                try:
                    dt = parsedate_to_datetime(pub_date_str)
                    published_at = dt.isoformat()
                except Exception:
                    published_at = pub_date_str

            if not title:
                continue

            headlines.append(
                NewsHeadline(
                    title=title,
                    source=source or "Unknown",
                    published_at=published_at,
                    url=link,
                    snippet=None,
                )
            )
        return headlines

    # ------------------------------------------------------------------
    # DuckDuckGo HTML fallback
    # ------------------------------------------------------------------

    async def _fetch_duckduckgo(self, ticker: str) -> list[NewsHeadline]:
        url = _DUCKDUCKGO_HTML.format(query=ticker)
        try:
            html = await self._http_get(url)
        except Exception:
            logger.warning(
                "DuckDuckGo request failed for %s", ticker, exc_info=True
            )
            return []
        return self._parse_duckduckgo_html(html)

    @staticmethod
    def _parse_duckduckgo_html(html: str) -> list[NewsHeadline]:
        """Extract headlines from DuckDuckGo HTML search results."""
        headlines: list[NewsHeadline] = []
        # DuckDuckGo result links have class "result__a".
        link_pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        snippet_pattern = re.compile(
            r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            re.DOTALL,
        )

        links = link_pattern.findall(html)
        snippets = snippet_pattern.findall(html)

        for idx, (href, raw_title) in enumerate(links):
            title = re.sub(r"<[^>]+>", "", raw_title).strip()
            snippet = ""
            if idx < len(snippets):
                snippet = re.sub(r"<[^>]+>", "", snippets[idx]).strip()

            if not title:
                continue

            headlines.append(
                NewsHeadline(
                    title=title,
                    source="DuckDuckGo",
                    published_at="",
                    url=href or None,
                    snippet=snippet or None,
                )
            )
        return headlines

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    async def _http_get(self, url: str) -> str:
        """Perform a GET request and return the response body as text."""
        headers = {"User-Agent": _USER_AGENT}
        async with aiohttp.ClientSession(
            timeout=self._timeout, headers=headers
        ) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                return await resp.text()
