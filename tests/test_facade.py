"""Facade tests: every behavior draws valid frames for its full duration."""

import math

import pytest

from chat54 import facade
from chat54.display import Frame, Color

ROWS, COLS = Frame.DISPLAY_ROWS, Frame.DISPLAY_COLS


def frame_is_black(f: Frame) -> bool:
    return all(f[r][c] == Color(0, 0, 0) for r in range(ROWS) for c in range(COLS))


def test_registry_complete():
    assert set(facade.BEHAVIORS) == {
        "breathe", "listen", "wave", "blush", "confetti", "grumble",
        "dance", "bow", "goodnight", "heartbeat", "look", "story",
        "countdown",
    }


def test_countdown_draws_three_digits_then_goes_dark():
    fn = facade.BEHAVIORS["countdown"]
    dur = fn.duration_ms / 1000
    hold = facade.DIGIT_HOLD_S
    lit_per_step = []
    for center in (0.4,):                      # mid-hold of each digit
        for step in range(3):
            f = Frame()
            fn(f, step * (hold + facade.DIGIT_GAP_S) + center)
            lit = sum(1 for r in range(ROWS) for c in range(COLS)
                      if (f[r][c].r, f[r][c].g, f[r][c].b) != (0, 0, 0))
            lit_per_step.append(lit)
    assert all(n > 8 for n in lit_per_step), lit_per_step   # each digit visible
    # after the last digit the show is over (director handles chaining)
    f = Frame()
    fn(f, dur + 0.05)
    lit = sum(1 for r in range(ROWS) for c in range(COLS)
              if (f[r][c].r, f[r][c].g, f[r][c].b) != (0, 0, 0))
    assert lit == 0


@pytest.mark.parametrize("name", sorted(facade.BEHAVIORS))
def test_behavior_draws_colorful_frames(name):
    fn = facade.BEHAVIORS[name]
    dur = fn.duration_ms / 1000
    seen_color = False
    steps = 12
    for i in range(steps):
        t = dur * i / steps
        f = Frame()
        fn(f, t)
        assert f.nrows() == ROWS and f.ncols() == COLS
        for r in range(ROWS):
            for c in range(COLS):
                col = f[r][c]
                assert 0 <= col.r <= 255 and 0 <= col.g <= 255 and 0 <= col.b <= 255
                if (col.r, col.g, col.b) != (0, 0, 0):
                    seen_color = True
    assert seen_color, f"{name} never lit a single window"


@pytest.mark.parametrize("name", ["wave", "blush", "heartbeat", "bow"])
def test_behavior_returns_to_quiet(name):
    """Animations should finish mostly dark so the loop back to idle is clean."""
    fn = facade.BEHAVIORS[name]
    f = Frame()
    fn(f, fn.duration_ms / 1000 + 0.05)
    lit = sum(
        1
        for r in range(ROWS)
        for c in range(COLS)
        if (f[r][c].r, f[r][c].g, f[r][c].b) != (0, 0, 0)
    )
    assert lit < ROWS * COLS * 0.5, f"{name} still mostly lit after finishing"


def test_get_unknown_raises():
    with pytest.raises(KeyError):
        facade.get("does-not-exist")
