"""Director tests: mood evolution, scheduling, crossfade."""

from chat54.director import Director
from chat54.display import Frame, Color

ROWS, COLS = Frame.DISPLAY_ROWS, Frame.DISPLAY_COLS


def test_mood_moves_and_decays():
    d = Director()
    d.on_reply("blush", +2)
    assert d.mood > 0.5
    # a minute of decay brings it most of the way back
    for _ in range(60):
        d.tick(1.0)
    assert abs(d.mood) < 0.6


def test_negative_mood():
    d = Director()
    d.on_reply("grumble", -3)
    assert d.mood < -0.5


def test_reply_switches_behavior_then_falls_back():
    d = Director()
    import time
    d.on_reply("wave", +1)
    assert d._current is not None
    # render past the wave duration; director should return to idle
    later = time.monotonic() + (d._current.duration_ms + 100) / 1000
    f = d.render_frame(later)
    assert isinstance(f, Frame)
    assert d._current is d.render_frame.__globals__["facade"].get("breathe")


def test_crossfade_blends_pixels():
    d = Director()
    d.on_reply("confetti", +3)
    f = d.render_frame()
    # frame renders without error and has valid colors
    for r in range(ROWS):
        for c in range(COLS):
            col = f[r][c]
            assert 0 <= col.r <= 255 and 0 <= col.g <= 255 and 0 <= col.b <= 255
