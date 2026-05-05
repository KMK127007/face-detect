"""
GET /api/roi/{session_id}          — latest ROI for a session
GET /api/roi/{session_id}/history  — paginated history
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from ..database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["roi"])


@router.get("/roi/{session_id}")
async def get_latest_roi(session_id: str):
    """Return the most recently detected ROI for this session."""
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT frame_index, x, y, width, height, confidence, detected_at
               FROM roi_detections
               WHERE session_id = ?
               ORDER BY frame_index DESC
               LIMIT 1""",
            (session_id,),
        )
        row = await cur.fetchone()
    finally:
        await db.close()

    if row is None:
        raise HTTPException(status_code=404, detail="No ROI data found for this session.")

    return {
        "session_id": session_id,
        "frame_index": row["frame_index"],
        "roi": {
            "x": row["x"],
            "y": row["y"],
            "width": row["width"],
            "height": row["height"],
        },
        "confidence": row["confidence"],
        "detected_at": row["detected_at"],
    }


@router.get("/roi/{session_id}/history")
async def get_roi_history(
    session_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Return paginated ROI history for a session."""
    db = await get_db()
    try:
        # total count
        cur = await db.execute(
            "SELECT COUNT(*) FROM roi_detections WHERE session_id = ?", (session_id,)
        )
        total = (await cur.fetchone())[0]

        cur = await db.execute(
            """SELECT frame_index, x, y, width, height, confidence, detected_at
               FROM roi_detections
               WHERE session_id = ?
               ORDER BY frame_index ASC
               LIMIT ? OFFSET ?""",
            (session_id, limit, offset),
        )
        rows = await cur.fetchall()
    finally:
        await db.close()

    return {
        "session_id": session_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "detections": [
            {
                "frame_index": r["frame_index"],
                "roi": {"x": r["x"], "y": r["y"], "width": r["width"], "height": r["height"]},
                "confidence": r["confidence"],
                "detected_at": r["detected_at"],
            }
            for r in rows
        ],
    }


@router.get("/sessions")
async def list_sessions():
    """List all sessions."""
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT s.session_id, s.started_at, s.ended_at,
                      COUNT(r.id) AS frame_count
               FROM sessions s
               LEFT JOIN roi_detections r ON r.session_id = s.session_id
               GROUP BY s.session_id
               ORDER BY s.started_at DESC
               LIMIT 50"""
        )
        rows = await cur.fetchall()
    finally:
        await db.close()

    return {
        "sessions": [
            {
                "session_id": r["session_id"],
                "started_at": r["started_at"],
                "ended_at": r["ended_at"],
                "frame_count": r["frame_count"],
            }
            for r in rows
        ]
    }