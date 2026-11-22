"""P.A.N. — Personal Assistant, Navigation & news. Entry point.

Run `./setup.sh` first, then `python pain.py`.
Use `python pain.py --smoke` to check config and system prerequisites.

Phase 1: config + tts + smoke. Phase 2: word-boundary intents. Phase 2b:
system_controls (stats/volume/brightness/apps). Phase 3: REPL loop +
reminders (this module). Phase 4+: weather/calendar/music/YouTube/news/
search/voice memos — see pain-build.md and the project plan.
"""

from __future__ import annotations

import asyncio
import datetime
import shutil
import sys

import calendar_io
import config
import dictation
import files
import music
import news
import notes
import player
import reminders
import search
import system_controls
import tts
import voice_recording
import weather
from input_hub import InputHub
from intents import (
    extract_app_name,
    extract_brightness_direction,
    extract_brightness_level,
    extract_item_query,
    extract_item_selector,
    extract_play_query,
    extract_search_query,
    extract_silent_mode,
    extract_volume_direction,
    extract_volume_level,
    get_intent,
)
from ollama import AsyncClient
from ptt import PushToTalk


# --------------------------------------------------------------------------
# Smoke test (Phase 1)
# --------------------------------------------------------------------------

def _need_cmd(cmd: str) -> None:
    if shutil.which(cmd) is None:
        raise RuntimeError(f"missing system command: {cmd}")


def _piper_ready() -> None:
    if tts.find_piper_command() is None:
        raise RuntimeError("piper unavailable (run ./setup.sh)")
    if not tts.voice_exists(config.DEFAULT_VOICE):
        raise RuntimeError(f"piper voice model missing: {config.DEFAULT_VOICE}")


def _import_vlc():
    import vlc

    instance = vlc.Instance()
    if instance is None:
        raise RuntimeError("vlc.Instance() is None — install the vlc package (apt install vlc)")


def _import_sounddevice():
    import sounddevice  # noqa: F401


def _spacy_model():
    import spacy

    spacy.load("en_core_web_sm")


def smoke() -> int:
    """Print prerequisite checks; return 0 when hard checks pass."""
    ok = True

    def check(name: str, fn) -> None:
        nonlocal ok
        try:
            fn()
            print(f"[ok]   {name}")
        except Exception as e:
            ok = False
            print(f"[FAIL] {name}: {e}")

    print("P.A.N. smoke test (Phase 1)")
    print(
        f"  location : {config.LOCATION.name} "
        f"lat={config.LOCATION.latitude} lon={config.LOCATION.longitude} "
        f"tz={config.LOCATION.timezone}"
    )
    print(f"  calendar : {config.CALENDAR_FILE_PATH} exists={config.CALENDAR_FILE_PATH.exists()}")
    print(f"  music dirs: {[str(d) for d in config.MUSIC_DIRS]}")
    print(f"  ollama   : {config.OLLAMA_HOST} model={config.OLLAMA_MODEL}")
    print(f"  data dir : {config.DATA_DIR}")
    print(f"  tts voice: {config.DEFAULT_VOICE}")
    print()

    check("import config + ensure_dirs()", config.ensure_dirs)
    check("import tts + TTSEngine()", tts.TTSEngine)
    check("system command: aplay", lambda: _need_cmd("aplay"))
    check("system command: ffmpeg", lambda: _need_cmd("ffmpeg"))
    check("piper TTS ready (binary + voice model)", _piper_ready)
    check("import vlc + vlc.Instance()", _import_vlc)
    check("import sounddevice", _import_sounddevice)
    check("spacy model en_core_web_sm", _spacy_model)
    check("system command: espeak-ng (last resort)", lambda: _need_cmd("espeak-ng"))

    print()
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    if "--smoke" in sys.argv:
        return smoke()
    print("P.A.N. — Phase 3: REPL loop + reminder scheduler running.")
    print("Run `python pain.py --smoke` to verify the environment.")
    engine = tts.TTSEngine(enabled="--silent" not in sys.argv)
    try:
        asyncio.run(ai_assistant(engine))
    except KeyboardInterrupt:
        print("\nGoodbye!")
    return 0


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _get_time_of_day() -> str:
    hour = datetime.datetime.now().hour
    if hour < 12:
        return "morning"
    elif hour < 18:
        return "afternoon"
    return "evening"


def _get_date() -> str:
    return datetime.datetime.now().strftime("%A, %B %d, %Y")


def _report(tts, message: str) -> None:
    """Print and speak a result message."""
    print(message)
    tts.speak(message)


# --------------------------------------------------------------------------
# Ollama chat (Phase 3: AsyncClient)
# --------------------------------------------------------------------------

