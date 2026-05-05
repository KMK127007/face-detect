"""
GET /api/stream/{session_id}
Server-Sent MJPEG stream of annotated frames.
"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..store import frame_store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stream"])

BOUNDARY = b"--frame"
TIMEOUT_S = 30          # close stream after 30 s with no frames


async def _mjpeg_generator(session_id: str):
    """Yield MJPEG multipart chunks as frames arrive."""
    consecutive_timeouts = 0
    while True:
        frame = await frame_store.next_frame(session_id, timeout=2.0)
        if frame is None:
            consecutive_timeouts += 1
            if consecutive_timeouts >= TIMEOUT_S // 2:
                logger.info("Stream %s timed out, closing.", session_id)
                return
            continue
        consecutive_timeouts = 0
        yield (
            BOUNDARY + b"\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(frame)).encode() + b"\r\n"
            b"\r\n" + frame + b"\r\n"
        )


@router.get("/stream/{session_id}")
async def stream_feed(session_id: str):
    """
    Stream annotated MJPEG frames for the given session.
    Connect a browser <img> src to this URL.
    """
    return StreamingResponse(
        _mjpeg_generator(session_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache"},
    )