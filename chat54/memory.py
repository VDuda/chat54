"""Per-user memory with JSON persistence.

Keeps the building's sense of relationship: sentiment (likes/dislikes),
interaction counts, and tallies of particular message kinds.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field


@dataclass
class UserInfo:
    visits: int = 0
    sentiment: int = 0
    total_messages: int = 0
    counts: dict = field(default_factory=dict)
    last_seen: float = 0.0


class Memory:
    def __init__(self, path: str = "chat54_memory.json"):
        self.path = path
        self._users: dict[str, UserInfo] = {}
        self._lock = threading.Lock()
        self._load()

    # --- public API ----------------------------------------------------------

    def visit(self, user: str) -> int:
        """Count this visit and return the visit number (1 = first time)."""
        with self._lock:
            info = self._users.setdefault(user, UserInfo())
            info.visits += 1
            info.total_messages += 1
            info.last_seen = time.time()
            self._save()
            return info.visits

    def add_sentiment(self, user: str, delta: int) -> None:
        with self._lock:
            info = self._users.setdefault(user, UserInfo())
            info.sentiment += delta
            self._save()

    def count_kind(self, user: str, kind: str) -> int:
        """Count messages of a kind (call after incrementing, so first is 1)."""
        with self._lock:
            info = self._users.setdefault(user, UserInfo())
            info.counts[kind] = info.counts.get(kind, 0) + 1
            self._save()
            return info.counts[kind]

    def mood_summary(self) -> dict:
        with self._lock:
            total_sent = sum(u.sentiment for u in self._users.values())
            return {"sentiment": total_sent, "users": len(self._users)}

    # --- persistence -----------------------------------------------------------

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path) as f:
                raw = json.load(f)
            for name, d in raw.items():
                self._users[name] = UserInfo(**d)
        except Exception:
            # corrupted memory is sad but not fatal; the building moves on
            self._users = {}

    def _save(self) -> None:
        try:
            with open(self.path, "w") as f:
                json.dump({n: vars(u) for n, u in self._users.items()}, f)
        except Exception:
            pass
