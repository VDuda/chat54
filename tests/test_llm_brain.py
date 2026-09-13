"""LLM brain tests: JSON contract, validation, fallback — all offline."""

import json

import pytest

from chat54.llm_brain import LLMBrain
from chat54.memory import Memory


@pytest.fixture()
def memory(tmp_path):
    return Memory(str(tmp_path / "mem.json"))


def make_brain(memory, reply):
    """Brain whose 'API' always returns the given JSON string."""
    return LLMBrain(memory=memory, chat_fn=lambda prompt: reply)


def good(emoji="🧠", behavior="dance", energy=2, line="i am thinking with my concrete."):
    return json.dumps({"emoji": emoji, "behavior": behavior,
                       "energy": energy, "line": line})


def test_llm_decision_passes_through(memory):
    b = make_brain(memory, good())
    d = b.respond("maya", "dance for us")
    assert d.behavior == "dance"
    assert d.emoji == "🧠"
    assert d.energy == 2
    assert d.line.startswith("i am thinking")


def test_llm_sees_history_and_mood(memory):
    seen = {}

    def chat_fn(prompt):
        seen["prompt"] = prompt
        return good()

    b = LLMBrain(memory=memory, chat_fn=chat_fn)
    b.respond("maya", "hi", history=[{"user": "maya", "text": "hi"}], mood=-1.5)
    assert "maya just said: hi" in seen["prompt"]
    assert "-1.5" in seen["prompt"]


def test_hallucinated_behavior_falls_back_to_rules(memory):
    b = make_brain(memory, good(behavior="teleport_now"))
    d = b.respond("maya", "hello there")
    assert d.behavior in ("wave", "breathe", "listen")  # rules answered
    assert b.fallbacks == 1


def test_malformed_json_falls_back(memory):
    b = LLMBrain(memory=memory, chat_fn=lambda prompt: "not json at all {{")
    d = b.respond("maya", "i love you")
    assert d.behavior == "blush"          # rule brain caught it
    assert b.fallbacks == 1


def test_energy_clamped(memory):
    b = make_brain(memory, good(energy=99))
    d = b.respond("maya", "party!")
    assert d.energy == 3


def test_long_line_truncated(memory):
    b = make_brain(memory, good(line="x" * 200))
    d = b.respond("maya", "hello")
    assert len(d.line) <= 91              # 90 chars + ellipsis


def test_memory_counted_once_across_fallback(memory):
    # fallback path must not double-count sentiment
    b = LLMBrain(memory=memory, chat_fn=lambda prompt: "{{{broken")
    b.respond("maya", "i love you")
    b2 = LLMBrain(memory=memory, chat_fn=lambda prompt: good())
    b2.respond("maya", "i love you")
    assert memory.mood_summary()["sentiment"] == 2


def test_idle_behaviors_rejected_for_replies(memory):
    b = make_brain(memory, good(behavior="breathe"))
    d = b.respond("maya", "what's up")
    assert d.behavior != "breathe"        # idle is not a reply show
    assert b.fallbacks == 1
