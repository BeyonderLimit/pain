"""Music playback helpers (Phase 4)."""

from __future__ import annotations

import os
import random
import re
from pathlib import Path

import yt_dlp

import player

_AUDIO_EXTS = (".mp3", ".mp4", ".m4a", ".aac", ".ogg", ".wav", ".flac")
_STOPWORDS = {"the", "a", "an", "of", "official", "lyric", "lyrics", "video", "hd", "hq"}


def _music_files(music_dirs) -> list[str]:
    files: list[str] = []
    for music_dir in music_dirs:
        if os.path.exists(music_dir):
            files.extend(
                os.path.join(music_dir, f)
                for f in os.listdir(music_dir)
                if f.lower().endswith(_AUDIO_EXTS)
            )
    return sorted(files)


def play_local(music_dirs) -> str:
    """Play a random local music file from ``music_dirs``."""
    all_music_files = _music_files(music_dirs)
    if not all_music_files:
        return "No music files found in the specified directories."
    random_file = random.choice(all_music_files)
    player.set_media(random_file)
    return f"Now playing: {os.path.basename(random_file)}"


def find_local_matches(query: str, music_dirs) -> list[str]:
    """Return local files whose names contain the query's meaningful words."""
    terms = [
        term for term in re.split(r"[\s\-_]+", query.lower())
        if term and term not in _STOPWORDS
    ]
    if not terms:
        return []
    return [
        path for path in _music_files(music_dirs)
        if all(term in Path(path).stem.lower() for term in terms)
    ]


def play_named(query: str, music_dirs) -> str:
    """Play a named track locally if possible, otherwise search YouTube."""
    matches = find_local_matches(query, music_dirs)
    if matches:
        chosen = matches[0]
        player.set_media(chosen)
        return f"Now playing: {os.path.basename(chosen)}"
    return play_youtube(query)


def play_youtube(query: str) -> str:
    """Play audio from YouTube (first result of a search)."""
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "%(title)s.%(ext)s",
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if "entries" not in info or not info["entries"]:
                return "No YouTube videos found for that query."
            entry = info["entries"][0]
            player.set_media(entry["url"])
            return f"Now playing: {entry['title']}"
    except Exception as e:
        return f"Error playing YouTube audio: {e}"
