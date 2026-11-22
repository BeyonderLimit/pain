"""Calendar I/O via icalendar (Phase 4: robust parsing + atomic writes)."""

from __future__ import annotations

import datetime
from pathlib import Path

from icalendar import Calendar, Event


def get_events_today(ics_file_path) -> list[str]:
    """Return summaries of events starting today from an ICS file."""
    try:
        with open(ics_file_path, "rb") as file:
            cal = Calendar.from_ical(file.read())
    except FileNotFoundError:
        print(f"Calendar file not found: {ics_file_path}")
        return []
    except Exception as e:
        print(f"Error reading calendar file: {e}")
        return []

    today = datetime.date.today()
    events = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        dtstart = component.get("dtstart")
        if dtstart is None or getattr(dtstart, "dt", None) is None:
            continue
        event_date = dtstart.dt
        if isinstance(event_date, datetime.datetime):
            event_date = event_date.date()
        if event_date == today:
            summary = component.get("summary")
            if summary is not None:
                events.append(str(summary))
    return events


def add_event(ics_file_path, summary, start_time, end_time, entry_type) -> bool:
    """Add an event to an ICS file. Returns True on success."""
    try:
        if Path(ics_file_path).is_file():
            with open(ics_file_path, "rb") as file:
                cal = Calendar.from_ical(file.read())
        else:
            cal = Calendar()

        event = Event()
        event.add("summary", summary)
        event.add("dtstart", start_time)
        event.add("dtend", end_time)
        event.add("categories", entry_type)
        cal.add_component(event)

        # Atomic write: temp file + replace.
        path = Path(ics_file_path)
        tmp_path = path.with_name(path.name + ".tmp")
        tmp_path.write_bytes(cal.to_ical())
        tmp_path.replace(path)
        return True
    except Exception as e:
        print(f"Error adding calendar entry: {e}")
        return False
