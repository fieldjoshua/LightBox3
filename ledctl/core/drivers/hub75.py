from __future__ import annotations
from typing import Any, Dict, Iterable, Optional, Tuple
from . import OutputDevice


class Hub75Driver(OutputDevice):
    """
    HUB75 output driver using rpi-rgb-led-matrix.

    This module avoids importing the rgbmatrix library at import time to keep
    development on non-Linux hosts working. The import happens inside `open()`.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config: Dict[str, Any] = config
        self._matrix: Optional[object] = None
        self._canvas: Optional[object] = None
        self._width: int = int(
            (config.get("hub75", {}) or {}).get("cols")
            or (config.get("ws2811", {}) or {}).get("width")
            or 0
        )
        self._height: int = int(
            (config.get("hub75", {}) or {}).get("rows")
            or (config.get("ws2811", {}) or {}).get("height")
            or 0
        )

    def open(self) -> None:
        try:
            # Lazy import to avoid dependency on non-Linux dev machines.
            # If import fails, try appending path from RGBMATRIX_PATH env var
            # (e.g., ~/rpi-rgb-led-matrix/bindings/python).
            try:
                from rgbmatrix import (
                    RGBMatrix,
                    RGBMatrixOptions,
                )  # type: ignore
            except Exception:
                import os as _os
                import sys as _sys
                extra = _os.environ.get("RGBMATRIX_PATH", "").strip()
                if (
                    extra
                    and _os.path.isdir(extra)
                    and extra not in _sys.path
                ):
                    _sys.path.append(extra)
                # Retry import after updating sys.path
                from rgbmatrix import (
                    RGBMatrix,
                    RGBMatrixOptions,
                )  # type: ignore

            hub = self.config.get("hub75", {}) or {}

            options = RGBMatrixOptions()
            # Dimensions
            options.rows = int(hub.get("rows", 64))
            options.cols = int(hub.get("cols", 64))
            # Chain/parallel tiling
            try:
                options.chain_length = int(hub.get("chain_length", 1))
            except Exception:
                options.chain_length = 1
            try:
                options.parallel = int(hub.get("parallel", 1))
            except Exception:
                options.parallel = 1
            # Hardware specifics
            if hub.get("hardware_mapping"):
                options.hardware_mapping = str(hub.get("hardware_mapping"))
            if hub.get("gpio_slowdown") is not None:
                options.gpio_slowdown = int(hub.get("gpio_slowdown"))
            if hub.get("pixel_mapper_config"):
                options.pixel_mapper_config = str(
                    hub.get("pixel_mapper_config")
                )
            if hub.get("panel_type"):
                options.panel_type = str(hub.get("panel_type"))

            matrix = RGBMatrix(options=options)
            canvas = matrix.CreateFrameCanvas()
            # Initial brightness (0-100)
            initial_brightness = int(hub.get("brightness", 85))
            try:
                matrix.brightness = max(0, min(100, initial_brightness))
            except Exception:
                # Not all versions expose brightness as a property
                pass

            self._matrix = matrix
            self._canvas = canvas
            # Cache width/height from device (some setups tile panels)
            try:
                self._width = int(canvas.width)
                self._height = int(canvas.height)
            except Exception:
                # Fallback to configured values
                self._width = int(options.cols)
                self._height = int(options.rows)
        except Exception as exc:  # pragma: no cover - hw-specific
            raise RuntimeError(f"HUB75 open failed: {exc}") from exc

    def close(self) -> None:
        try:
            # Best-effort cleanup; library doesn't require explicit close
            self._canvas = None
            self._matrix = None
        except Exception:
            # Never raise from close path
            return None

    def set_brightness(self, value01: float) -> None:
        try:
            if not self._matrix:
                return None
            value01 = max(0.0, min(1.0, float(value01)))
            brightness_0100 = int(round(value01 * 100.0))
            try:
                # rgbmatrix exposes brightness 0..100
                setattr(self._matrix, "brightness", brightness_0100)
            except Exception:
                # Ignore if unsupported
                pass
        except Exception:
            # Do not propagate minor brightness errors
            return None

    def draw_rgb_frame(
        self,
        width: int,
        height: int,
        pixels: Iterable[Tuple[int, int, int]],
    ) -> None:
        if not self._matrix or not self._canvas:
            # Allow calls before open() to no-op safely
            return None

        # Normalize dimensions: if mismatch, draw the overlapping region
        target_w = int(self._width) if self._width else int(width)
        target_h = int(self._height) if self._height else int(height)
        draw_w = min(int(width), target_w)
        draw_h = min(int(height), target_h)

        # Draw pixels onto offscreen canvas, then swap on vsync
        try:
            # The canvas API uses SetPixel(x, y, r, g, b)
            data = list(pixels)
            idx = 0
            for y in range(draw_h):
                for x in range(draw_w):
                    try:
                        r, g, b = data[idx]
                    except Exception:
                        r, g, b = 0, 0, 0
                    idx += 1
                    # type: ignore[attr-defined]
                    self._canvas.SetPixel(
                        int(x),
                        int(y),
                        int(r),
                        int(g),
                        int(b),
                    )  # pragma: no cover

            # Swap buffer to screen
            # type: ignore[attr-defined]
            self._canvas = self._matrix.SwapOnVSync(
                self._canvas
            )  # pragma: no cover
        except Exception as exc:  # pragma: no cover - hw-specific
            raise RuntimeError(f"HUB75 draw failed: {exc}") from exc


