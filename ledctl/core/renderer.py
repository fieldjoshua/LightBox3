from __future__ import annotations

import os
import threading
import time
from typing import Dict, Iterable, Optional, Tuple

from PIL import Image

from .drivers import OutputDevice
from .frames import Frame, load_gif, load_image, load_video
from .gamma import apply_gamma_rgb_balance
from .mapper import Mapper
from . import anims


class Renderer:
    """
    Frame rendering service that streams frames from an asset file to an
    `OutputDevice` at controlled pacing. Thread-safe start/stop and live
    parameter updates are supported.
    """

    def __init__(self, device: OutputDevice, config: Dict[str, object]):
        self._device = device
        self._config = config
        self._mapper = Mapper(config)  # uses config for dimensions/transforms
        self._lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._run,
            name="Renderer",
            daemon=True,
        )
        self._run_event = threading.Event()
        self._stop_event = threading.Event()
        self._current_path: Optional[str] = None
        self._latest_image: Optional[Image.Image] = None
        self._builtin_name: Optional[str] = None
        self._builtin_params: Dict[str, object] = {}
        self._stats = {
            "frames": 0,
            "last_draw_ms": 0.0,
            "started_at": 0.0,
        }
        self._thread.start()

    # Public API
    def start(self, path: str) -> None:
        norm = os.path.abspath(path)
        if not os.path.exists(norm) or not os.path.isfile(norm):
            raise FileNotFoundError(f"Asset not found: {path}")
        with self._lock:
            self._current_path = norm
            self._stats = {
                "frames": 0,
                "last_draw_ms": 0.0,
                "started_at": time.time(),
            }
        self._run_event.set()

    def stop(self) -> None:
        self._run_event.clear()
        with self._lock:
            self._current_path = None
            self._builtin_name = None
            self._builtin_params = {}

    def is_running(self) -> bool:
        return self._run_event.is_set()

    def set_render_params(self, render_params: Dict[str, object]) -> None:
        with self._lock:
            cfg_render = self._config.setdefault(
                "render",
                {},
            )  # type: ignore[assignment]
            assert isinstance(cfg_render, dict)
            cfg_render.update(render_params)
            # Rebuild mapper to apply new transform scaling/rotation
            self._mapper = Mapper(self._config)

    def get_latest_image(self) -> Optional[Image.Image]:
        with self._lock:
            return (
                self._latest_image.copy() if self._latest_image else None
            )

    def get_status(self) -> Dict[str, object]:
        with self._lock:
            return {
                "running": self.is_running(),
                "path": self._current_path,
                "builtin": self._builtin_name,
                "frames": self._stats.get("frames", 0),
                "last_draw_ms": round(
                    float(self._stats.get("last_draw_ms", 0.0)),
                    3,
                ),
                "started_at": self._stats.get("started_at", 0.0),
            }

    # Worker
    def _run(self) -> None:
        while not self._stop_event.is_set():
            if not self._run_event.is_set():
                time.sleep(0.02)
                continue

            path: Optional[str]
            with self._lock:
                path = self._current_path

            if not path:
                # Drive builtin animation if selected
                name: Optional[str]
                params: Dict[str, object]
                with self._lock:
                    name = self._builtin_name
                    params = dict(self._builtin_params)
                if not name:
                    time.sleep(0.05)
                    continue
                try:
                    gen = self._open_builtin(name, params)
                    for frame in gen:
                        if not self._run_event.is_set():
                            break
                        self._draw_frame(frame)
                        sleep_ms = self._frame_duration_ms(frame)
                        time.sleep(max(0.0, sleep_ms / 1000.0))
                        if not self._run_event.is_set():
                            break
                    continue
                except Exception:
                    time.sleep(0.1)
                    continue

            try:
                for frame in self._open_frames(path):
                    self._draw_frame(frame)
                    if not self._run_event.is_set():
                        break
                    sleep_ms = self._frame_duration_ms(frame)
                    time.sleep(max(0.0, sleep_ms / 1000.0))
                    if not self._run_event.is_set():
                        break
            except Exception:
                # Swallow to keep thread alive; caller sees status
                time.sleep(0.25)

    def _draw_frame(self, frame: Frame) -> None:
        started = time.perf_counter()
        img = self._mapper.apply_transforms(frame.image)
        gamma = float(
            self._config.get("render", {}).get("gamma", 2.2)
        )  # type: ignore[union-attr]
        rgb_balance = tuple(
            self._config.get("render", {}).get(
                "rgb_balance",
                (1.0, 1.0, 1.0),
            )
        )  # type: ignore[assignment, union-attr]
        img = apply_gamma_rgb_balance(
            img,
            gamma,
            rgb_balance,
        )  # type: ignore[arg-type]

        width, height = img.size
        pixels: Iterable[Tuple[int, int, int]] = img.getdata()
        self._device.draw_rgb_frame(width, height, pixels)

        with self._lock:
            self._latest_image = img.copy()
            self._stats["frames"] = int(self._stats.get("frames", 0)) + 1
            self._stats["last_draw_ms"] = (time.perf_counter() - started) * 1000.0

    def _frame_duration_ms(self, frame: object) -> float:
        # Frame from frames.Frame dataclass with duration_ms attr
        duration_ms = getattr(frame, "duration_ms", None)
        if isinstance(duration_ms, int) and duration_ms and duration_ms > 0:
            return float(duration_ms)
        fps_cap = float(
            self._config.get("render", {}).get("fps_cap", 60)
        )  # type: ignore[union-attr]
        fps_cap = max(1.0, min(240.0, fps_cap))
        return 1000.0 / fps_cap

    def _open_frames(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext in (".gif",):
            return load_gif(path)
        if ext in (".mp4", ".mov", ".mkv", ".avi"):
            return load_video(path)
        return load_image(path)

    def _open_builtin(self, name: str, params: Dict[str, object]):
        w, h = self._target_size()
        if name == "color_cycle":
            return anims.color_cycle(w, h)
        if name == "moving_stripes":
            return anims.moving_stripes(w, h)
        if name == "scrolling_text":
            text = str(params.get("text", "HELLO"))
            return anims.scrolling_text(w, h, text)
        # default: static black
        def _gen():
            img = Image.new("RGB", (w, h), (0, 0, 0))
            while True:
                yield Frame(img.copy(), 100)
        return _gen()

    def _target_size(self) -> Tuple[int, int]:
        w = (
            self._config.get("hub75", {}).get("cols")  # type: ignore[union-attr]
            or self._config.get("ws2811", {}).get("width")  # type: ignore[union-attr]
            or 64
        )
        h = (
            self._config.get("hub75", {}).get("rows")  # type: ignore[union-attr]
            or self._config.get("ws2811", {}).get("height")  # type: ignore[union-attr]
            or 64
        )
        return int(w), int(h)

    def start_builtin(self, name: str, params: Optional[Dict[str, object]] = None) -> None:
        with self._lock:
            self._builtin_name = str(name)
            self._builtin_params = dict(params or {})
            self._current_path = None
            self._stats = {
                "frames": 0,
                "last_draw_ms": 0.0,
                "started_at": time.time(),
            }
        self._run_event.set()
