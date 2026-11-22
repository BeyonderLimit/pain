"""Intent parser for P.A.N. (Phase 2: word-boundary regex rules).

Replaces the Phase 1 substring parser (`keyword in text`) which had
verified misfires:

- "get the news"          -> add_entry   ("new" in "news" is a substring of "new")
- "update the software"   -> date        ("date" is a substring of "update")
- "display the options"   -> play_music  ("play" is a substring of "display")
- "new york weather"      -> add_entry   ("new")
- "show my schedule"      -> add_entry   ("schedule" was in add_entry's keywords)
- "schedule meeting"      -> add_entry   (same)

Design:
- Rules are ordered from most specific to most general (order matters: the
  first matching intent wins).
- Patterns use ``\\b`` word boundaries, so "news" doesn't match "new",
  "update" doesn't match "date", "display" doesn't match "play", etc.
- No spaCy: keyword regexes are fast, dependency-free, and testable.

Phase 2b: added intents — `launch_app` (open/launch/run), `close_app`
(close/kill/terminate), `volume`, `brightness`, `system_stats` — plus
extractor helpers: `extract_app_name`, `extract_volume_direction`,
`extract_brightness_direction`.
"""

from __future__ import annotations

import re

# (intent, [regexes]) — checked in this order; first match wins.
INTENT_RULES: list[tuple[str, list[str]]] = [
    ("exit", [r"\bexit\b", r"\bquit\b", r"\bbye\b", r"\bgoodbye\b", r"\bend\b", r"\bleave\b", r"\bshut down\b"]),
    # Before stop_music/chat so "stop speaking" isn't parsed as either.
    ("silent_mode", [
        r"\bsilent mode\b", r"\bsilent\b", r"\bquiet mode\b",
        r"\bvoice off\b", r"\bvoice on\b", r"\bspeech off\b",
        r"\bspeech on\b", r"\btts off\b", r"\btts on\b",
        r"\bspeak again\b", r"\btalk again\b", r"\bstop speaking\b",
        r"\bdon'?t speak\b", r"\bdisable (?:tts|speech|voice)\b",
        r"\benable (?:tts|speech|voice)\b", r"\bno speech\b",
    ]),
    ("stop_music", [r"\bstop\b", r"\bpause\b", r"\bhalt\b"]),
    ("youtube", [r"\byoutube\b", r"\bwatch\b", r"\bvideo\b"]),
    ("news", [r"\bnews\b", r"\bheadlines\b", r"\bupdates\b", r"\bcurrent events\b"]),
    ("play_music", [r"\bplay\b", r"\bmusic\b", r"\bsong\b", r"\btune\b", r"\baudio\b"]),
    ("status", [r"\bstatus\b", r"\bwhat's playing\b", r"\bwhat is playing\b", r"\bnow playing\b", r"\bcurrently playing\b", r"\bwhat song\b", r"\bwhat track\b"]),
    ("schedule", [r"\bschedule\b", r"\bevents\b", r"\bcalendar\b", r"\bagenda\b", r"\bappointments\b"]),
    ("launch_app", [r"\bopen\b", r"\blaunch\b", r"\brun\b"]),
    ("add_entry", [r"\badd\b", r"\bcreate\b", r"\bset up\b", r"\bplan\b"]),
    ("close_app", [r"\bclose\b", r"\bkill\b", r"\bterminate\b"]),
    ("weather", [r"\bweather\b", r"\btemperature\b", r"\bforecast\b", r"\bclimate\b", r"\bconditions\b"]),
    ("time", [r"\btime\b", r"\bclock\b"]),
    ("date", [r"\bdate\b", r"\bday\b", r"\btoday\b"]),
    # Saved transcript commands must precede memo/dictate/search/list rules.
    ("search_dictations", [
        r"\b(?:search|find|grep|look up)\s+(?:for\s+|in\s+|through\s+)?(?:my\s+)?(?:dictations?|dictation notes?)\b",
    ]),
    ("search_notes", [
        r"\b(?:search|find|grep|look up)\s+(?:for\s+|in\s+|through\s+)?(?:my\s+)?(?:notes?|memos?)\b",
        r"\b(?:notes?|memos?)\s+(?:about|containing|with|for)\b",
    ]),
    ("list_dictations", [
        r"\blist\s+(?:my\s+)?(?:dictations?|dictation notes?)\b",
        r"\bdictations\b", r"\bdictation notes\b",
    ]),
    ("list_notes", [
        r"\blist\s+(?:my\s+)?(?:voice\s+)?(?:notes?|memos?)\b",
        r"\bnotes\b", r"\bmemos\b", r"\bmy notes\b",
    ]),
    ("read_note", [
        r"\b(?:cat|read|show|view)\s+(?:my\s+)?(?:voice\s+)?(?:note|memo)(?:\s+(?:number\s+)?[\w.\-]+)?\b",
        r"\b(?:latest|last|most recent)\s+(?:voice\s+)?(?:note|memo)\b",
        r"\b(?:cat|read|show|view)\s+(?:memo|note)_[\w.\-]+\b",
    ]),
    ("read_dictation", [
        r"\b(?:cat|read|show|view)\s+(?:my\s+)?(?:dictation)(?:\s+(?:number\s+)?[\w.\-]+)?\b",
        r"\b(?:latest|last|most recent)\s+dictation\b",
        r"\b(?:cat|read|show|view)\s+dictation_[\w.\-]+\b",
    ]),
    ("memo", [r"\bmemo\b", r"\bvoice memo\b", r"\brecord\b", r"\bnote\b"]),
    ("dictate", [r"\bdictate\b", r"\bdictation\b"]),
    ("reminder", [r"\breminder\b", r"\bremind\b", r"\balarm\b", r"\bnotify\b"]),
    ("system_stats", [r"\bstats\b", r"\bsystem stats\b", r"\bcpu\b", r"\bmemory\b", r"\bram\b", r"\bdisk\b", r"\bdisk space\b", r"\bstorage\b", r"\bresources\b", r"\bsystem resources\b", r"\bsystem info\b", r"\buptime\b", r"\bbattery\b"]),
    ("volume", [r"\bvolume\b", r"\blouder\b", r"\bquieter\b", r"\bmute\b", r"\bunmute\b", r"\bturn up\b", r"\bturn down\b", r"\bincrease volume\b", r"\bdecrease volume\b"]),
    ("brightness", [r"\bbrightness\b", r"\bscreen brightness\b", r"\bbrighter\b", r"\bdarker\b", r"\bdimmer\b", r"\bmake it brighter\b", r"\bmake it darker\b"]),
    ("chat", [r"\bchat\b", r"\btalk\b", r"\bconverse\b", r"\bspeak\b", r"\btell me\b"]),
    ("help", [r"\bhelp\b", r"\bhelp me\b", r"\bwhat can you do\b", r"\bwhat do you do\b", r"\busage\b"]),
    ("files", [r"\bfiles\b", r"\bfile\b", r"\bfile search\b"]),
    ("search", [
        r"\bsearch\b", r"\blook up\b", r"\bfind\b", r"\bgoogle\b",
        r"\bwhat is\b", r"\bwhat are\b", r"\bwhat does\b", r"\bwho is\b",
        r"\bwho are\b", r"\bwhat's\b", r"\bwho's\b", r"\bdefine\b",
        r"\bdefinition of\b", r"\bmeaning of\b", r"\bexplain\b", r"\blist\b",
    ]),
]

