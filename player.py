"""Music player wrapper for P.A.N. (Phase 3: stop + status; Phase 4: more)."""

from __future__ import annotations

import vlc

_player: vlc.MediaPlayer | None = None
_media: str = ""


def set_media(path_or_url: str) -> None:
    """Set and start playback; stops any currently playing media."""
    global _player, _media
    _media = path_or_url
    if _player is not None:
        _player.stop()
    _player = vlc.MediaPlayer(path_or_url)
    _player.play()


def stop() -> str:
    """Stop playback and clear the player."""
    global _player
    if _player is not None:
        _player.stop()
        _player = None
        return "Music stopped."
    return "No music is playing."


def set_pause(paused: bool) -> None:
    """Pause/resume playback (no-op if nothing is playing)."""
    if _player is not None:
        _player.set_pause(paused)


def status() -> str:
    """Human-readable playback status."""
    if _player is not None and _player.is_playing():
        return f"Playing: {_media}"
    return "No music is playing."
