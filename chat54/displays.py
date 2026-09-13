"""Display backends.

- GBSimDisplay: wraps the simulator's WebDisplay (drop-in, same two-method
  contract). Import is deferred so the dummy works without gbsim installed.
- DummyDisplay: big ANSI preview in the terminal, for developing anywhere.
- open_display(): picks based on args.
"""

from __future__ import annotations

import sys

from .display import Display, Frame

ROWS, COLS = Frame.DISPLAY_ROWS, Frame.DISPLAY_COLS


class GBSimDisplay(Display):
    """Streams frames to a simulator instance at sundai.willsarg.com."""

    def __init__(self, instance: str, base_url: str | None = None):
        from gbsim import WebDisplay            # vendored in chat54/gbsim
        self._d = WebDisplay(instance, base_url=base_url) if base_url else WebDisplay(instance)

    def makeframe(self) -> Frame:
        return self._d.makeframe()

    def send(self, frame: Frame) -> None:
        self._d.send(frame)


class DummyDisplay(Display):
    """Renders each frame as ANSI color blocks in the terminal (downsampled)."""

    CELL = "\u2588"     # full block

    def send(self, frame: Frame) -> None:
        rows = []
        rows.append("+" + "-" * (COLS * 2) + "+")
        for r in range(ROWS):
            line = "|"
            for c in range(COLS):
                col = frame[r][c]
                # double-width cells keep the aspect roughly building-like
                line += f"\x1b[48;2;{col.r};{col.g};{col.b}m  \x1b[0m"
            rows.append(line + "|")
        rows.append("+" + "-" * (COLS * 2) + "+")
        sys.stdout.write("\x1b[H\x1b[2J" + "\n".join(rows) + "\n")
        sys.stdout.flush()

    def makeframe(self) -> Frame:
        return Frame()


def open_display(instance: str | None, base_url: str | None = None) -> Display:
    if instance:
        return GBSimDisplay(instance, base_url)
    return DummyDisplay()
