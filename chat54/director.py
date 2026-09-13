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
        self._idle_started = time.monotonic()   # idle phase runs continuously
        self._prev: dict | None = None      # {fn, start} for crossfade
        self._queued = None                 # show chained after a countdown

    # --- events ---------------------------------------------------------------

    def on_reply(self, behavior_name: str, energy: int) -> None:
        """Immediately perform a behavior (chat-triggered shows don't wait)."""
        self._start_show(facade.get(behavior_name), now=None)
        # mood: fast attack toward the energy, slow release handled in tick
        target = max(-3.0, min(3.0, self.mood + energy * 0.8))
        self.mood = target * 0.7 + self.mood * 0.3

    def perform_after_countdown(self, behavior_name: str, energy: int = 0) -> None:
        """Play 3-2-1 on the facade, then the queued behavior starts itself.

        Used for ambient changes: anticipation first, then the reveal.
        The energy is applied when the countdown starts, so the mood is
        already leaning where the room pushed it while the digits show.
        """
        self._queued = facade.get(behavior_name)
        self.on_reply("countdown", energy)

    def _start_show(self, fn, now) -> None:
        now = now if now is not None else time.monotonic()
        src = self.render_frame(now)          # snapshot as the crossfade source
        self._prev = {"frame": src, "fade_end": now + CROSSFADE_MS / 1000}
        self._current = fn
        self._started = now

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
        breathe = facade.get("breathe")

        if self._current is breathe:
            # idle phase never resets: returning from a show continues the
            # breathing cycle where it would have been, so no phase jump
            self._draw_idle_tinted(f, now - self._idle_started)
        else:
            self._current(f, t)
            self._apply_gain(f, self._current.__name__.replace("draw_", ""))
            # behavior finished -> queued show next (countdown chaining),
            # otherwise back to idle
            if t * 1000 >= self._current.duration_ms:
                nxt, self._queued = self._queued, None
                if nxt is not None:
                    self._start_show(nxt, now)
                else:
                    self._current = breathe
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
        self._apply_gain(f, "breathe")

    @staticmethod
    def _apply_gain(f: Frame, name: str) -> None:
        g = facade.gain_for(name)
        if g == 1.0:
            return
        for r in range(ROWS):
            for c in range(COLS):
                col = f[r][c]
                f[r][c] = Color(col.r * g, col.g * g, col.b * g)

    @staticmethod
    def _blend(f: Frame, old: Frame, keep_old: float) -> None:
        for r in range(ROWS):
            for c in range(COLS):
                a, b = old[r][c], f[r][c]
                f[r][c] = Color(a.r * keep_old + b.r * (1 - keep_old),
                                a.g * keep_old + b.g * (1 - keep_old),
                                a.b * keep_old + b.b * (1 - keep_old))
