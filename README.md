# FaceTrack — Face Detection API

A containerised face-detection pipeline that receives a video feed, detects faces using **MediaPipe** (no OpenCV), stores ROI data in **SQLite**, annotates frames using **Pillow**, and streams the result back to a live browser frontend.

---

## Quick Start (< 5 minutes)

**Prerequisites:** Docker ≥ 24, Docker Compose v2

```bash
git clone <repo-url> face-detect
cd face-detect
docker compose up --build
```

Open **http://localhost:3000** in your browser, enter a session ID, and click **Start**.

> The first build downloads MediaPipe (~150 MB). Subsequent builds use the layer cache.

---

## Architecture

```
Browser
  │  (MJPEG stream + REST)
  ▼
┌─────────────────────────────────────────┐
│  frontend container  (nginx :80→3000)   │
│  Serves index.html, proxies /api/*      │
└────────────────┬────────────────────────┘
                 │ HTTP proxy  /api/*
                 ▼
┌─────────────────────────────────────────┐
│  backend container  (uvicorn :8000)     │
│                                         │
│  POST /api/feed/{session_id}            │  ← JPEG frame in
│    → MediaPipe detect                   │
│    → Pillow annotate (bounding box)     │
│    → SQLite store ROI                   │
│    → FrameStore.put(annotated_jpeg)     │
│                                         │
│  GET  /api/stream/{session_id}          │  → MJPEG multipart stream
│    ← FrameStore async generator         │
│                                         │
│  GET  /api/roi/{session_id}             │  → latest ROI JSON
│  GET  /api/roi/{session_id}/history     │  → paginated ROI history
│  GET  /api/sessions                     │  → session list
│                                         │
│  SQLite  /data/face_detect.db           │
│  ├── sessions (session_id, timestamps)  │
│  └── roi_detections (x,y,w,h,conf,…)   │
└─────────────────────────────────────────┘
         │ Docker named volume
         ▼
     face_data (persistent SQLite file)
```

---

## API Reference

### Ingest a frame

```
POST /api/feed/{session_id}
Content-Type: image/jpeg
Body: <raw JPEG bytes>

200 OK
{
  "session_id": "live-01",
  "frame_index": 42,
  "face_detected": true,
  "roi": { "x": 120, "y": 80, "width": 200, "height": 220, "confidence": 0.97 }
}
```

### MJPEG stream

```
GET /api/stream/{session_id}
→ multipart/x-mixed-replace; boundary=frame
```

Point an `<img>` src here. Works in all major browsers.

### Latest ROI

```
GET /api/roi/{session_id}

200 OK
{
  "session_id": "live-01",
  "frame_index": 42,
  "roi": { "x": 120, "y": 80, "width": 200, "height": 220 },
  "confidence": 0.97,
  "detected_at": "2024-06-01 12:34:56"
}
```

### ROI history

```
GET /api/roi/{session_id}/history?limit=100&offset=0

200 OK
{ "session_id": "…", "total": 310, "limit": 100, "offset": 0, "detections": [ … ] }
```

### Session management

```
POST /api/feed/start/{session_id}   → 201 Created
POST /api/feed/stop/{session_id}    → 200 OK
GET  /api/sessions                  → list of sessions
GET  /health                        → {"status": "ok"}
```

---

## Key Design Decisions

| Concern | Choice | Reason |
|---|---|---|
| Face detection | MediaPipe | Free, fast, no OpenCV dependency |
| Bounding box drawing | Pillow | Pure-Python, no OpenCV |
| Database | SQLite + aiosqlite | Zero-config, relational, ideal for single-server |
| Streaming | MJPEG multipart | Native browser support, no JS library needed |
| Frame transport | JPEG POST | Simple, stateless, works from any client |
| API framework | FastAPI | Async, typed, OpenAPI docs auto-generated |

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

---

## Database Schema

```sql
CREATE TABLE sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL UNIQUE,
    started_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    ended_at    TEXT
);

CREATE TABLE roi_detections (
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
```

---

## Security Notes

- Frame size capped at 5 MB per request.
- CORS configured (restrict `allow_origins` in production).
- SQLite foreign keys enabled; parameterised queries throughout.
- No secrets required; extend with API key header for production use.

---

## Stopping

```bash
docker compose down          # stop containers
docker compose down -v       # also remove the SQLite volume
```
