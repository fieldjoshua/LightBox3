from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Generator, Optional

import cv2  # type: ignore
from PIL import Image, ImageSequence


@dataclass
class Frame:
    """A video frame with optional duration (in milliseconds)."""

    image: Image.Image
    duration_ms: Optional[int] = None


def load_image(path: str) -> Generator[Frame, None, None]:
    """Yield a single RGB frame from a static image file."""
    try:
        im = Image.open(path).convert("RGB")
        yield Frame(im, None)
    except Exception as exc:
        raise RuntimeError(f"Failed to load image: {path}") from exc


def load_gif(path: str) -> Generator[Frame, None, None]:
    """Yield frames from an animated GIF with their durations if present."""
    try:
        im = Image.open(path)
        for frame in ImageSequence.Iterator(im):
            duration = frame.info.get("duration")  # ms
            yield Frame(
                frame.convert("RGB"),
                int(duration) if duration else None,
            )
    except Exception as exc:
        raise RuntimeError(f"Failed to load gif: {path}") from exc


def load_video(path: str) -> Generator[Frame, None, None]:
    """
    Yield frames from a video using OpenCV.
    Duration per frame is derived from FPS.
    """
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {path}")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        duration_ms = int(1000.0 / max(1.0, fps))
        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break
            # Convert BGR -> RGB and to Pillow Image
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            yield Frame(
                Image.fromarray(frame_rgb),
                duration_ms,
            )
    except Exception as exc:
        raise RuntimeError(f"Failed to decode video: {path}") from exc
    finally:
        with contextlib.suppress(Exception):
            cap.release()