async def chat_with_ollama(prompt: str) -> str:
    """Chats with the local Ollama model via AsyncClient (non-blocking)."""
    try:
        client = AsyncClient(host=config.OLLAMA_HOST)
        response = await client.chat(
            model=config.OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response["message"]["content"]
    except Exception as e:
        print(f"Error chatting with Ollama: {e}")
        return "Sorry, I couldn't connect to the AI."


# --------------------------------------------------------------------------
# Command handlers
# --------------------------------------------------------------------------

def _handle_time(tts) -> None:
    current_time = datetime.datetime.now().strftime("%I:%M %p")
    _report(tts, f"The current time is {current_time}")


def _handle_date(tts) -> None:
    _report(tts, f"Today is {_get_date()}.")


def _handle_status(tts) -> None:
    _report(tts, player.status())


def _handle_play(tts, command: str) -> None:
    query = extract_play_query(command)
    if query:
        _report(tts, music.play_named(query, config.MUSIC_DIRS))
    else:
        _report(tts, music.play_local(config.MUSIC_DIRS))


def _handle_system_stats(tts) -> None:
    _report(tts, system_controls.system_stats())


def _handle_volume(tts, command: str) -> None:
    _report(tts, system_controls.apply_volume(
        extract_volume_direction(command), extract_volume_level(command)
    ))


def _handle_brightness(tts, command: str) -> None:
    _report(tts, system_controls.apply_brightness(
        extract_brightness_direction(command), extract_brightness_level(command)
    ))


def _handle_launch_app(tts, command: str) -> None:
    _report(tts, system_controls.launch_app(extract_app_name(command)))


def _handle_close_app(tts, command: str) -> None:
    _report(tts, system_controls.close_app(extract_app_name(command)))


HELP_TEXT = (
    "Help — P.A.N. commands: weather; schedule; add; time; date; news; play; "
    "status; stop; volume up/down; brightness up/down; open/close apps; "
    "system stats; dictate; memo; list notes; read/cat note; search notes; "
    "list dictations; read/cat dictation; search dictations; reminder; search; files; chat; "
    "silent mode/voice on; exit."
)


def _handle_help(tts) -> None:
    _report(tts, HELP_TEXT)


def _handle_silent_mode(tts, command: str) -> None:
    action = extract_silent_mode(command)
    if action == "on":
        tts.set_enabled(True)
        message = "Voice responses on."
    elif action == "off":
        tts.set_enabled(False)
        message = "Voice responses off."
    else:
        tts.set_enabled(not tts.enabled)
        message = f"Voice responses {'on' if tts.enabled else 'off'}."
    _report(tts, message)


def _handle_files(tts, command: str) -> None:
    pattern = files.extract_file_pattern(command)
    paths = files.search_files(pattern)
    if not paths:
        _report(tts, f"No files found matching {pattern}.")
        return
    shown = [str(p) for p in paths[:10]]
    message = f"Files matching {pattern} ({len(paths)} found): " + "; ".join(shown)
    if len(paths) > 10:
        message += f"; ... and {len(paths) - 10} more"
    _report(tts, message)


# Saved transcripts are printed verbatim; speaking a whole note is rarely useful.
def _handle_list_notes(tts, command: str) -> None:
    print(notes.format_list("note"))


def _handle_list_dictations(tts, command: str) -> None:
    print(notes.format_list("dictation"))


def _handle_read_note(tts, command: str) -> None:
    print(notes.cat_item("note", extract_item_selector(command)))


def _handle_read_dictation(tts, command: str) -> None:
    print(notes.cat_item("dictation", extract_item_selector(command)))


def _handle_search_notes(tts, command: str) -> None:
    print(notes.search_items("note", extract_item_query(command)))


def _handle_search_dictations(tts, command: str) -> None:
    print(notes.search_items("dictation", extract_item_query(command)))


async def _handle_weather(tts) -> None:
    _report(tts, await weather.get_weather(config.LOCATION))


def _handle_schedule(tts) -> None:
    events = calendar_io.get_events_today(config.CALENDAR_FILE_PATH)
    if events:
        _report(tts, "Your schedule for today includes: " + "; ".join(events))
    else:
        _report(tts, "You have no events scheduled for today.")


def _handle_news(tts) -> None:
    headlines = news.fetch_news()
    if headlines:
        for headline in headlines:
            _report(tts, f"Latest news: {headline}")
    else:
        _report(tts, "Sorry, I couldn't fetch the latest news at the moment.")


def _handle_search(tts, query: str) -> None:
    _report(tts, f"Searching for: {query}...")
    results = search.search_web(query)
    if not results:
        _report(tts, "No results found.")
        return
    parts = []
    for r in results:
        part = r.get("title", "")
        body = r.get("body", "")
        if body:
            part = f"{part} — {body[:100]}"
        parts.append(part)
    _report(tts, "Search results: " + " | ".join(parts))


async def _handle_reminder(tts, hub: InputHub) -> None:
    print("Setting a reminder...")
    tts.speak("Setting a reminder...")
    reminder_time_str = await hub.read("Enter the reminder time (YYYY-MM-DD HH:MM): ")
    reminder_message = await hub.read("Enter the reminder message: ")
    try:
        datetime.datetime.strptime(reminder_time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        _report(tts, "Invalid date format. Please use YYYY-MM-DD HH:MM.")
        return
    reminders.add(reminder_time_str, reminder_message)
    _report(tts, f"Reminder set for {reminder_time_str}: {reminder_message}")


# --------------------------------------------------------------------------
# REPL loop (Phase 3)
# --------------------------------------------------------------------------

async def ai_assistant(tts) -> None:
    """Main REPL loop: greet, start the reminder scheduler, dispatch commands."""
    hub = InputHub()
    hub.start()
    ptt = None
    if config.PTT_ENABLED:
        def announce(message: str) -> None:
            # Start on a fresh line so PTT status never overwrites "Enter your command:".
            print(f"\n{message}", flush=True)

        ptt = PushToTalk(on_transcript=hub.push, announce=announce)
        if not ptt.start():
            ptt = None

    print(f"Good {_get_time_of_day()}!")
    tts.speak(f"Good {_get_time_of_day()}!")

    date = _get_date()
    print(f"Today is {date}.")
    tts.speak(f"Today is {date}.")

    reminder_task = asyncio.create_task(reminders.check_reminders(tts))
    try:
        while True:
            print("I'm ready for your command.")
            tts.speak("I'm ready for your command.")
            try:
                command = await hub.read("Enter your command: ")
            except EOFError:
                print("Goodbye!")
                tts.speak("Goodbye!")
                break

            intent = get_intent(command)
            if intent == "exit":
                print("Goodbye!")
                tts.speak("Goodbye!")
                break
            elif intent == "stop_music":
                _report(tts, player.stop())
            elif intent == "time":
                _handle_time(tts)
            elif intent == "date":
                _handle_date(tts)
            elif intent == "status":
                _handle_status(tts)
            elif intent == "system_stats":
                _handle_system_stats(tts)
            elif intent == "volume":
                _handle_volume(tts, command)
            elif intent == "brightness":
                _handle_brightness(tts, command)
            elif intent == "launch_app":
                _handle_launch_app(tts, command)
            elif intent == "close_app":
                _handle_close_app(tts, command)
            elif intent == "reminder":
                await _handle_reminder(tts, hub)
            elif intent == "list_notes":
                _handle_list_notes(tts, command)
            elif intent == "list_dictations":
                _handle_list_dictations(tts, command)
            elif intent == "read_note":
                _handle_read_note(tts, command)
            elif intent == "read_dictation":
                _handle_read_dictation(tts, command)
            elif intent == "search_notes":
                _handle_search_notes(tts, command)
            elif intent == "search_dictations":
                _handle_search_dictations(tts, command)
            elif intent == "memo":
                _report(tts, await asyncio.to_thread(voice_recording.record_memo))
            elif intent == "dictate":
                _report(tts, await asyncio.to_thread(dictation.record_dictation))
            elif intent == "chat":
                prompt = await hub.read("Enter your message for the AI: ")
                response = await chat_with_ollama(prompt)
                print("AI response:", response)
                tts.speak(response)
            elif intent == "add_entry":
                summary = await hub.read("Enter the summary of the entry: ")
                entry_type = await hub.read(
                    "Enter the type of entry (todo, reminder, appointment): "
                )
                start_time = datetime.datetime.now()
                end_time = start_time + datetime.timedelta(hours=1)
                ok = await asyncio.to_thread(
                    calendar_io.add_event,
                    config.CALENDAR_FILE_PATH, summary, start_time, end_time, entry_type,
                )
                if ok:
                    _report(tts, f"Added {entry_type} entry: {summary}")
                else:
                    _report(tts, "Failed to add calendar entry.")
            elif intent == "schedule":
                _handle_schedule(tts)
            elif intent == "weather":
                await _handle_weather(tts)
            elif intent == "play_music":
                _handle_play(tts, command)
            elif intent == "youtube":
                query = await hub.read("Enter the YouTube search query: ")
                _report(tts, music.play_youtube(query))
            elif intent == "news":
                _handle_news(tts)
            elif intent == "silent_mode":
                _handle_silent_mode(tts, command)
            elif intent == "help":
                _handle_help(tts)
            elif intent == "files":
                _handle_files(tts, command)
            elif intent == "search":
                query = extract_search_query(command) or await hub.read(
                    "What do you want to search for? "
                )
                _handle_search(tts, query)
            else:
                message = "I'm sorry, I didn't understand that command."
                _report(tts, message)
    finally:
        if ptt is not None:
            ptt.stop()
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass
        player.stop()


if __name__ == "__main__":
    sys.exit(main())
