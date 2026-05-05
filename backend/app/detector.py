"""
Face detection using MediaPipe.
Draws bounding box using Pillow only — no OpenCV.
"""

from __future__ import annotations
import io
import logging
from dataclasses import dataclass
from typing import Optional

import mediapipe as mp
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

_face_detection = mp.solutions.face_detection.FaceDetection(
    model_selection=0, min_detection_confidence=0.5
)

BOX_COLOR = (0, 255, 80)       # bright green
BOX_WIDTH = 3
LABEL_COLOR = (0, 255, 80)
LABEL_BG = (0, 0, 0, 160)


@dataclass
class FaceROI:
    x: int
    y: int
    width: int
    height: int
    confidence: float


def detect_and_annotate(jpeg_bytes: bytes) -> tuple[bytes, Optional[FaceROI]]:
    """
    Detect a face in a JPEG frame, draw an axis-aligned bounding box,
    and return annotated JPEG bytes + ROI data.
    No OpenCV used anywhere in this pipeline.
    """
    img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    w, h = img.size

    # MediaPipe expects RGB numpy array
    import numpy as np
    rgb = np.array(img)
    results = _face_detection.process(rgb)

    roi: Optional[FaceROI] = None

    if results.detections:
        det = results.detections[0]          # single face assumption
        bb = det.location_data.relative_bounding_box
        score = det.score[0]

        # Convert relative coords → absolute pixel coords
        x = max(0, int(bb.xmin * w))
        y = max(0, int(bb.ymin * h))
        box_w = min(int(bb.width * w), w - x)
        box_h = min(int(bb.height * h), h - y)

        roi = FaceROI(x=x, y=y, width=box_w, height=box_h, confidence=float(score))

        # Draw axis-aligned bounding box with Pillow (no OpenCV)
        draw = ImageDraw.Draw(img)
        x2, y2 = x + box_w, y + box_h
        for offset in range(BOX_WIDTH):
            draw.rectangle(
                [x - offset, y - offset, x2 + offset, y2 + offset],
                outline=BOX_COLOR,
            )

        # Label
        label = f"face {score:.0%}"
        try:
            from PIL import ImageFont
            font = ImageFont.load_default()
        except Exception:
            font = None

        label_x, label_y = x, max(0, y - 18)
        draw.text((label_x + 1, label_y + 1), label, fill=(0, 0, 0), font=font)
        draw.text((label_x, label_y), label, fill=LABEL_COLOR, font=font)

    # Re-encode to JPEG
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue(), roi