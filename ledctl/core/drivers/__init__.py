from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Tuple


class OutputDevice(ABC):
    """Abstract base class for output devices."""

    @abstractmethod
    def open(self) -> None:
        """Open underlying device resources."""

    @abstractmethod
    def close(self) -> None:
        """Close and cleanup resources."""

    @abstractmethod
    def set_brightness(self, value01: float) -> None:
        """Set brightness in [0.0, 1.0]."""

    @abstractmethod
    def draw_rgb_frame(
        self,
        width: int,
        height: int,
        pixels: Iterable[Tuple[int, int, int]],
    ) -> None:
        """Draw one RGB frame as an iterable of (r,g,b) tuples."""



