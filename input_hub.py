"""Async line input from the terminal or push-to-talk transcripts.

A single daemon thread drains stdin into an asyncio queue, so a PTT transcript
can satisfy a pending prompt without leaving a second reader on stdin.
"""

from __future__ import annotations

import asyncio
import sys
import threading

_EOF = object()


class InputHub:
    """Queue terminal lines and PTT transcripts for ``await read(prompt)``."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[str | object] = asyncio.Queue()
        self._thread = threading.Thread(target=self._stdin_worker, daemon=True)
        self._started = False

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        return self._loop

    def start(self) -> None:
        """Begin reading stdin; call from inside a running event loop."""
        if self._started:
            return
        self._ensure_loop()
        self._started = True
        self._thread.start()

    def _stdin_worker(self) -> None:
        try:
            for line in sys.stdin:
                self._loop.call_soon_threadsafe(
                    self._queue.put_nowait, line.rstrip("\r\n")
                )
        finally:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, _EOF)

    def push(self, text: str) -> None:
        """Enqueue a PTT transcript as if the user had typed it."""
        text = text.strip()
        if not text:
            return
        self._ensure_loop().call_soon_threadsafe(self._queue.put_nowait, text)

    async def read(self, prompt: str = "") -> str:
        """Print ``prompt`` and return the next terminal line or transcript."""
        if prompt:
            print(prompt, end="", flush=True)
        item = await self._queue.get()
        if item is _EOF:
            raise EOFError
        return str(item)
