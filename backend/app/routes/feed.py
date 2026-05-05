"""
POST /api/feed/{session_id}
Accepts a raw JPEG frame, runs face detection, persists ROI, stores annotated frame.
"""

import logging
import uuid
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ..database import get_db
from ..detector import detect_and_annotate
from ..store import frame_store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["feed"])

MAX_FRAME_BYTES = 5 * 1024 * 1024   # 5 MB safety cap


@router.post("/feed/{session_id}", status_code=status.HTTP_200_OK)
async def ingest_frame(session_id: str, request: Request):
    """
    Receive a single JPEG frame for the given session.
    - Runs face detection (MediaPipe, no OpenCV).
    - Draws bounding box (Pillow).
    - Stores ROI in SQLite.
    - Pushes annotated frame to the stream store.
    """
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty body; expected JPEG bytes.")
    if len(body) > MAX_FRAME_BYTES:
        raise HTTPException(status_code=413, detail="Frame too large (max 5 MB).")

    # Ensure session row exists
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)", (session_id,)
        )

        # Detect face and annotate frame
        try:
            annotated, roi = detect_and_annotate(body)
        except Exception as exc:
            logger.warning("Detection failed for session %s: %s", session_id, exc)
            raise HTTPException(status_code=422, detail=f"Could not process frame: {exc}")

        # Persist ROI if a face was found
        frame_index: int = 0
        if roi:
            cur = await db.execute(
                "SELECT COUNT(*) FROM roi_detections WHERE session_id = ?", (session_id,)
            )
            row = await cur.fetchone()
            frame_index = row[0]

            await db.execute(
                """INSERT INTO roi_detections (session_id, frame_index, x, y, width, height, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, frame_index, roi.x, roi.y, roi.width, roi.height, roi.confidence),
            )

        await db.commit()
    finally:
        await db.close()

    # Push annotated frame for streaming
    frame_store.put(session_id, annotated)

    return {
        "session_id": session_id,
        "frame_index": frame_index,
        "face_detected": roi is not None,
        "roi": {
            "x": roi.x, "y": roi.y,
            "width": roi.width, "height": roi.height,
            "confidence": roi.confidence,
        } if roi else None,
    }


@router.post("/feed/start/{session_id}", status_code=status.HTTP_201_CREATED)
async def start_session(session_id: str):
    """Explicitly create a session (optional; auto-created on first frame)."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)", (session_id,)
        )
        await db.commit()
    finally:
        await db.close()
    return {"session_id": session_id, "status": "created"}


@router.post("/feed/stop/{session_id}")
async def stop_session(session_id: str):
    """Mark a session as ended."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE sessions SET ended_at = datetime('now') WHERE session_id = ?",
            (session_id,),
        )
        await db.commit()
    finally:
        await db.close()
    frame_store.remove(session_id)
    return {"session_id": session_id, "status": "ended"}