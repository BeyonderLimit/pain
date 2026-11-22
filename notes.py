"""List, read, and search saved voice memos and dictation transcripts."""

from __future__ import annotations

from pathlib import Path

import config

MEMOS_DIR = config.MEMOS_DIR
DICTATE_DIR = config.DICTATE_DIR

_MAX_RESULTS = 10


def _spec(kind: str):
    if kind == "note":
        return MEMOS_DIR, "memo_", "note"
    return DICTATE_DIR, "dictation_", "dictation"


def list_items(kind: str) -> list[Path]:
    directory, prefix, _ = _spec(kind)
    if not directory.is_dir():
        return []
    return sorted(
        directory.glob(f"{prefix}*.txt"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _snippet(text: str, width: int = 60) -> str:
    single_line = " ".join(text.split())
    return single_line[:width] + ("…" if len(single_line) > width else "")


def format_list(kind: str) -> str:
    _, _, label = _spec(kind)
    items = list_items(kind)
    if not items:
        return f"No {label}s saved yet."
    lines = []
    for index, path in enumerate(items, 1):
        text = _read(path)
        snippet = _snippet(text) if text else "(empty transcript)"
        lines.append(f"{index}. {path.name} — {snippet}")
    shown = "\n".join(lines[:_MAX_RESULTS])
    if len(items) > _MAX_RESULTS:
        shown += f"\n... and {len(items) - _MAX_RESULTS} more (read note <n> to view one)"
    return f"{label.capitalize()}s (newest first):\n{shown}"


def _resolve(kind: str, selector: str | None):
    _, _, label = _spec(kind)
    items = list_items(kind)
    if not items:
        return None, f"No {label}s saved yet."
    if not selector or selector.lower() in {"last", "latest", "most recent"}:
        return items[0], None
    if selector.isdigit():
        index = int(selector)
        if 1 <= index <= len(items):
            return items[index - 1], None
        return None, f"No {label} number {index}; {len(items)} saved."
    matches = [path for path in items if selector.lower() in path.name.lower()]
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        return None, f"No {label} matching {selector!r}."
    return None, f"Ambiguous {label} name {selector!r}: {', '.join(p.name for p in matches)}"


def cat_item(kind: str, selector: str | None = None) -> str:
    _, _, label = _spec(kind)
    path, error = _resolve(kind, selector)
    if error:
        return error
    text = _read(path)
    return f"--- {path.name} ---\n{text or '(empty transcript)'}"


def search_items(kind: str, query: str) -> str:
    _, _, label = _spec(kind)
    query = query.strip()
    if not query:
        return format_list(kind)
    needle = query.lower()
    matches = []
    for path in list_items(kind):
        text = _read(path)
        if needle in text.lower():
            hits = [line.strip() for line in text.splitlines() if needle in line.lower()]
            matches.append((path, hits[:2]))
    if not matches:
        return f"No {label}s containing {query!r}."
    lines = []
    for index, (path, hits) in enumerate(matches, 1):
        lines.append(f"{index}. {path.name}: {' / '.join(hits) if hits else '(match)'}")
    shown = "\n".join(lines[:_MAX_RESULTS])
    if len(matches) > _MAX_RESULTS:
        shown += f"\n... and {len(matches) - _MAX_RESULTS} more matches"
    return f"Matches in {label}s for {query!r}:\n{shown}"
