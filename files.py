"""Local file search (Phase 9): find files by name/extension on disk."""

from __future__ import annotations

import re
from pathlib import Path

from config import FILES_SEARCH_ROOTS

FILLER_WORDS = {
    "find", "me", "a", "an", "the", "any", "all", "some",
    "local", "locally", "on", "in", "at", "disk", "drive", "folder", "dir",
    "my", "your", "file", "files",
    "what", "which", "where", "when", "how", "do", "does",
    "show", "list", "search", "look", "looking", "for", "please",
    "can", "could",
}


def extract_file_pattern(query: str) -> str:
    """Extract a glob pattern for files from the user's query.

    Examples:
    - "find me .md files locally" -> "*.md"
    - "readme file" -> "*readme*"
    """
    words = []
    for token in query.split():
        word = token.strip(".,;:!?'\"")
        if token.startswith("."):
            word = "." + word.lstrip(".") if word else "."
        if not word or word.lower() in FILLER_WORDS:
            continue
        words.append(word)
    # 1) Extension-like tokens: ".md", "app.py" -> "*.md"
    for word in words:
        if word.startswith("."):
            return f"*{word}"
        if re.fullmatch(r"[A-Za-z0-9]+\.[A-Za-z0-9]+", word):
            return f"*{word}"
    # 2) Fallback: the remaining words as a substring pattern.
    if words:
        return f"*{' '.join(w.lower() for w in words)}*"
    return "*"


def search_files(pattern: str = "*", roots=None) -> list[Path]:
    """Return files matching ``pattern`` (a glob) under the search roots."""
    if roots is None:
        roots = FILES_SEARCH_ROOTS
    found: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            for path in sorted(root.rglob(pattern)):
                if not path.is_file():
                    continue
                key = str(path)
                if key in seen:
                    continue
                seen.add(key)
                found.append(path)
        except OSError as e:
            print(f"Files search error in {root}: {e}")
    return found
