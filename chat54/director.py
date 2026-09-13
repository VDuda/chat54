"""The director: turns chat events into a continuous 30 fps stream of frames.

Owns two things:

1. **Mood** — a persistent scalar (grumpy -3 .. giddy +3) fed by the energy of
   every reply, decaying slowly toward neutral. Mood tints the idle behavior
   and is exposed for the building's self-image.
2. **Performance** — when a reply arrives, its behavior plays for its duration
   with a short crossfade from whatever is on screen, then the director falls
   back to idle (breathe, mood-tinted).

Fast attack, slow release: behavior starts within one frame of the message;
mood takes a minute to cool down. That asymmetry is what makes it feel alive.
"""

from __future__ import annotations

import math
import time

from . import facade
from .display import Frame, Color

ROWS, COLS = Frame.DISPLAY_ROWS, Frame.DISPLAY_COLS
CROSSFADE_MS = 500


def _tint(c: Color, hue_shift: float, sat: float) -> Color:
    """Rudimentary tint: scale channels toward a mood color."""
    m = facade.hsv(hue_shift, sat, 1.0)
    return Color((c.r * 0.6 + m.r * 0.4),
                 (c.g * 0.6 + m.g * 0.4),
                 (c.b * 0.6 + m.b * 0.4))


class Director:
    def __init__(self):
        self.mood = 0.0                     # -3..+3, 0 = chill
        self._current = facade.get("breathe")
        self._started = time.monotonic()
        self._prev: dict | None = None      # {fn, start} for crossfade

    # --- events ---------------------------------------------------------------

    def on_reply(self, behavior_name: str, energy: int) -> None:
        fn = facade.get(behavior_name)
        now = time.monotonic()
        # snapshot current frame as the fade source
        src = self.render_frame(now)
        self._prev = {"fn": self._current, "frame": src,
                      "fade_end": now + CROSSFADE_MS / 1000}
        self._current = fn
        self._started = now
        # mood: fast attack toward the energy, slow release handled in tick
        target = max(-3.0, min(3.0, self.mood + energy * 0.8))
        self.mood = target * 0.7 + self.mood * 0.3

    # --- per-frame --------------------------------------------------------------

    def tick(self, dt: float) -> None:
        """Slow decay of mood toward neutral."""
        decay = 0.02 * dt                   # full cooldown in ~a minute
        if abs(self.mood) > 0.01:
            self.mood -= math.copysign(min(decay, abs(self.mood)), self.mood)

    def render_frame(self, now: float | None = None) -> Frame:
        now = now if now is not None else time.monotonic()
        f = Frame()
        t = now - self._started

        if self._current is facade.get("breathe"):
            self._draw_idle_tinted(f, t)
        else:
            self._current(f, t)
            # behavior finished -> back to idle
            if t * 1000 >= self._current.duration_ms:
                self._current = facade.get("breathe")
                self._started = now

        if self._prev is not None:
            fade_k = max(0.0, (self._prev["fade_end"] - now)) / (CROSSFADE_MS / 1000)
            if fade_k <= 0:
                self._prev = None
            else:
                self._blend(f, self._prev["frame"], fade_k)
        return f

    def _draw_idle_tinted(self, f: Frame, t: float) -> None:
        facade.get("breathe")(f, t)
        if self.mood >= 0.3:
            k = min(1.0, self.mood / 3.0)
            for r in range(ROWS):
                for c in range(COLS):
                    f[r][c] = _tint(f[r][c], 0.95 - 0.1 * (1 - k), 0.35 + 0.3 * k)
        elif self.mood <= -0.3:
            k = min(1.0, -self.mood / 3.0)
            for r in range(ROWS):
                for c in range(COLS):
                    f[r][c] = _tint(f[r][c], 0.02, 0.35 + 0.3 * k)

    @staticmethod
    def _blend(f: Frame, old: Frame, keep_old: float) -> None:
        for r in range(ROWS):
            for c in range(COLS):
                a, b = old[r][c], f[r][c]
                f[r][c] = Color(a.r * keep_old + b.r * (1 - keep_old),
                                a.g * keep_old + b.g * (1 - keep_old),
                                a.b * keep_old + b.b * (1 - keep_old))
