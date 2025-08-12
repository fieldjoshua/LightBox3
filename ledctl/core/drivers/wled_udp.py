from __future__ import annotations

from typing import Any, Dict, Iterable, Tuple

from . import OutputDevice


class WledUdpDriver(OutputDevice):
    """Placeholder WLED UDP driver. Implement in M2."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def open(self) -> None:
        return None

    def close(self) -> None:
        return None

    def set_brightness(self, value01: float) -> None:
        return None

    def draw_rgb_frame(
        self,
        width: int,
        height: int,
        pixels: Iterable[Tuple[int, int, int]],
    ) -> None:
        return None


