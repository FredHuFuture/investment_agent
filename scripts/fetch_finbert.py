#!/usr/bin/env python
"""Pre-download the FinBERT model so the first SentimentAgent.analyze call is fast.

Run this once after ``pip install -e .[llm-local]``::

    python scripts/fetch_finbert.py

The model (~400 MB) will be cached in the default HuggingFace cache directory:
- macOS/Linux: ``~/.cache/huggingface/hub/models--ProsusAI--finbert``
- Windows:     ``%USERPROFILE%\\.cache\\huggingface\\hub\\models--ProsusAI--finbert``

If ``[llm-local]`` is not installed, SentimentAgent still works via Anthropic
when ``ANTHROPIC_API_KEY`` is set, or returns HOLD with a warning when both
paths are unavailable.
"""
from __future__ import annotations

import sys


def main() -> int:
    """Download and cache the FinBERT model. Returns 0 on success, 1 on error."""
    try:
        from transformers import pipeline  # noqa: F401
    except ImportError:
        print(
            "transformers is not installed. Run:\n"
            "    pip install -e .[llm-local]\n"
            "to enable local FinBERT sentiment analysis.",
            file=sys.stderr,
        )
        return 1

    print("Downloading ProsusAI/finbert (~400 MB)...", flush=True)
    try:
        _ = pipeline("sentiment-analysis", model="ProsusAI/finbert")
    except Exception as exc:
        print(f"FinBERT download failed: {exc}", file=sys.stderr)
        return 1

    print(
        "FinBERT cached successfully. "
        "SentimentAgent can now use local sentiment when ANTHROPIC_API_KEY is unset."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
