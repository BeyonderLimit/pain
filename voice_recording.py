"""Voice memos (Phase 7a): record mic audio and transcribe with Vosk."""

from __future__ import annotations

import datetime
import io
import json
import shutil
import zipfile
from pathlib import Path
from urllib.request import urlopen

import sounddevice as sd
import vosk

from config import MEMOS_DIR, VOSK_MODEL_PATH

# The small US model (Apache 2.0) from HuggingFace (alphacep/vosk-api models).
VOSK_MODEL_URL = (
    "https://huggingface.co/ambind/vosk-model-small-en-us-0.15/resolve/main/"
    "vosk-model-small-en-us-0.15_c_.zip"
)
VOSK_MODEL_SAMPLE_RATE = 16000
DEFAULT_DURATION = 5.0  # seconds of audio to record per memo


def ensure_vosk_model() -> None:
    """Download and extract the Vosk model if it is missing."""
    if _model_ok():
        return
    VOSK_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Vosk model to {VOSK_MODEL_PATH} (one time, ~40 MB)...")
    with urlopen(VOSK_MODEL_URL, timeout=180) as response:
        with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
            names = archive.namelist()
            archive.extractall(VOSK_MODEL_PATH.parent)
            top = names[0].split("/")[0]
    extracted = VOSK_MODEL_PATH.parent / top
    if extracted != VOSK_MODEL_PATH:
        if VOSK_MODEL_PATH.exists():
            shutil.rmtree(VOSK_MODEL_PATH)
        extracted.replace(VOSK_MODEL_PATH)
    if not _model_ok():
        raise RuntimeError(
            f"Vosk model missing after download — expected at {VOSK_MODEL_PATH}"
        )


def _model_ok() -> bool:
    try:
        return (VOSK_MODEL_PATH / "am").is_dir()
    except OSError:
        return False


def record_memo(duration: float = DEFAULT_DURATION) -> str:
    """Record a voice memo, save the transcript as a text file, and return
    a human-readable message. Never raises (failures become messages)."""
    try:
        return _record_memo(duration)
    except Exception as e:
        return f"Voice memo failed: {e}"


def _record_memo(duration: float) -> str:
    ensure_vosk_model()
    model = vosk.Model(str(VOSK_MODEL_PATH))
    recognizer = vosk.KaldiRecognizer(model, VOSK_MODEL_SAMPLE_RATE)

    frames = int(duration * VOSK_MODEL_SAMPLE_RATE)
    recording = sd.rec(
        frames, samplerate=VOSK_MODEL_SAMPLE_RATE, channels=1, dtype="int16"
    )
    sd.wait()

    transcript = _transcribe(recognizer, recording)

    memo_path = MEMOS_DIR / datetime.datetime.now().strftime("memo_%Y%m%d_%H%M%S.txt")
    memo_path.parent.mkdir(parents=True, exist_ok=True)
    memo_path.write_text(transcript if transcript else "(empty memo)")

    message = f"Memo saved to {memo_path}"
    if transcript:
        message += f" — {transcript}"
    else:
        message += " (transcript empty)"
    return message


def _transcribe(recognizer: vosk.KaldiRecognizer, recording) -> str:
    """Feed a recorded ndarray through the recognizer, returning the text."""
    data = recording.tobytes()
    text = []
    chunk = 4096
    for i in range(0, len(data), chunk):
        piece = data[i : i + chunk]
        if not piece:
            break
        if recognizer.AcceptWaveform(piece):
            text.append(str(json.loads(recognizer.Result()).get("text", "")))
    text.append(str(json.loads(recognizer.FinalResult()).get("text", "")))
    return " ".join(t for t in text if t).strip()
