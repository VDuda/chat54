"""Brain tests: message -> decision mapping and memory effects."""

import pytest

from chat54.brain import Brain
from chat54.memory import Memory
from chat54 import facade


@pytest.fixture()
def brain(tmp_path):
    return Brain(memory=Memory(str(tmp_path / "mem.json")), seed=42)


def behavior_of(brain, text, user="tester"):
    return brain.respond(user, text).behavior


def test_love_blushes(brain):
    d = brain.respond("maya", "i love you")
    assert d.behavior == "blush"
    assert d.energy > 0
    assert "❤" in d.emoji or "🥰" in d.emoji


def test_hate_grumbles(brain):
    d = brain.respond("maya", "you suck")
    assert d.behavior == "grumble"
    assert d.energy < 0


def test_party_confetti(brain):
    assert behavior_of(brain, "party!!") == "confetti"
    assert behavior_of(brain, "happy birthday!") == "confetti"


def test_dance_not_confetti(brain):
    assert behavior_of(brain, "dance for me") == "dance"


def test_goodnight(brain):
    assert behavior_of(brain, "goodnight building") == "goodnight"


def test_greet_waves(brain):
    assert behavior_of(brain, "hello!") == "wave"


def test_identity_story(brain):
    d = brain.respond("maya", "who are you?")
    assert d.behavior == "story"
    assert d.line  # has a voice line


def test_yo_is_not_you(brain):
    # 'yo' should greet, but 'you suck' must not
    assert behavior_of(brain, "yo!") == "wave"
    assert behavior_of(brain, "you suck") == "grumble"


def test_unknown_is_curious_listen(brain):
    d = brain.respond("maya", "do you like the weather today")
    assert d.behavior in ("listen",)
    assert d.energy == 0


def test_memory_counts_loves(brain):
    for _ in range(3):
        d = brain.respond("maya", "i love you")
    assert "3 times" in (d.line or "")


def test_memory_greeting_recognition(brain):
    brain.respond("maya", "hello")
    brain.respond("maya", "hi again")
    d = brain.respond("maya", "hey, it's me")
    assert "maya" in (d.line or "")


def test_memory_persists_sentiment(brain, tmp_path):
    path = str(tmp_path / "mem2.json")
    b1 = Brain(memory=Memory(path), seed=1)
    b1.respond("maya", "i love you")
    b2 = Brain(memory=Memory(path), seed=1)
    assert b2.memory.mood_summary()["sentiment"] == 1


def test_decisions_reference_real_behaviors(brain):
    for text in ("hi", "i love you", "you suck", "party", "goodnight",
                 "dance", "who are you", "wave at me", "storm", "thanks"):
        d = brain.respond("t", text)
        assert d.behavior in facade.BEHAVIORS