_INTENT_PATTERNS = [
    (intent, [re.compile(pattern, re.IGNORECASE) for pattern in patterns])
    for intent, patterns in INTENT_RULES
]

# ---------------------------------------------------------------------------
# Extractors (Phase 2b)
# ---------------------------------------------------------------------------

_STOPWORDS = {"the", "a", "an", "my", "your", "please", "now", "me", "this", "that"}
_LEADING_VERBS = {"open", "launch", "run", "close", "kill", "terminate", "stop", "exit"}


def get_intent(text: str) -> str:
    """Return the first matching intent name, or "unknown" if none match."""
    if not text:
        return "unknown"
    for intent, patterns in _INTENT_PATTERNS:
        if any(pattern.search(text) for pattern in patterns):
            return intent
    return "unknown"


def extract_app_name(text: str) -> str:
    """Extract the application name from user text (launch_app/close_app).

    Strips leading verbs ("open", "launch", "close", "kill", ...) and
    stopwords ("the", "a", "please", ...); returns the remaining words joined.
    """
    words = [w.strip("?!.,:;'\"()") for w in text.split()]
    words = [w for w in words if w]
    while words and (words[0].lower() in _LEADING_VERBS or words[0].lower() in _STOPWORDS):
        words = words[1:]
    return " ".join(words)


def extract_volume_direction(text: str) -> str:
    """Volume intent: return "up", "down", "mute", "unmute", or "" (current)."""
    lowered = text.lower()
    if re.search(r"\bunmute\b|\bsilence\b", lowered):
        return "unmute"
    if re.search(r"\bmute\b", lowered):
        return "mute"
    if re.search(r"\bup\b|\blouder\b|\bincrease\b|\braise\b", lowered):
        return "up"
    if re.search(r"\bdown\b|\bquieter\b|\bdecrease\b|\breduce\b|\blower\b", lowered):
        return "down"
    return ""


def extract_brightness_direction(text: str) -> str:
    """Brightness intent: return "up", "down", or "" (current)."""
    lowered = text.lower()
    if re.search(r"\bup\b|\bbrighter\b|\bincrease\b", lowered):
        return "up"
    if re.search(r"\bdown\b|\bdarker\b|\bdecrease\b|\bdim\b", lowered):
        return "down"
    return ""


