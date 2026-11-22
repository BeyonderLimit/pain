"""System controls for P.A.N. (Phase 2b): stats, volume, brightness, apps.

Handlers used by the REPL loop (Phase 3). All commands are best-effort:
they return human-readable strings describing what happened (or why not).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


def system_stats() -> str:
    """Return a one-line summary of memory/CPU/uptime/disk usage (Linux)."""
    parts: list[str] = []
    mem = _read_meminfo()
    total = mem.get("MemTotal")
    if total:
        available = mem.get("MemAvailable", 0)
        used = total - available
        parts.append(f"memory {_gb(used)} used of {_gb(total)}")
    cpu = _cpu_busy_ratio()
    if cpu is not None:
        parts.append(f"cpu {cpu:.0%} busy")
    uptime = _uptime_hours()
    if uptime is not None:
        parts.append(f"uptime {uptime:.1f} h")
    disk = _root_disk_usage()
    if disk is not None:
        used, total_disk = disk
        parts.append(f"disk {_gb(used)} used of {_gb(total_disk)}")
    battery = _battery_level()
    if battery is not None:
        parts.append(f"battery {battery}%")
    if not parts:
        return "System stats unavailable."
    return "System stats: " + "; ".join(parts) + "."


def _gb(bytes_value: int) -> str:
    return f"{bytes_value / 1e9:.1f} GB"


def _read_meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, rest = line.partition(":")
                if key in ("MemTotal", "MemAvailable", "MemFree"):
                    values[key] = int(rest.strip().split()[0]) * 1024  # kB -> bytes
    except (OSError, ValueError, IndexError):
        pass
    return values


def _cpu_busy_ratio() -> float | None:
    """CPU busy ratio since boot (from the first /proc/stat line)."""
    try:
        with open("/proc/stat") as f:
            fields = f.readline().split()
        if len(fields) < 5 or fields[0] != "cpu":
            return None
        nums = [float(x) for x in fields[1:]]
        total = sum(nums)
        if total <= 0:
            return None
        return (total - nums[3]) / total  # busy = total - idle
    except (OSError, ValueError, IndexError):
        return None


def _uptime_hours() -> float | None:
    try:
        return float(Path("/proc/uptime").read_text().split()[0]) / 3600
    except (OSError, ValueError, IndexError):
        return None


def _root_disk_usage() -> tuple[int, int] | None:
    try:
        usage = shutil.disk_usage("/")
        return usage.used, usage.total
    except OSError:
        return None


def _battery_level() -> int | None:
    for capacity in sorted(Path("/sys/class/power_supply").glob("BAT*/capacity")):
        try:
            return int(capacity.read_text().strip())
        except (OSError, ValueError):
            continue
    return None


# --- Volume (via amixer from alsa-utils) ---


def _run_amixer(args: list[str]) -> str:
    result = subprocess.run(["amixer", *args], capture_output=True, text=True, timeout=15)
    return result.stdout


def _volume_current() -> str:
    try:
        out = _run_amixer(["get", "Master"])
        levels = re.findall(r"(\d+)%", out)
        if levels:
            return f"Volume is at {levels[0]}%."
        return "Volume level unavailable."
    except Exception as e:
        return f"Couldn't read volume: {e}"


def apply_volume(direction: str, level: int | None = None) -> str:
    """Apply a volume command: absolute ``level``, or direction up/down/mute."""
    try:
        if level is not None:
            level = max(0, min(100, level))
            _run_amixer(["set", "Master", f"{level}%"])
        elif direction == "up":
            _run_amixer(["set", "Master", "5%+"])
        elif direction == "down":
            _run_amixer(["set", "Master", "5%-"])
        elif direction in ("mute", "unmute"):
            _run_amixer(["set", "Master", "toggle"])
        return _volume_current()
    except Exception as e:
        return f"Couldn't change volume: {e}"


# --- Brightness (via /sys/class/backlight) ---


def _brightness_devices() -> list[Path]:
    try:
        return [
            device / "brightness"
            for device in sorted(Path("/sys/class/backlight").iterdir())
            if (device / "brightness").is_file()
        ]
    except OSError:
        return []


def apply_brightness(direction: str, level: int | None = None) -> str:
    """Apply a brightness command: absolute ``level`` %, or direction up/down."""
    devices = _brightness_devices()
    if not devices:
        return "No screen brightness control found."
    if level is not None:
        level = max(0, min(100, level))
        changed = False
        for device in devices:
            try:
                max_brightness = int((device.parent / "max_brightness").read_text().strip())
                device.write_text(str(max_brightness * level // 100))
                changed = True
            except (OSError, ValueError):
                continue
        if not changed:
            return "Couldn't change brightness (write permission needed?)."
    elif direction:
        delta_pct = 10 if direction == "up" else -10
        changed = False
        for device in devices:
            try:
                max_brightness = int((device.parent / "max_brightness").read_text().strip())
                current = int(device.read_text().strip())
                new = max(1, min(max_brightness, current + max_brightness * delta_pct // 100))
                device.write_text(str(new))
                changed = True
            except (OSError, ValueError):
                continue
        if not changed:
            return "Couldn't change brightness (write permission needed?)."
    # Report current level.
    try:
        levels = []
        for device in devices:
            max_brightness = int((device.parent / "max_brightness").read_text().strip())
            levels.append(round(int(device.read_text().strip()) * 100 / max_brightness))
        return f"Brightness is at {levels[0]}%."
    except (OSError, ValueError, ZeroDivisionError):
        return "Brightness updated."


# --- App launch/close (via Popen / pkill) ---


_APP_ALIASES = {
    "notepad": ("featherpad", "mousepad", "gedit", "kate", "pluma", "leafpad"),
    "text editor": ("featherpad", "mousepad", "gedit", "kate", "pluma", "leafpad"),
    "terminal": ("lxterminal", "xfce4-terminal", "gnome-terminal", "konsole", "xterm"),
    "browser": ("firefox", "chromium", "google-chrome", "google-chrome-stable"),
    "file manager": ("thunar", "nautilus", "pcmanfm", "dolphin"),
}


def launch_app(app: str) -> str:
    """Launch an application by name or common alias (detached)."""
    name = (app or "").strip()
    if not name:
        return "No application name given."
    candidates = _APP_ALIASES.get(name.lower(), (name,))
    for candidate in candidates:
        if shutil.which(candidate) is None:
            continue
        try:
            proc = subprocess.Popen(
                [candidate],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return f"Launched {candidate} (pid {proc.pid})."
        except Exception as e:
            return f"Couldn't launch {candidate}: {e}"
    tried = ", ".join(candidates)
    return f"Couldn't launch {name}: not found on PATH (tried {tried})."


def close_app(app: str) -> str:
    """Close (kill) applications matching a name with pkill."""
    name = (app or "").strip()
    if not name:
        return "No application name given."
    try:
        result = subprocess.run(["pkill", "-f", name], capture_output=True, timeout=10)
    except FileNotFoundError:
        return "pkill not available."
    except Exception as e:
        return f"Couldn't close {name}: {e}"
    if result.returncode == 0:
        return f"Closed {name}."
    return f"No process matched {name}."
