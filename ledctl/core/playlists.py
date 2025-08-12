from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PlaylistState:
    items: List[str] = field(default_factory=list)
    index: int = 0
    loop: bool = True


class PlaylistManager:
    """Minimal playlist state manager with JSON persistence."""

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.state = PlaylistState()
        self._load()

    def _load(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.state = PlaylistState(
                    items=list(data.get("items", [])),
                    index=int(data.get("index", 0)),
                    loop=bool(data.get("loop", True)),
                )
        except Exception:
            # Non-fatal; start fresh
            self.state = PlaylistState()

    def _save(self) -> None:
        # Best-effort persistence; bubble exceptions to caller for logging
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.state.__dict__, f, indent=2)

    def set_items(self, items: List[str], loop: bool = True) -> None:
        self.state.items = list(items)
        self.state.index = 0
        self.state.loop = bool(loop)
        self._save()

    def current(self) -> Optional[str]:
        if not self.state.items:
            return None
        if 0 <= self.state.index < len(self.state.items):
            return self.state.items[self.state.index]
        return None

    def next(self) -> Optional[str]:
        if not self.state.items:
            return None
        self.state.index += 1
        if self.state.index >= len(self.state.items):
            if self.state.loop:
                self.state.index = 0
            else:
                self.state.index = len(self.state.items) - 1
        self._save()
        return self.current()


