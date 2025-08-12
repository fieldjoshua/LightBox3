from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

from PIL import Image


class Mapper:
    """
    Image transform and device mapping utilities.

    - apply_transforms: rotate/mirror/scale to target size
    - map_for_ws2811: convert a 2D image into a linear sequence
      following a map spec
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._ws_map: List[Dict[str, int]] = []
        try:
            device = str(config.get("device", "")).upper()
            if device in ("WS2811", "WS2811_PI"):
                map_path = config.get("ws2811", {}).get("map_file")
                joined = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    map_path or "",
                )
                if map_path and os.path.exists(joined):
                    # Support both relative to package root and absolute
                    full_path = joined
                else:
                    full_path = map_path or ""
                if full_path and os.path.exists(full_path):
                    with open(full_path, "r", encoding="utf-8") as f:
                        self._ws_map = json.load(f) or []
        except Exception:
            # Non-fatal; mapper can still be used for preview
            self._ws_map = []

    def apply_transforms(self, image: Image.Image) -> Image.Image:
        render = self.config.get("render", {})
        rotate = int(render.get("rotate", 0)) % 360
        mirror_x = bool(render.get("mirror_x", False))
        mirror_y = bool(render.get("mirror_y", False))
        scale = str(render.get("scale", "LANCZOS")).upper()

        # Rotate
        if rotate in (90, 180, 270):
            image = image.rotate(rotate, expand=True)

        # Mirror
        if mirror_x:
            image = image.transpose(Image.FLIP_LEFT_RIGHT)
        if mirror_y:
            image = image.transpose(Image.FLIP_TOP_BOTTOM)

        # Scale to device target if present
        target_w = (
            self.config.get("ws2811", {}).get("width")
            or self.config.get("hub75", {}).get("cols")
        )
        target_h = (
            self.config.get("ws2811", {}).get("height")
            or self.config.get("hub75", {}).get("rows")
        )
        if target_w and target_h:
            resample = Image.LANCZOS if scale == "LANCZOS" else Image.BILINEAR
            image = image.resize(
                (int(target_w), int(target_h)),
                resample=resample,
            )
        return image

    def map_for_ws2811(self, image: Image.Image) -> List[Tuple[int, int, int]]:
        """
        Map a 2D RGB image into a linear GRB/RGB list following
        ws2811.map.json order. If no mapping is loaded, returns pixels
        in row-major order.
        """
        img = image.convert("RGB")
        width, height = img.size
        pixels = img.load()

        ordered: List[Tuple[int, int, int]] = []
        if self._ws_map:
            for entry in self._ws_map:
                x = int(entry.get("x", 0))
                y = int(entry.get("y", 0))
                if 0 <= x < width and 0 <= y < height:
                    ordered.append(pixels[x, y])
        else:
            # Default row-major order
            for y in range(height):
                for x in range(width):
                    ordered.append(pixels[x, y])
        return ordered
