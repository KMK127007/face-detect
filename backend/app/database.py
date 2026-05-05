"""
Database layer using SQLite (via aiosqlite).
Stores per-frame ROI detections.
"""

import aiosqlite
import os

DB_PATH = os.environ.get("DB_PATH", "/data/face_detect.db")

CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL UNIQUE,
    started_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    ended_at    TEXT
);
"""

CREATE_ROI_TABLE = """
CREATE TABLE IF NOT EXISTS roi_detections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL REFERENCES sessions(session_id),
    frame_index INTEGER NOT NULL,
    x           INTEGER NOT NULL,
    y           INTEGER NOT NULL,
    width       INTEGER NOT NULL,
    height      INTEGER NOT NULL,
    confidence  REAL    NOT NULL,
    detected_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_roi_session_frame
ON roi_detections (session_id, frame_index);
"""


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA foreign_keys=ON;")
    return db


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys=ON;")
        await db.execute(CREATE_SESSIONS_TABLE)
        await db.execute(CREATE_ROI_TABLE)
        await db.execute(CREATE_INDEX)
        await db.commit()