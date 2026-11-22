"""Dictation tool (Phase 8): record speech and transcribe with whisper.cpp.

Uses the whisper.cpp binary (``whisper-cli``) with a whisper model
(default: ``ggml-base.en.bin`` — say ``ggml-tiny.en.bin`` for a smaller,
faster model). ``record_dictation()`` records a window of audio, transcribes
it, saves the transcript as a text file, and returns a message.
"""

from __future__ import annotations

import datetime
import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import wave
from pathlib import Path
from urllib.request import urlopen

import sounddevice as sd

from config import (
    DICTATE_BIN,
    DICTATE_DIR,
    DICTATE_DURATION,
    DICTATE_MODEL,
    DICTATE_MODEL_PATH,
    DICTATE_MODELS_DIR,
    DICTATE_WHISPER_RELEASE_URL,
)

# Models are hosted on HuggingFace under the ggerganov/whisper.cpp repo.
DICTATE_MODEL_URL = (
    f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{DICTATE_MODEL}"
)


def ensure_whisper() -> None:
    """Download and extract the whisper.cpp binary and the dictation model
    if they are missing."""
    if not _whisper_ok():
        DICTATE_DIR.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading whisper.cpp to {DICTATE_DIR} (one time)...")
        with urlopen(DICTATE_WHISPER_RELEASE_URL, timeout=300) as response:
            data = response.read()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            names = archive.getnames()
            archive.extractall(DICTATE_DIR.parent)
            top = names[0].split("/")[0]
        extracted = DICTATE_DIR.parent / top
        if extracted != DICTATE_DIR:
            if DICTATE_DIR.exists():
                shutil.rmtree(DICTATE_DIR)
            extracted.replace(DICTATE_DIR)
        if not _whisper_ok():
            raise RuntimeError(
                f"whisper.cpp binary missing after download — expected at {DICTATE_BIN}"
            )
    _ensure_dictate_model()


def _whisper_ok() -> bool:
    try:
        return DICTATE_BIN.is_file()
    except OSError:
        return False


def _ensure_dictate_model() -> None:
    """Download the whisper.cpp model if it is missing."""
    if DICTATE_MODEL_PATH.is_file():
        return
    DICTATE_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading whisper model {DICTATE_MODEL} ...")
    with urlopen(DICTATE_MODEL_URL, timeout=600) as response:
        data = response.read()
    DICTATE_MODEL_PATH.write_bytes(data)
    if not DICTATE_MODEL_PATH.is_file():
        raise RuntimeError(
            f"whisper model missing after download — expected at {DICTATE_MODEL_PATH}"
        )


def record_dictation(duration: float = DICTATE_DURATION) -> str:
    """Record a dictation, transcribe it with whisper.cpp, save the
    transcript as a text file, and return a human-readable message.
    Never raises (failures become messages)."""
    try:
        return _record_dictation(duration)
    except Exception as e:
        return f"Dictation failed: {e}"


def _record_dictation(duration: float) -> str:
    ensure_whisper()
    _ensure_dictate_model()

    frames = int(duration * 16000)
    recording = sd.rec(frames, samplerate=16000, channels=1, dtype="int16")
    sd.wait()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
        wav_path = fh.name
    try:
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(recording.tobytes())
        result = subprocess.run(
            [str(DICTATE_BIN), "-m", str(DICTATE_MODEL_PATH), "-f", wav_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        transcript = _parse_whisper_output(result.stdout)
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass

    DICTATE_DIR.mkdir(parents=True, exist_ok=True)
    dictation_path = DICTATE_DIR / datetime.datetime.now().strftime(
        "dictation_%Y%m%d_%H%M%S.txt"
    )
    dictation_path.write_text(transcript if transcript else "(empty dictation)")

    message = f"Dictation saved to {dictation_path}"
    if transcript:
        message += f" — {transcript}"
    else:
        message += " (transcript empty)"
    return message


def _parse_whisper_output(stdout: str) -> str:
    """Extract the transcribed text from whisper-cli stdout.

    whisper-cli prints lines like ``[00:00:00.000 --> 00:00:02.000]  text``;
    strip the timestamp prefixes and join the segments with spaces.
    """
    segments = []
    for line in stdout.splitlines():
        line = re.sub(r"^\s*\[[^\]]*\]\s*", "", line).strip()
        if line:
            segments.append(line)
    return " ".join(segments)
