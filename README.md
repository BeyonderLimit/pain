# P.A.N. — Personal Assistant, Navigation & news

A personal assistant for Linux: weather, calendar, music (local + YouTube),
news, web search, system controls (stats/volume/brightness/apps), reminders,
chat with a local Ollama model, and voice memos (planned, Phase 7a).

## Setup

```bash
./setup.sh
```

`setup.sh` is idempotent and:

1. Installs system packages (Debian/Ubuntu): `alsa-utils` (provides `aplay`,
   the TTS output device), `espeak-ng` (TTS fallback engine), `ffmpeg`
   (audio extraction for YouTube), `libvlc-dev` + `vlc` (python-vlc — note:
   the `vlc` package is required; `libvlc5` alone is not enough),
   `portaudio19-dev` (sounddevice).
2. Creates the `.venv` virtual environment and runs `pip install -r
   requirements.txt`.
3. Downloads the `en_core_web_sm` spaCy model.
4. Downloads the default Piper voice `en_US-danny-low` into
   `~/.local/share/pain/voices/`.
5. Downloads the Vosk model (`~/.local/share/pain/vosk-model/`, one-time ~40 MB).
6. Downloads the whisper.cpp binary and the `ggml-base.en.bin` model into
   `~/.local/share/pain/dictation/` (one-time ~140 MB).
7. Runs `python pain.py --smoke` — the prerequisite checker.

At any point, `./download_models.sh` (re)downloads the associated models:
the Piper voice, the whisper.cpp binary + model, and the Ollama model
(`ollama pull tinyllama`; requires `ollama serve`).

Requires: Debian/Ubuntu, `sudo` access, network access.

## Run

```bash
.venv/bin/python pain.py
```

The assistant greets you, starts the reminder scheduler, and reads a command
per line. Results are printed and also spoken (TTS via Piper) unless silent
mode is active.

Start with `.venv/bin/python pain.py --silent`, set `config.SPEAK_RESPONSES =
False`, or use the commands below to toggle speech at runtime. Silent mode
suppresses speech only — all text output still appears.

For voice input, hold **Super+Space**, speak, then release. The transcript is
submitted as if you had typed it at the next prompt (including follow-up
prompts such as reminders and chat). This requires X11 (via `pynput`) and a
microphone; on Wayland/headless sessions the listener prints a warning and
typed input continues to work. Set `config.PTT_ENABLED = False` to disable it.

## Commands

| Command | Action |
| --- | --- |
| `exit` / `quit` / `bye` / `goodbye` / `end` | Quit the assistant |
| `stop` / `pause` | Stop music |
| `play` / `play music` | Play a random local file from `MUSIC_DIRS` |
| `play <query>` | Play a matching local file, or fall back to YouTube search |
| `youtube <query>` | Play audio from YouTube |
| `status` / `what's playing?` | What is playing |
| `news` / `headlines` | Fetch headlines (RSS, 3 latest) |
| `search <query>` | DuckDuckGo search (top 5) |
| `weather` / `temperature` / `forecast` | Weather for your location |
| `time` / `clock` | The current time |
| `date` / `today` | Today's date |
| `add entry` / `create …` | Add a calendar entry (summary + type) |
| `schedule` | Today's calendar events |
| `open <app>` / `launch <app>` | Launch an application (`notepad`, `terminal`, `browser`, `file manager` have Linux aliases) |
| `close <app>` / `kill <app>` | Close an application |
| `system stats` / `cpu` / `memory` / `disk` / `uptime` / `battery level` | System stats (including battery when present) |
| `volume up` / `louder` | Volume +5% |
| `volume down` / `quieter` | Volume -5% |
| `brightness up` / `brighter` | Brightness +10% |
| `brightness down` / `darker` | Brightness -10% |
| `reminder <time> <message>` | Set a persistent reminder |
| `chat` | Chat with the local Ollama model |
| `memo` | Record a voice memo (Vosk transcription, saved to `~/.local/share/pain/memos/`) |
| `list notes` / `notes` | List saved voice memos (newest first, with snippets) |
| `cat note <n>` / `read note <n>` | Print a saved memo verbatim (`last`/`latest` also works) |
| `search my notes for <text>` | Search inside saved memos |
| `dictate` | Record a dictation (whisper.cpp transcription, saved to `~/.local/share/pain/dictation/`) |
| `list dictations` | List saved dictations (newest first, with snippets) |
| `cat dictation <n>` / `read dictation <n>` | Print a saved dictation verbatim |
| `search my dictations for <text>` | Search inside saved dictations |
| `Super+Space` (hold) | Push-to-talk: release to submit the transcript as input |
| `help` | Show the command list |
| `files` | Local file search — e.g., "find me .md files locally" |
| `silent mode` / `voice off` / `speech off` / `stop speaking` | Disable spoken responses (text still printed) |
| `voice on` / `speech on` / `speak again` | Re-enable spoken responses |