def extract_silent_mode(text: str) -> str:
    """Return "on", "off", or "" (toggle) for silent-mode commands."""
    lowered = text.lower()
    if re.search(
        r"\bvoice on\b|\bspeech on\b|\btts on\b|\bspeak again\b|"
        r"\btalk again\b|\benable (?:tts|speech|voice)\b",
        lowered,
    ):
        return "on"
    if re.search(
        r"\bsilent(?: mode)?\b|\bquiet mode\b|\bvoice off\b|"
        r"\bspeech off\b|\btts off\b|\bstop speaking\b|\bdon'?t speak\b|"
        r"\bdisable (?:tts|speech|voice)\b|\bno speech\b",
        lowered,
    ):
        return "off"
    return ""


def _extract_level(text: str, setting: str) -> int | None:
    """Extract an absolute percentage for ``setting`` (volume/brightness).

    Only matches when the setting name precedes the number, so relative
    commands like "volume up 5" are not mistaken for "set volume to 5".
    """
    pattern = (
        rf"\b{setting}\s*(?:level)?\s*(?:to|at|=|:)?\s*"
        r"(\d{1,3})\s*(?:%|percent)?(?!\d)"
    )
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    value = int(match.group(1))
    return value if 0 <= value <= 100 else None


def extract_volume_level(text: str) -> int | None:
    """Return the requested volume percentage, or None when unspecified."""
    return _extract_level(text, "volume")


def extract_brightness_level(text: str) -> int | None:
    """Return the requested brightness percentage, or None when unspecified."""
    return _extract_level(text, "brightness")


_SEARCH_PREFIX = re.compile(
    r"^\s*(?:please\s+)?(?:can you\s+|could you\s+|would you\s+)?"
    r"(?:search(?:\s+(?:for|the web for))?|look up|google|find|"
    r"what is|what are|what does|who is|who are|what's|who's|"
    r"define|definition of|meaning of|explain|tell me about|list(?:\s+some)?)"
    r"\s+",
    re.IGNORECASE,
)
_SEARCH_TRAILER = re.compile(
    r"[,\s]+(?:what is it|who is it|what is that|etc\.?)\s*$", re.IGNORECASE
)


def extract_search_query(text: str) -> str:
    """Strip the trigger phrase from a search-like command."""
    query = text.strip().rstrip("?!.")
    if query.lower() in {"search", "find", "google", "look up"}:
        return ""
    query = _SEARCH_TRAILER.sub("", query).strip()
    match = _SEARCH_PREFIX.match(query)
    if match:
        query = query[match.end():]
    return re.sub(r"^(?:a|an|the)\s+", "", query, flags=re.IGNORECASE).strip()


_PLAY_PREFIX = re.compile(
    r"^\s*(?:please\s+)?(?:can you\s+|could you\s+)?play\s+"
    r"(?:some\s+|the\s+|a\s+|an\s+)?(?:music\s+|song\s+)?",
    re.IGNORECASE,
)


def extract_play_query(text: str) -> str:
    """Return the requested track/query after ``play``, or "" for random play."""
    match = _PLAY_PREFIX.match(text)
    if not match:
        return ""
    query = text[match.end():].strip().strip("'\"“”‘’").rstrip("?!.").strip()
    if query.lower() in {"music", "song", "songs", "some music"}:
        return ""
    return query


_ITEM_FILE = re.compile(
    r"\b(?:cat|read|show|view)\s+((?:memo|note|dictation)_[\w.\-]+)",
    re.IGNORECASE,
)
_ITEM_SELECTOR = re.compile(
    r"\b(?:cat|read|show|view)\s+(?:my\s+)?(?:voice\s+)?"
    r"(?:notes?|memos?|dictations?)\s+(?:number\s+)?(.+?)\s*$",
    re.IGNORECASE,
)
_ITEM_QUERY = re.compile(
    r"^\s*(?:please\s+)?(?:can you\s+|could you\s+)?"
    r"(?:search|find|grep|look up)\s+(?:for\s+|in\s+|through\s+)?"
    r"(?:my\s+)?(?:notes?|memos?|dictations?(?:\s+notes?)?)"
    r"(?:\s+(?:for\s+|about\s+|containing\s+))?",
    re.IGNORECASE,
)


def extract_item_selector(text: str) -> str | None:
    """Return a transcript number/name, or None for the latest item."""
    if re.search(r"\b(?:latest|last|most recent)\b", text, re.IGNORECASE):
        return "last"
    file_match = _ITEM_FILE.search(text)
    if file_match:
        return file_match.group(1)
    selector_match = _ITEM_SELECTOR.search(text)
    if selector_match:
        return selector_match.group(1).strip().strip("'\"")
    return None


def extract_item_query(text: str) -> str:
    """Return the text to search for inside saved transcripts."""
    match = _ITEM_QUERY.match(text)
    if match:
        query = text[match.end():]
    else:
        query = re.sub(
            r"^\s*(?:search|find|grep|look up)\s+", "", text, flags=re.IGNORECASE
        )
    return query.strip().strip("'\"").rstrip("?!.").strip()

