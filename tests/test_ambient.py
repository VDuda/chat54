"""Ambient cycle tests: room temperature read, quiet-room wave, quota bounds."""

import threading

import pytest

from chat54.building import Building
from chat54.display import Display, Frame
from chat54 import facade


def settle(building):
    """Simulate the current show having finished (real gap is ~3s; ambient is 15s)."""
    building.director._current = facade.get("breathe")


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

    def respond(self, user, text, **kwargs):
        from chat54.brain import BrainDecision
        return BrainDecision("👋", "wave", 1, None, "waves")


def test_quiet_room_waves_without_api_or_chat(building):
    r = building.ambient_cycle()
    assert r is None                            # no chat spam when quiet
    assert building.director._current.__name__ == "draw_wave"
    assert building._ambient_pending == []


def test_llm_reads_only_new_window(building):
    stub = StubLLMBrain(decision=None)
    building.brain = stub
    building.handle_message("maya", "everyone say hi!")     # goes to window
    building.handle_message("maya", "party later")          # and again
    settle(building)
    building.ambient_cycle()
    assert stub.calls == [["everyone say hi!", "party later"]]
    # consumed: a second cycle with no new messages is a quiet-room wave
    building.ambient_cycle()
    assert len(stub.calls) == 1


def test_llm_decision_performs_and_chats(building):
    from chat54.brain import BrainDecision
    stub = StubLLMBrain(decision=BrainDecision(
        "🎉", "confetti", +3, "this room is alive.", "celebrates"))
    building.brain = stub
    building.handle_message("maya", "PARTY!")
    settle(building)
    r = building.ambient_cycle()
    assert r is not None and "alive" in r["text"]
    assert building.director._current.__name__ == "draw_confetti"
    assert building.history[-1]["user"] == "building54"


def test_llm_failure_stays_silent_that_cycle(building):
    stub = StubLLMBrain(fail=True)
    building.brain = stub
    building.handle_message("maya", "hello")
    settle(building)
    r = building.ambient_cycle()
    assert r is None
    assert stub.fallbacks == 1
    # window was consumed; building did not perform anything for it
    assert building._ambient_pending == []


def test_midshow_cycle_skips_but_keeps_window(building):
    building.handle_message("maya", "i love you")           # triggers blush show
    assert building.director._current.__name__ != "draw_breathe"
    r = building.ambient_cycle()
    assert r is None
    assert len(building._ambient_pending) == 1   # kept for the next cycle


def test_rules_temperature_read(building):
    building.handle_message("maya", "happy birthday!!!")
    building.ambient_cycle()
    assert building.director._current.__name__ == "draw_confetti"


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