Unrecognized input gets an apology.

## Configuration (`config.py`)

Everything is a plain constant in `config.py`:

- `LOCATION` — `Location(name, latitude, longitude, timezone)` — used by the
  weather endpoint; set your own city (the HTTP `timezone` should match).
- `CALENDAR_FILE_PATH` — the ICS file read by `schedule` / `add entry`
  (default: Evolution's calendar path; `add_event` writes there too).
- `MUSIC_DIRS` — directories scanned by `play` (default: `~/Music`, `~/Downloads`).
- `OLLAMA_HOST`, `OLLAMA_MODEL` — the local Ollama server and model (`chat`).
- `DEFAULT_VOICE` — the Piper voice used by TTS (`~/.local/share/pain/voices/`).
- `SPEAK_RESPONSES` — default for spoken output; `False` starts every session silent (`--silent` also does this for one run).
- `PTT_ENABLED` — enable the Super+Space push-to-talk listener (default `True`).
- `PTT_SAMPLE_RATE`, `PTT_MAX_DURATION` — capture format and safety cap for push-to-talk.
- `NEWS_SOURCES` — RSS URLs used by `news` (one is picked at random).
- `DATA_DIR` — where pain keeps its data (`~/.local/share/pain`):
  reminders, voice memos, Piper voices.

## Architecture

- `pain.py` — entry point: smoke test + REPL loop (Phase 3).
- `intents.py` — word-boundary regex intent parser (Phase 2).
- `system_controls.py` — system stats/volume/brightness/app launch (Phase 2b).
- `weather.py` / `calendar_io.py` / `music.py` / `news.py` / `search.py` — Phase 4 features.
- `tts.py` — Piper (piper-tts) primary TTS; espeak-ng fallback (the `Dimits`
  package is no longer on PyPI).
- `player.py` — vlc media player wrapper (stop/status/set_pause).
- `reminders.py` — persistent reminder scheduler (Phase 3).
- `voice_recording.py` — Phase 7a: voice memos (Vosk).
- `dictation.py` — Phase 8: dictation tool (whisper.cpp).
- `notes.py` — list, cat, and search saved memos/dictations.
- `ptt.py` — push-to-talk hotkey listener and whisper.cpp transcription.
- `input_hub.py` — queues terminal lines and PTT transcripts for every REPL prompt.

## Tests

```bash
.venv/bin/python -m pytest tests/ -q   # 59 passing tests
```

## Roadmap / known limitations

- Voice memos (`memo`): built (Phase 7a) — Vosk ASR, transcripts saved
  to `~/.local/share/pain/memos/`.
- Dictation: built (Phase 8) — whisper.cpp, transcripts saved to
  `~/.local/share/pain/dictation/`.
- `chat` needs `ollama serve` running; the `tinyllama` model was not pulled
  in this container: `ollama pull tinyllama`.
- News depends on the RSS sources being up; failures are reported as
  "Sorry, I couldn't fetch the latest news at the moment."
