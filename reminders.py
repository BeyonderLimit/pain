"""Reminder scheduler for P.A.N. (Phase 3: persistent, runs as a task)."""

from __future__ import annotations

import asyncio
import datetime
import json

from config import REMINDER_FILE


def load() -> list[dict]:
    """Load persisted reminders: [{"time": "YYYY-MM-DD HH:MM", "message": str}, ...]."""
    try:
        data = json.loads(REMINDER_FILE.read_text())
        if isinstance(data, list):
            return [dict(item) for item in data]
    except (OSError, ValueError):
        pass
    return []


def save(reminders_list: list[dict]) -> None:
    """Persist reminders to REMINDER_FILE (temp file + atomic replace)."""
    REMINDER_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = REMINDER_FILE.with_name(REMINDER_FILE.name + ".tmp")
    tmp.write_text(json.dumps(reminders_list, indent=2))
    tmp.replace(REMINDER_FILE)


def add(time_str: str, message: str) -> None:
    """Add and persist a reminder (caller validates the time format)."""
    reminders_list = load()
    reminders_list.append({"time": time_str, "message": message})
    save(reminders_list)


def remove(time_str: str) -> bool:
    """Remove all reminders with the given time; returns True if any were removed."""
    reminders_list = load()
    kept = [r for r in reminders_list if r.get("time") != time_str]
    if len(kept) != len(reminders_list):
        save(kept)
        return True
    return False


async def check_reminders(tts) -> None:
    """Fire due reminders every minute (runs as an asyncio task; never returns)."""
    while True:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        for reminder in list(load()):
            if reminder.get("time") == now:
                message = f"Reminder: {reminder.get('message', '')}"
                print(message)
                await asyncio.to_thread(tts.speak, message)
                remove(now)
        await asyncio.sleep(60)
