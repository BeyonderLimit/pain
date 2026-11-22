"""Push-to-talk voice input: hold Super+Space, speak, release to submit.

The global hotkey listener needs X11 (via pynput) and a working microphone.
If either is unavailable the listener fails softly and typed input keeps
working. Transcripts are handed to a callback, which pain.py feeds into its
REPL input queue.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import wave
from collections.abc import Callable

import sounddevice as sd
from pynput import keyboard

from config import (
    DICTATE_BIN,
    DICTATE_MODEL_PATH,
    PTT_MAX_DURATION,
    PTT_SAMPLE_RATE,
)
from dictation import _parse_whisper_output, ensure_whisper

_SUPER_KEYS = {
    keyboard.Key.cmd,
    keyboard.Key.cmd_l,
    keyboard.Key.cmd_r,
}
_HOTKEY_KEYS = _SUPER_KEYS | {keyboard.Key.space}


def transcribe_audio(audio: bytes) -> str:
    """Transcribe raw int16 mono audio with the whisper.cpp binary."""
    ensure_whisper()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
        wav_path = fh.name
    try:
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(PTT_SAMPLE_RATE)
            wf.writeframes(audio)
        result = subprocess.run(
            [str(DICTATE_BIN), "-m", str(DICTATE_MODEL_PATH), "-f", wav_path],
            capture_output=True,
            text=True,
            timeout=180,
        )
        return _parse_whisper_output(result.stdout).strip()
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass


class PushToTalk:
    """Listen for Super+Space and invoke ``on_transcript`` on release."""

    def __init__(
        self,
        on_transcript: Callable[[str], None],
        announce: Callable[[str], None] | None = None,
    ) -> None:
        self._on_transcript = on_transcript
        self._announce = announce or (lambda message: None)
        self._lock = threading.RLock()
        self._pressed: set[keyboard.Key] = set()
        self._frames: list[bytes] = []
        self._stream = None
        self._timer: threading.Timer | None = None
        self._recording = False
        self._listener: keyboard.Listener | None = None
        self._stopped = threading.Event()

    def start(self) -> bool:
        """Start the hotkey listener; return False if it cannot be started."""
        try:
            self._listener = keyboard.Listener(
                on_press=self._on_press, on_release=self._on_release
            )
            self._listener.start()
            return True
        except Exception as e:
            print(f"Push-to-talk unavailable: {e}")
            return False

    def stop(self) -> None:
        """Stop listening and discard any in-progress recording."""
        self._stopped.set()
        with self._lock:
            if self._recording:
                self._stop_recording(discard=True)
        if self._listener is not None:
            self._listener.stop()
            self._listener.join(timeout=2)

    def _hotkey_held(self) -> bool:
        return bool(_SUPER_KEYS & self._pressed) and keyboard.Key.space in self._pressed

    def _on_press(self, key) -> None:
        if key not in _HOTKEY_KEYS:
            return
        with self._lock:
            self._pressed.add(key)
            if not self._recording and self._hotkey_held():
                self._start_recording()

    def _on_release(self, key) -> None:
        if key not in _HOTKEY_KEYS:
            return
        with self._lock:
            self._pressed.discard(key)
            if self._recording and not self._hotkey_held():
                self._stop_recording()

    def _start_recording(self) -> None:
        self._recording = True
        self._frames = []
        try:
            self._stream = sd.InputStream(
                samplerate=PTT_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                callback=self._audio_callback,
            )
            self._stream.start()
            self._timer = threading.Timer(PTT_MAX_DURATION, self._on_timeout)
            self._timer.start()
            self._announce("Listening… release Super+Space to submit.")
        except Exception as e:
            self._recording = False
            self._stream = None
            self._frames = []
            self._announce(f"Push-to-talk recording failed: {e}")

    def _audio_callback(self, indata, frames, time, status) -> None:
        if self._recording:
            self._frames.append(indata.tobytes())

    def _on_timeout(self) -> None:
        with self._lock:
            if self._recording:
                self._stop_recording()
                self._announce("Push-to-talk maximum duration reached.")

    def _stop_recording(self, discard: bool = False) -> None:
        """Stop the stream; caller must hold ``self._lock``."""
        self._recording = False
        stream, self._stream = self._stream, None
        frames, self._frames = b"".join(self._frames), []
        timer, self._timer = self._timer, None
        if timer is not None:
            timer.cancel()
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        if discard or not frames:
            if not discard:
                self._announce("No audio captured.")
            return
        threading.Thread(
            target=self._transcribe, args=(frames,), daemon=True
        ).start()

    def _transcribe(self, frames: bytes) -> None:
        try:
            text = transcribe_audio(frames)
        except Exception as e:
            self._announce(f"Push-to-talk transcription failed: {e}")
            return
        if self._stopped.is_set():
            return
        if text:
            self._on_transcript(text)
        else:
            self._announce("No speech recognized.")
