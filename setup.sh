#!/usr/bin/env bash
# P.A.N. — setup script (Phase 1: foundations).
# Usage: ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "== P.A.N. setup (Phase 1: foundations) =="

APT_GET="apt-get"
if [ "$(id -u)" != "0" ]; then APT_GET="sudo apt-get"; fi

install_pkg() { # install_pkg <pkg> [fallback-pkg]
    local pkg=$1 fallback=${2:-}
    if $APT_GET install -y "$pkg" >/dev/null 2>&1; then
        echo "  [ok]   $pkg"
    elif [ -n "$fallback" ] && $APT_GET install -y "$fallback" >/dev/null 2>&1; then
        echo "  [ok]   $pkg (via $fallback)"
    else
        echo "  [warn] $pkg / $fallback: apt install failed (see output above)"
    fi
}

if command -v apt-get >/dev/null 2>&1; then
    $APT_GET update -qq || true
    echo "-- system packages --"
    install_pkg alsa-utils                      # aplay (TTS output)
    install_pkg espeak-ng                       # TTS fallback engine
    install_pkg ffmpeg                          # yt_dlp audio extraction (Phase 4)
    install_pkg libvlc-dev vlc                  # libvlc.so for python-vlc
    install_pkg portaudio19-dev libportaudio-dev  # PortAudio for sounddevice
else
    echo "  [skip] apt-get not available"
fi

echo "-- virtual environment --"
if ! python3 -m venv .venv 2>/dev/null; then
    $APT_GET install -y python3.11-venv
    python3 -m venv .venv
fi

echo "-- pip install -r requirements.txt --"
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "-- Piper TTS: download default voice (config: DEFAULT_VOICE) --"
.venv/bin/python -c "import config, tts; tts.download_voice(config.DEFAULT_VOICE)"

echo "-- Voice memos (Phase 7a): Vosk model --"
.venv/bin/python -c "from voice_recording import ensure_vosk_model; ensure_vosk_model()" || echo "  [warn] Vosk model download failed"

echo "-- Dictation tool (Phase 8): whisper.cpp binary + model --"
.venv/bin/python -c "from dictation import ensure_whisper; ensure_whisper()" || echo "  [warn] whisper.cpp download failed"

echo "-- spaCy model (en_core_web_sm; Phase 2 rewrites get_intent to regexes) --"
.venv/bin/python -m spacy download en_core_web_sm || echo "  [warn] spaCy model download failed"

echo "-- smoke test --"
.venv/bin/python pain.py --smoke

echo "== P.A.N. setup complete =="
