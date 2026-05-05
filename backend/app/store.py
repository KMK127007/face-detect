"""
Shared in-memory store for the latest annotated frame per session.
Keeps only the most recent frame to minimise memory usage.
"""

from __future__ import annotations
import asyncio
from collections import defaultdict
from typing import Optional


class FrameStore:
    def __init__(self):
        self._frames: dict[str, bytes] = {}
        self._events: dict[str, asyncio.Event] = defaultdict(asyncio.Event)

    def put(self, session_id: str, frame: bytes):
        self._frames[session_id] = frame
        self._events[session_id].set()
        self._events[session_id].clear()

    async def next_frame(self, session_id: str, timeout: float = 5.0) -> Optional[bytes]:
        """Wait for the next frame; returns None on timeout."""
        try:
            await asyncio.wait_for(self._events[session_id].wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        return self._frames.get(session_id)

    def latest(self, session_id: str) -> Optional[bytes]:
        return self._frames.get(session_id)

    def remove(self, session_id: str):
        self._frames.pop(session_id, None)
        self._events.pop(session_id, None)


frame_store = FrameStore()