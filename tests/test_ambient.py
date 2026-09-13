"""Ambient cycle tests: silent chat, 15s countdown reveal, quota bounds."""

import threading

import pytest

from chat54.building import Building
from chat54.display import Display, Frame
from chat54 import facade
from chat54.facade import ROWS, COLS


class NullDisplay(Display):
    def makeframe(self):
        return Frame()

    def send(self, frame):
        pass


@pytest.fixture()
def building(monkeypatch, tmp_path):
    monkeypatch.setattr("chat54.building.open_display",
                        lambda i, b=None: NullDisplay())
    return Building(memory_path=str(tmp_path / "mem.json"))


class StubLLMBrain:
    """Quacks like LLMBrain for the ambient path."""

    def __init__(self, decision=None, fail=False):
        self.fallbacks = 0
        self._decision = decision
        self._fail = fail
        self.calls = []

    def ambient(self, window, history, mood):
        self.calls.append([m["text"] for m in window])
        if self._fail:
            raise RuntimeError("api down")
        return self._decision


def settle(building):
    """Mark no show in flight (the countdown counts as a show)."""
    building.director._current = facade.get("breathe")
    building.director._queued = None


def test_messages_are_silent_no_replies(building):
    for text in ("hello", "i love you", "you suck", "party!!"):
        r = building.handle_message("maya", text)
        assert r is None                       # building never replies per message
    assert building.outbox.empty()
    assert len(building.history) == 4
    assert all(m["user"] == "maya" for m in building.history)
    assert building.director._current.__name__ == "draw_breathe"  # stayed idle


def test_quiet_room_counts_down_to_a_wave(building):
    r = building.ambient_cycle()
    assert r is None                            # silent, no chat spam
    assert building.director._current.__name__ == "draw_countdown"
    assert building.director._queued.__name__ == "draw_wave"
    assert building._ambient_pending == []


def test_llm_reads_only_new_window(building):
    stub = StubLLMBrain(decision=None)
    building.brain = stub
    building.handle_message("maya", "everyone say hi!")
    building.handle_message("maya", "party later")
    settle(building)
    building.ambient_cycle()
    assert stub.calls == [["everyone say hi!", "party later"]]
    settle(building)
    building.ambient_cycle()                    # no new messages -> no LLM call
    assert len(stub.calls) == 1


def test_llm_decision_chains_after_countdown(building):
    from chat54.brain import BrainDecision
    stub = StubLLMBrain(decision=BrainDecision(
        "🎉", "confetti", +3, "this room is alive.", "celebrates"))
    building.brain = stub
    building.handle_message("maya", "PARTY!")
    settle(building)
    r = building.ambient_cycle()
    assert r is not None and "alive" in r["text"]
    assert building.director._current.__name__ == "draw_countdown"
    assert building.director._queued.__name__ == "draw_confetti"

    # advance past the countdown: the queued show must start itself
    import time as _t
    later = _t.monotonic() + (building.director._current.duration_ms + 100) / 1000
    building.director.render_frame(later)
    assert building.director._current.__name__ == "draw_confetti"


def test_llm_failure_stays_silent_that_cycle(building):
    stub = StubLLMBrain(fail=True)
    building.brain = stub
    building.handle_message("maya", "hello")
    settle(building)
    r = building.ambient_cycle()
    assert r is None
    assert stub.fallbacks == 1
    assert building.director._current.__name__ == "draw_breathe"
    assert building._ambient_pending == []


def test_midshow_cycle_skips_but_keeps_window(building):
    building.ambient_cycle()                    # countdown starts
    r = building.ambient_cycle()                # still counting/chaining
    assert r is None
    assert len(building._ambient_pending) == 0  # window consumed by first cycle
    # new messages during the show are held for the next cycle
    building.handle_message("maya", "again!")
    assert len(building._ambient_pending) == 1


def test_rules_temperature_read(building):
    building.handle_message("maya", "happy birthday!!!")
    settle(building)
    building.ambient_cycle()
    assert building.director._current.__name__ == "draw_countdown"
    assert building.director._queued.__name__ == "draw_confetti"


def test_countdown_then_show_renders_through_chain(building):
    """The full render path: countdown frames, then the queued show's frames."""
    import time as _t
    building.handle_message("maya", "hello")
    settle(building)
    building.ambient_cycle()
    now = _t.monotonic()
    step = 0.15
    seen_countdown = seen_show = False
    for i in range(60):                         # ~9s at 0.15s steps
        f = building.director.render_frame(now + i * step)
        lit = sum(1 for r in range(ROWS) for c in range(COLS)
                  if (f[r][c].r, f[r][c].g, f[r][c].b) != (0, 0, 0))
        cd_ms = facade.BEHAVIORS["countdown"].duration_ms
        t_rel = i * step
        if t_rel < cd_ms / 1000 and lit > 8:
            seen_countdown = True
        if t_rel > cd_ms / 1000 + 0.5 and lit > 8:
            seen_show = True
    assert seen_countdown and seen_show


def test_countdown_mirrors_into_chat_in_sync(building):
    """3/2/1 keycaps post on the facade's digit schedule, reveal at show start."""
    import queue as _q
    import time as _t
    building.handle_message("maya", "we did the thing!")
    settle(building)
    t0 = _t.monotonic()
    building.ambient_cycle()
    step = facade.DIGIT_HOLD_S + facade.DIGIT_GAP_S
    msgs = []
    while True:
        try:
            m = building.outbox.get(timeout=5)
            msgs.append((round(_t.monotonic() - t0, 2), m["text"]))
        except _q.Empty:
            break
    texts = [t for _, t in msgs]
    assert texts[0:3] == ["3️⃣", "2️⃣", "1️⃣"]
    assert len(msgs) == 4
    # each digit lands on its step boundary (+-0.2s), reveal at 3*step
    for i in range(3):
        assert abs(msgs[i][0] - i * step) < 0.2, msgs
    assert abs(msgs[3][0] - 3 * step) < 0.2, msgs
    assert msgs[3][1].startswith("👋")      # quiet-room wave reveal


def test_ambient_loop_runs_periodically(building, monkeypatch):
    ran = threading.Event()

    real_cycle = building.ambient_cycle

    def spy():
        real_cycle()
        ran.set()

    monkeypatch.setattr(building, "ambient_cycle", spy)
    stop = threading.Event()
    building.start_ambient(stop, period=0.2)
    assert ran.wait(2.0)
    stop.set()
