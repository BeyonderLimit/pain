"""Web search via DuckDuckGo (Phase 4)."""

from __future__ import annotations

from ddgs import DDGS


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Return up to ``max_results`` DuckDuckGo results: [{"title", "body"}, ...]."""
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
    except Exception as e:
        print(f"Error searching: {e}")
        return []
    return [{"title": r.get("title", ""), "body": r.get("body", "")} for r in results]
