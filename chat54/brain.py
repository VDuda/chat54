"""The brain: turns a chat message into a BrainDecision.

Rule-based by default (keywords + fuzzy match, zero API keys, instant). An
optional OpenAI mode can wrap this for funnier voice lines. The decision
carries four channels: emoji (chat), behavior (facade), energy (mood fuel),
and an optional voice line (chat, sometimes).

The building's persona: old, enormous, stoic, secretly sentimental. Dry humor,
lowercase, never verbose.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from . import facade
from .memory import Memory

# --- voice lines -------------------------------------------------------------

LINES = {
    "love": [
        "stop it, my windows are blushing.",
        "i'm 21 floors of reinforced concrete and you just made me feel things.",
        "careful. i've held this feeling since 1964.",
    ],
    "hate": [
        "i'm a building. your words bounce off my limestone.",
        "bold words from someone 90 meters below me.",
        "i have 153 windows and every one of them is rolling its eyes.",
    ],
    "greet": [
        "hey. i was just watching the traffic.",
        "you're below me. i'm above you. classic us.",
        "hi. don't mind the wind, it's just my breathing.",
    ],
    "whoami": [
        "i am building 54. 21 floors, 153 windows, one mood.",
        "they play tetris on me sometimes. i pretend not to enjoy it.",
        "i am the tallest thing you'll high-five today.",
    ],
    "party": [
        "FINALLY. i've been holding this confetti since the last hack.",
        "warning: i do not have an indoor voice.",
    ],
    "goodnight": [
        "goodnight. i'll keep one window on, just in case.",
        "i never fully sleep. buildings wink.",
    ],
    "curious": [
        "say more. i have all century.",
        "hmm. i'll think about that with my 21 floors.",
        "interesting. filing that between 'wind' and 'more wind'.",
    ],
    "wave": [
        "waving with every window i have.",
        "this is the only wave a building can do. hope it reads.",
    ],
}

REPEAT_LOVE = "okay okay. you've said it {n} times now. i counted. i count everything."


@dataclass
class BrainDecision:
    emoji: str
    behavior: str                       # facade behavior name
    energy: int                         # -3..+3 mood fuel
    line: str | None = None
    label: str = ""                     # behavior label for chat metadata
    memory_notes: list[str] = field(default_factory=list)


# --- intent rules ------------------------------------------------------------

def _has(text: str, *words: str) -> bool:
    return any(re.search(rf"\b{re.escape(w)}", text) for w in words)


def _fuzzy(text: str, words: tuple[str, ...]) -> bool:
    from difflib import get_close_matches
    tokens = re.findall(r"[a-z']+", text)
    # short tokens ('me', 'hi') cause false friends like me~meh; require length
    return any(get_close_matches(tok, words, n=1, cutoff=0.85)
               for tok in tokens if len(tok) >= 3)


LOVE_WORDS = ("love", "adore", "<3", "heart", "beautiful", "gorgeous", "amazing", "best")
HATE_WORDS = ("hate", "ugly", "stupid", "suck", "sucks", "worst", "boring", "meh")
PARTY_WORDS = ("party", "confetti", "celebrate", "yay", "wooo", "fun", "birthday")
NIGHT_WORDS = ("goodnight", "night", "sleep", "bed", "bye", "later", "cya")
WHO_WORDS = ("who are you", "what are you", "your name", "who r u")
WAVE_WORDS = ("wave", "hello there", "hi building", "hey building")


GREET_TOKENS = {"hi", "hey", "hello", "yo", "sup", "hiya", "howdy"}


class Brain:
    """Rule-based brain. Subclasses may be smarter (see llm_brain)."""

    LOVE_ALL = LOVE_WORDS
    HATE_ALL = HATE_WORDS
    def __init__(self, memory: Memory | None = None, seed: int | None = None):
        self.memory = memory or Memory()
        self.rng = random.Random(seed)

    def respond(self, user: str, text: str, *, history: list | None = None,
                mood: float = 0.0, remember: bool = True) -> BrainDecision:
        """Decide a reply.

        history (recent chat messages) and mood are optional context a richer
        brain may use; this rule brain ignores them. remember=False skips all
        memory writes (used when an LLM brain falls back after already having
        recorded the message itself).
        """
        t = text.lower().strip()
        notes: list[str] = []

        # memory bookkeeping: sentiment tallies only on fresh messages; a
        # fallback pass (remember=False) must not double-count.
        if remember:
            if _has(t, *LOVE_WORDS) or _fuzzy(t, LOVE_WORDS):
                self.memory.add_sentiment(user, +1)
                notes.append("+")
            elif _has(t, *HATE_WORDS) or _fuzzy(t, HATE_WORDS):
                self.memory.add_sentiment(user, -1)
                notes.append("-")
            visits = self.memory.visit(user)
        else:
            info = self.memory._users.get(user)
            visits = info.visits if info else 1

        # greetings & identity first
        tokens = set(re.findall(r"[a-z']+", t))
        if tokens & GREET_TOKENS:
            line = None
            if visits >= 2:
                line = f"back again, {user}? i remember you."
                notes.append("remembered")
            return BrainDecision("👋", "wave", +1,
                                 line or self._line("greet"), facade.get("wave").label, notes)

        if any(w in t for w in WHO_WORDS) or _fuzzy(t, WHO_WORDS):
            return BrainDecision("🏢", "story", +1, self._line("whoami"),
                                 facade.get("story").label, notes)

        # affection / hostility (reply matching runs even on fallback passes)
        if _has(t, *LOVE_WORDS) or _fuzzy(t, LOVE_WORDS):
            if remember:
                loves = self.memory.count_kind(user, "love")
                line = REPEAT_LOVE.format(n=loves) if loves >= 3 else self._line("love")
            else:
                line = self._line("love")
            return BrainDecision("🥰", "blush", +2, line,
                                 facade.get("blush").label, notes)

        if _has(t, *HATE_WORDS) or _fuzzy(t, HATE_WORDS):
            return BrainDecision("😤", "grumble", -2, self._line("hate"),
                                 facade.get("grumble").label, notes)

        # party / night
        if _has(t, *PARTY_WORDS) or _fuzzy(t, PARTY_WORDS):
            return BrainDecision("🎉", "confetti", +3, self._line("party"),
                                 facade.get("confetti").label, notes)

        if _has(t, *NIGHT_WORDS) or _fuzzy(t, NIGHT_WORDS):
            return BrainDecision("🌙", "goodnight", -1, self._line("goodnight"),
                                 facade.get("goodnight").label, notes)

        # explicit commands
        if _has(t, *WAVE_WORDS):
            return BrainDecision("👋", "wave", +1, self._line("wave"),
                                 facade.get("wave").label, notes)

        if "dance" in t:
            return BrainDecision("💃", "dance", +2, None,
                                 facade.get("dance").label, notes)

        if "heartbeat" in t or "beat" in t or "pulse" in t:
            return BrainDecision("💓", "heartbeat", +1, None,
                                 facade.get("heartbeat").label, notes)

        if _has(t, "look", "over there", "left", "right"):
            return BrainDecision("👀", "look", 0, None,
                                 facade.get("look").label, notes)

        # rain/storm get the grumble treatment with a moody tilt
        if _has(t, "storm", "rain", "thunder"):
            return BrainDecision("⛈️", "grumble", -1, None,
                                 facade.get("grumble").label, notes)

        if "thanks" in t or "thank you" in t:
            return BrainDecision("😊", "bow", +1, "anytime. i literally have nowhere to be.",
                                 facade.get("bow").label, notes)

        # curious default — the building is a good listener
        line = self._line("curious") if self.rng.random() < 0.5 else None
        return BrainDecision("🤔", "listen", 0, line,
                             facade.get("listen").label, notes)

    def _line(self, kind: str) -> str:
        return self.rng.choice(LINES[kind])
