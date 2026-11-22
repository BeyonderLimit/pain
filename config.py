"""Centralized settings for P.A.N. (Personal Assistant, Navigation & news).

Phase 1 (Foundations): plain constants shared by pain.py, tts.py and the
feature modules that land in later phases (Phase 2: intents; Phase 3: REPL
loop + reminders; Phase 4: weather, calendar, music, YouTube, news, search;
Phase 7a: voice memos).

Values match the original pain-build.md defaults. Piper replaces the
espeak-ng default for TTS (natural-sounding neural voice; see tts.py).
Later phases make some of these configurable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# --- Data directories ---
DATA_DIR = Path.home() / ".local" / "share" / "pain"
MEMOS_DIR = DATA_DIR / "memos"
REMINDER_FILE = DATA_DIR / "reminders.json"
VOSK_MODEL_DIR = DATA_DIR / "vosk-model"
PIPER_MODELS_DIR = DATA_DIR / "voices"  # <voice>.onnx + <voice>.onnx.json


def ensure_dirs() -> None:
    """Create the data directories (called by pain.py --smoke and pain.py)."""
    for directory in (DATA_DIR, MEMOS_DIR, PIPER_MODELS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


# --- Location (open-meteo endpoint parameters) ---
@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float
    timezone: str


LOCATION = Location(
    name="New Haven, CT",
    latitude=41.3083,
    longitude=-72.9279,
    timezone="America/New_York",
)
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"


# --- Calendar ---
# The original app reads Evolution's ICS; overridable in later phases.
CALENDAR_FILE_PATH = (
    Path.home()
    / ".local"
    / "share"
    / "evolution"
    / "calendar"
    / "system"
    / "calendar.ics"
)


# --- Music ---
MUSIC_DIRS = (Path.home() / "Music", Path.home() / "Downloads")


# --- Ollama (local chat, Phase 3) ---
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "tinyllama"


# --- TTS: Piper (piper-tts) via tts.py ---
SPEAK_RESPONSES = True  # False (or `python pain.py --silent`) starts with speech off
DEFAULT_VOICE = "en_US-danny-low"


# --- News (Phase 4) ---
NEWS_SOURCES = (
    "http://rss.cnn.com/rss/cnn_topstories.rss",
    "https://feeds.bbci.co.uk/news/rss.xml",
    "http://feeds.reuters.com/reuters/topNews",
)


# --- Voice memos (Phase 7a) ---
VOSK_MODEL_PATH = VOSK_MODEL_DIR

# --- Dictation (Phase 8): whisper.cpp ASR ---
DICTATE_DIR = DATA_DIR / "dictation"  # whisper-cli, models/, dictation files
DICTATE_BIN = DICTATE_DIR / "whisper-cli"
DICTATE_MODELS_DIR = DICTATE_DIR / "models"
DICTATE_MODEL = "ggml-base.en.bin"
DICTATE_MODEL_PATH = DICTATE_MODELS_DIR / DICTATE_MODEL
DICTATE_DURATION = 30.0  # seconds of audio per dictation

# --- Push-to-talk (hold Super+Space) ---
PTT_ENABLED = True
PTT_SAMPLE_RATE = 16000  # must match the whisper model's expected input
PTT_MAX_DURATION = 60.0  # safety cap if the release event is missed

DICTATE_WHISPER_RELEASE_URL = (
    "https://github.com/ggml-org/whisper.cpp/releases/download/b5907/"
    "whisper-bin-ubuntu-x64.tar.gz"
)


# --- Local file search (Phase 9) ---
FILES_SEARCH_ROOTS = (Path.home(),)
