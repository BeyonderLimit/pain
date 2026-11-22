"""News headlines via RSS (Phase 4)."""

from __future__ import annotations

import random

import feedparser

from config import NEWS_SOURCES


def fetch_news(max_headlines: int = 3) -> list[str]:
    """Fetch headlines from a random RSS source in ``NEWS_SOURCES``."""
    if not NEWS_SOURCES:
        print("No news sources configured (config.NEWS_SOURCES).")
        return []
    feed_url = random.choice(list(NEWS_SOURCES))
    try:
        feed = feedparser.parse(feed_url)
    except Exception as e:
        print(f"Error fetching news: {e}")
        return []

    headlines = []
    for entry in list(getattr(feed, "entries", []) or [])[:max_headlines]:
        title = entry.get("title") or "No title"
        summary = entry.get("summary") or entry.get("title") or "No summary available"
        headlines.append(f"{title}. {summary}")
    return headlines
