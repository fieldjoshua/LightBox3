from __future__ import annotations

import threading
from typing import Iterable, Tuple

from PIL import Image

from . import OutputDevice


class NullPreviewDriver(OutputDevice):
    """
    Preview driver that stores the latest frame in memory for UI preview.
    """

    def __init__(self, device_name: str = "PREVIEW") -> None:
        self.device_name = device_name
        self._brightness: float = 1.0
        self._lock = threading.Lock()
        self._latest_image: Image.Image | None = None

    def open(self) -> None:
        return None

    def close(self) -> None:
        with self._lock:
            self._latest_image = None

    def set_brightness(self, value01: float) -> None:
        value = max(0.0, min(1.0, float(value01)))
        self._brightness = value

    def draw_rgb_frame(
        self,
        width: int,
        height: int,
        pixels: Iterable[Tuple[int, int, int]],
    ) -> None:
        img = Image.new("RGB", (int(width), int(height)))
        img.putdata(list(pixels))
        with self._lock:
            self._latest_image = img

    def get_latest_image(self) -> Image.Image | None:
        with self._lock:
            return self._latest_image.copy() if self._latest_image else None


