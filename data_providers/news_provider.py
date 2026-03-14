"""Abstract news provider interface for headline retrieval."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NewsHeadline:
    """A single news headline with metadata."""

    title: str
    source: str
    published_at: str
    url: str | None = None
    snippet: str | None = None


class NewsProvider(ABC):
    """Abstract base class for news data sources."""

    @abstractmethod
    async def get_headlines(
        self, ticker: str, max_results: int = 10
    ) -> list[NewsHeadline]:
        """Fetch recent news headlines for a given ticker.

        Args:
            ticker: Stock/crypto ticker symbol.
            max_results: Maximum number of headlines to return.

        Returns:
            List of NewsHeadline objects, most recent first.
        """
