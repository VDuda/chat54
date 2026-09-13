"""Facade behavior library.

A "behavior" is a named light show on the 17x9 grid. Each behavior exposes
duration_ms and draw(frame, t) where t is seconds since the behavior started.
Behaviors only ever write Color cells into a Frame — they never touch the
display, the network, or the simulator — so this layer is verbatim-portable
to the real building.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .display import Frame, Color

ROWS = Frame.DISPLAY_ROWS   # 17
COLS = Frame.DISPLAY_COLS   # 9


# --- color helpers -----------------------------------------------------------

def lerp(a: float, b: float, k: float) -> float:
    return a + (b - a) * k


def mix(c1: Color, c2: Color, k: float) -> Color:
    return Color(lerp(c1.r, c2.r, k), lerp(c1.g, c2.g, k), lerp(c1.b, c2.b, k))


def scale(c: Color, k: float) -> Color:
    return Color(c.r * k, c.g * k, c.b * k)


def hsv(h: float, s: float = 1.0, v: float = 1.0) -> Color:
    h = h % 1.0
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = [
        (v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q),
    ][i]
    return Color(r * 255, g * 255, b * 255)


def fadeout(t: float, dur: float, frac: float = 0.25) -> float:
    """Brightness envelope: 1 for most of the show, ease to 0 in the last `frac`."""
    p = t / dur
    if p >= 1.0:
        return 0.0
    return min(1.0, (1.0 - p) / frac) if frac > 0 else 1.0


def warm(k: float = 1.0) -> Color:
    return Color(255 * k, 120 * k, 40 * k)


def cool(k: float = 1.0) -> Color:
    return Color(60 * k, 140 * k, 255 * k)


def pink(k: float = 1.0) -> Color:
    return Color(255 * k, 90 * k, 140 * k)


# --- behavior base -----------------------------------------------------------

@dataclass
class BehaviorResponse:
    """What the facade should perform for one chat reply."""
    name: str
    duration_ms: int
    draw_fn: object          # callable(frame, t_seconds)
    label: str = ""          # human-readable, shown in chat metadata


def behavior(duration_ms: int, label: str = ""):
    def deco(fn):
        fn.duration_ms = duration_ms
        fn.label = label
        return fn
    return deco


def response_from(fn) -> BehaviorResponse:
    return BehaviorResponse(fn.__name__.replace("draw_", ""),
                            fn.duration_ms, fn, getattr(fn, "label", ""))


# --- idle behaviors ----------------------------------------------------------

@behavior(4_000, "the building breathes")
def draw_breathe(f: Frame, t: float) -> None:
    """Dim aurora slowly pulsing; the default idle. Tint is mood-driven."""
    phase = (math.sin(2 * math.pi * t / 4.0) + 1) / 2          # 0..1, 4s cycle
    for r in range(ROWS):
        for c in range(COLS):
            w = 0.5 + 0.5 * math.sin(2 * math.pi * (0.08 * r - 0.06 * c + t / 4.0))
            v = 0.10 + 0.10 * w * (0.6 + 0.4 * phase)
            f[r][c] = hsv(0.62 - 0.05 * w, 0.55, v)


@behavior(4_000, "listening")
def draw_listen(f: Frame, t: float) -> None:
    """Soft cool shimmer: the building is paying attention."""
    for r in range(ROWS):
        for c in range(COLS):
            w = 0.5 + 0.5 * math.sin(2 * math.pi * (t * 1.2) + 0.4 * (r - c))
            f[r][c] = scale(cool(), 0.10 + 0.08 * w)


# --- triggered behaviors -----------------------------------------------------

@behavior(3_200, "waves back at you")
def draw_wave(f: Frame, t: float) -> None:
    """A friendly diagonal sweep that rolls up the facade and back down."""
    dur = draw_wave.duration_ms / 1000
    p = t / dur                                                # 0..1
    sweep = math.sin(math.pi * p)                              # up then down
    for r in range(ROWS):
        for c in range(COLS):
            d = abs((r / ROWS) - sweep)
            v = max(0.0, 1.0 - d * 3.2)
            if v > 0:
                f[r][c] = scale(hsv(0.52 + 0.02 * c, 0.7, 1.0), v)


@behavior(3_000, "blushes")
def draw_blush(f: Frame, t: float) -> None:
    """A shy pink bloom that starts at the heart and spreads upward."""
    dur = draw_blush.duration_ms / 1000
    p = min(1.0, t / dur)
    radius = p * 1.15
    heart_r, heart_c = 12, 4
    for r in range(ROWS):
        for c in range(COLS):
            d = math.hypot((r - heart_r) / ROWS, (c - heart_c) / COLS * 1.8)
            v = max(0.0, 1.0 - d / max(radius, 1e-6))
            v = v ** 1.4
            f[r][c] = scale(pink(), v * (0.75 + 0.25 * math.sin(t * 6)) * fadeout(t, dur))


@behavior(3_400, "celebrates")
def draw_confetti(f: Frame, t: float) -> None:
    """Party: colorful cells sparkle and pop upward, then rain down."""
    dur = draw_confetti.duration_ms / 1000
    p = t / dur
    rng = math_rng()
    env = 0.5 - 0.5 * math.cos(2 * math.pi * p)            # smooth 0->1->0
    for r in range(ROWS):
        for c in range(COLS):
            # deterministic per-cell random phase
            s = rng((r, c))
            tw = 0.5 + 0.5 * math.sin(2 * math.pi * (t * 2.0 + s * 7.0))
            v = tw * env
            if v > 0.08:
                f[r][c] = hsv(s + t * 0.1, 0.9, v)


def math_rng():
    """Tiny deterministic hash -> [0,1) keyed by cell coords."""
    def h(key):
        r, c = key
        x = math.sin(12.9898 * (r * 97 + c * 131) + 4.1414) * 43758.5453
        return x - math.floor(x)
    return h


@behavior(3_400, "grumbles")
def draw_grumble(f: Frame, t: float) -> None:
    """Stormy: dark red flicker rising from the ground floors."""
    dur = draw_grumble.duration_ms / 1000
    p = t / dur
    for r in range(ROWS):
        for c in range(COLS):
            flick = 0.5 + 0.5 * math.sin(2 * math.pi * (t * 7.0) + r * 2.1 + c * 0.7)
            base = max(0.0, 1.0 - r / ROWS)                    # brighter at bottom
            v = base * flick * (1 - 0.4 * p)
            f[r][c] = scale(Color(200, 40, 30), v)


@behavior(3_600, "dances")
def draw_dance(f: Frame, t: float) -> None:
    """Dance mode: equalizer columns bouncing to an imaginary beat."""
    dur = draw_dance.duration_ms / 1000
    for c in range(COLS):
        beat = abs(math.sin(2 * math.pi * (t * 1.5) + c * 0.9))
        height = int(beat * (ROWS - 1)) + 1
        for r in range(ROWS):
            if r >= ROWS - height:
                k = 1.0 - (ROWS - 1 - r) / max(height, 1) * 0.6
                f[r][c] = scale(hsv(0.12 + 0.05 * (c % 3), 0.85, 1.0), k * fadeout(t, dur))


@behavior(3_000, "takes a bow")
def draw_bow(f: Frame, t: float) -> None:
    """A single bright column pulse — 'at your service'."""
    dur = draw_bow.duration_ms / 1000
    p = t / dur
    pulse = math.sin(math.pi * p) ** 2
    for r in range(ROWS):
        for c in range(COLS):
            edge = max(abs(c - 4) / 4.0, abs(r - 8) / 8.0)
            v = pulse * max(0.0, 1.0 - edge * 2.2)
            f[r][c] = scale(Color(255, 250, 210), v)


@behavior(3_600, "settles for the night")
def draw_goodnight(f: Frame, t: float) -> None:
    """Lights dim floor by floor; one window stays on, winks, then off."""
    dur = draw_goodnight.duration_ms / 1000
    p = t / dur
    cutoff = int(p * (ROWS + 2))
    for r in range(ROWS):
        for c in range(COLS):
            if r < cutoff - 2:
                continue                                        # already dark
            w = 0.5 + 0.5 * math.sin(2 * math.pi * (t + r * 0.2))
            if cutoff - 2 <= r < cutoff:
                f[r][c] = scale(warm(), 0.25 * w)
            else:
                f[r][c] = scale(hsv(0.6, 0.4, 1.0), 0.10 + 0.06 * w)
    # the famous last window: warm and bright near the end, then gone
    if p > 0.88:
        wink = math.sin(math.pi * min(1.0, (p - 0.88) / 0.12))
        f[1][4] = scale(warm(), 0.55 * wink)


@behavior(3_200, "hums a heart-beat")
def draw_heartbeat(f: Frame, t: float) -> None:
    """Two-thump heartbeat pulse in warm white."""
    dur = draw_heartbeat.duration_ms / 1000
    p = t / dur
    thump = max(
        math.exp(-((p - 0.15) ** 2) / 0.004),
        0.6 * math.exp(-((p - 0.45) ** 2) / 0.004),
    )
    for r in range(ROWS):
        for c in range(COLS):
            d = abs((r - 8) / 8.0) + abs((c - 4) / 4.0) * 0.5
            v = thump * max(0.0, 1.0 - d)
            f[r][c] = scale(Color(255, 80, 90), v)


@behavior(3_200, "looks over here")
def draw_look(f: Frame, t: float) -> None:
    """A scanning 'eye': a bright band travels toward the side mentioned."""
    dur = draw_look.duration_ms / 1000
    p = t / dur
    # sweep 0 -> 1 then bounce back
    sweep = p if p < 0.5 else 1 - p
    center = sweep * (COLS - 1)
    for r in range(ROWS):
        for c in range(COLS):
            d = abs(c - center)
            v = max(0.0, 1.0 - d * 0.9)
            f[r][c] = scale(cool(), v * (0.4 + 0.6 * (r / ROWS)) * fadeout(t, dur))


@behavior(4_000, "tells you its story")
def draw_story(f: Frame, t: float) -> None:
    """A slow rainbow rolls up the tower: the building showing off its age."""
    dur = draw_story.duration_ms / 1000
    for r in range(ROWS):
        for c in range(COLS):
            v = (0.30 + 0.18 * math.sin(2 * math.pi * (t * 0.8 + r * 0.1))) * fadeout(t, dur)
            f[r][c] = hsv((r / ROWS) * 0.5 + t * 0.15 + c * 0.01, 0.75, v)


# --- brightness tuning -------------------------------------------------------

# Per-behavior gain, tuned against the simulator viewer (its renderer applies
# a canvas core-lift plus GPU bloom, so dim content reads brighter than raw
# and hot content blooms). Values from measured luminance: peaks target the
# 150-200 range for shows, 20-25 for idle.
FACADE_GAIN = {
    "breathe": 0.60,     # idle should whisper: mean 23 -> 14
    "listen": 0.75,
    "wave": 0.85,
    "blush": 1.40,       # shy but visible: peak 128 -> 179
    "confetti": 0.85,
    "grumble": 1.60,     # anger must read: peak 72 -> 115
    "dance": 0.70,       # was flooding the facade (mean 86 -> 60)
    "bow": 0.80,         # was near full white (peak 248 -> 198)
    "goodnight": 1.00,
    "heartbeat": 1.40,   # thumps were faint (peak 109 -> 153)
    "look": 1.35,        # scanning band was half-asleep
    "story": 0.85,
}


def gain_for(name: str) -> float:
    return FACADE_GAIN.get(name, 1.0)


# --- registry ----------------------------------------------------------------

BEHAVIORS = {
    "breathe": draw_breathe,
    "listen": draw_listen,
    "wave": draw_wave,
    "blush": draw_blush,
    "confetti": draw_confetti,
    "grumble": draw_grumble,
    "dance": draw_dance,
    "bow": draw_bow,
    "goodnight": draw_goodnight,
    "heartbeat": draw_heartbeat,
    "look": draw_look,
    "story": draw_story,
}


def get(name: str) -> object:
    fn = BEHAVIORS.get(name)
    if fn is None:
        raise KeyError(f"unknown behavior: {name}")
    return fn
