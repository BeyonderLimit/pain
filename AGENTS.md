# AGENTS.md — P.A.N. (Personal Assistant, Navigation & news)

## Commands / verification

- Prefer `.venv/bin/python` (all scripts and the README use it). This is a flat, package-less Python repo — no `pyproject.toml`, no `src/`. Ad-hoc `python -c`/REPL imports need the repo root as cwd because modules use bare imports (`import config`, `import weather`).
- `./setup.sh` is the full bootstrap: apt packages, `.venv`, runtime requirements, Piper/Vosk/whisper/spaCy assets, then `.venv/bin/python pain.py --smoke`.
- It does **not** install `requirements-dev.txt`; in a fresh venv run `.venv/bin/python -m pip install -r requirements-dev.txt` before pytest.
- Checks: `.venv/bin/python pain.py --smoke` (system prerequisites, exit 0/1) and `.venv/bin/python -m pytest tests/ -q`. No lint, typecheck, codegen, or CI config exists.
- `python-vlc` needs the `vlc` apt package (not just `libvlc5`); smoke's `vlc.Instance()` check catches that.
- `./download_models.sh` is models-only (Piper voice, whisper.cpp + model, `ollama pull` of `config.OLLAMA_MODEL`). `chat` needs `ollama serve` running; smoke does not check Ollama.
- `--silent` starts with speech off; `config.SPEAK_RESPONSES` is the default. Runtime `silent mode` / `voice off` / `speech off` / `stop speaking` (or `voice on` / `speak again`) toggle `TTSEngine.enabled`; printed output is never suppressed.
- Super+Space PTT: `ptt.PushToTalk` uses pynput/X11 + sounddevice + whisper.cpp; transcripts go through `input_hub.InputHub` into every REPL prompt (no keystroke injection into other apps). It fails soft without X11; `config.PTT_ENABLED` disables it. Announcements start with `\n` so they don't overwrite the pending prompt.
- `play <query>` goes through `music.play_named` (local filename match, then YouTube); bare `play`/`play music` stays random. `system_controls._APP_ALIASES` maps names like `notepad` to available Linux apps, and `battery level` is a system stat, not a web search.
- `notes.py` serves saved memos/dictations: `list notes`, `cat note <n>`, `search my notes for <text>`, and the `dictation` equivalents are deterministic intents that must stay before generic `memo`/`dictate`/`search`/`list` rules. `notes` snapshots `MEMOS_DIR`/`DICTATE_DIR` at import.

## Gotchas

- `pain.py` is the only entrypoint (`--smoke` or REPL); feature modules are top-level files. `pain-build.md` is a large archive of older monolithic prototypes, not the current architecture or source of truth.
- `intents.py` rules are ordered and first match wins; specific before general. `tests/test_intents.py` locks in past substring misfires (`news`/`new`, `update`/`date`, `display`/`play`) — don't reorder rules casually.
- Several modules snapshot config values at import (`from config import REMINDER_FILE`, `FILES_SEARCH_ROOTS`, etc.). Monkeypatch the consuming module's attribute (`reminders.REMINDER_FILE`), not `config.REMINDER_FILE`.
- Persistent state lives outside the repo in `~/.local/share/pain` (reminders, voices, Vosk/whisper models, memos/dictations); user-specific paths and location are constants in `config.py`.
- Search uses the `ddgs` package; the old `duckduckgo_search` import emits a RuntimeWarning. Keep `search.py` and `requirements.txt` on `ddgs`.
- Tests mock all HTTP/RSS/DuckDuckGo calls; no network is needed. `test_music.py` uses fake `.mp3` files, so VLC prints demux errors to stderr while pytest still passes.
