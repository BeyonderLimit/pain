"""Text-to-speech engine for P.A.N. (Piper via the `piper-tts` pip package).

Primary: Piper (natural-sounding neural TTS). Last resort: espeak-ng (if
installed). Final: plain text output.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from config import DEFAULT_VOICE, PIPER_MODELS_DIR, SPEAK_RESPONSES

try:
    import piper  # pip package "piper-tts"
except ImportError:
    piper = None  # type: ignore[assignment]


def find_piper_command() -> list[str] | None:
    """Return the command list to invoke Piper, or None if not available."""
    import shutil

    if shutil.which("piper"):
        return ["piper"]
    if piper is not None:
        return [sys.executable, "-m", "piper"]
    return None


def voice_model_path(voice: str) -> Path:
    """Path of a downloaded Piper voice model (``<voice>.onnx``)."""
    return PIPER_MODELS_DIR / f"{voice}.onnx"


def voice_exists(voice: str) -> bool:
    """True if both the voice model and its config are downloaded."""
    return (PIPER_MODELS_DIR / f"{voice}.onnx").is_file() and (
        PIPER_MODELS_DIR / f"{voice}.onnx.json"
    ).is_file()


def download_voice(voice: str) -> None:
    """Download a Piper voice (model + config) into PIPER_MODELS_DIR."""
    from piper import download_voices

    PIPER_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    download_voices.download_voice(voice, PIPER_MODELS_DIR)
    if not voice_exists(voice):
        raise RuntimeError(f"voice model not found after download: {voice}")


def ensure_voice(voice: str) -> None:
    """Download the voice if it is not present yet."""
    if not voice_exists(voice):
        download_voice(voice)


class TTSEngine:
    """Speaks text: Piper first, espeak-ng as a last resort."""

    def __init__(self, voice: str = DEFAULT_VOICE, enabled: bool | None = None):
        self.voice = voice
        self.enabled = SPEAK_RESPONSES if enabled is None else enabled

    def set_enabled(self, enabled: bool) -> None:
        """Turn speech responses on/off (printed output is unaffected)."""
        self.enabled = bool(enabled)

    def speak(self, text: str) -> None:
        if not self.enabled:
            return
        if self._piper_speak(text):
            return
        self._espeak_speak(text)

    def _piper_speak(self, text: str) -> bool:
        """Render with Piper into a temp WAV and play it with aplay."""
        command = find_piper_command()
        if command is None:
            return False
        model = voice_model_path(self.voice)
        wav_path = ""
        try:
            ensure_voice(self.voice)
            if not model.is_file():
                return False
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
                wav_path = fh.name
            result = subprocess.run(
                [*command, "--model", str(model), "--output-file", wav_path],
                input=text.encode("utf-8"),
                stderr=subprocess.PIPE,
                timeout=60,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace").strip()
                raise RuntimeError(
                    f"piper exited with code {result.returncode}: {stderr[:200]}"
                )
            subprocess.run(
                ["aplay", wav_path], check=True, capture_output=True, timeout=90
            )
            return True
        except Exception as e:
            print(f"Piper TTS Error: {e}")
            return False
        finally:
            if wav_path:
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass

    def _espeak_speak(self, text: str) -> None:
        """Last resort: render with espeak-ng and play with aplay."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
                wav_path = fh.name
            try:
                subprocess.run(
                    ["espeak-ng", "-v", self._espeak_voice(), "-w", wav_path, text],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
                subprocess.run(
                    ["aplay", wav_path], check=True, capture_output=True, timeout=90
                )
            finally:
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass
        except Exception as e:
            print(f"TTS Error: {e}")
            print(f"Falling back to text output: {text}")

    def _espeak_voice(self) -> str:
        """Map Dimits-style voices ("en_US-danny-low") to espeak-ng ("en-us")."""
        if "_" in self.voice:
            lang, rest = self.voice.split("_", 1)
            region = rest.split("-")[0]
            return f"{lang}-{region.lower()}"
        return self.voice

    def set_voice(self, voice: str) -> None:
        """Set the voice name."""
        self.voice = voice

    def list_voices(self) -> None:
        """List available Piper voices."""
        try:
            from piper import download_voices

            download_voices.list_voices()
        except Exception as e:
            print(f"Error listing voices: {e}")
