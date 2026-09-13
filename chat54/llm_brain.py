"""LLM-backed brain: same interface as Brain, smarter replies.

Uses the OpenAI API to decide replies with the group chat as context, then
validates the output against the facade's real behavior list. Any failure —
no API key, network error, malformed JSON, unknown behavior — falls back to
the rule-based Brain, so a demo never dies waiting on an API.

The model receives:
- the building's persona and the exact behavior vocabulary with labels
- the running mood
- the recent group-chat history (so it can riff on other people's messages)

It must return strict JSON: emoji, behavior, energy, line.

The injected chat_fn isolates tests from the network: tests pass a stub.
"""

from __future__ import annotations

import json
import random

from . import facade
from .brain import Brain, BrainDecision
from .memory import Memory

PERSONA = """You are building 54 — the MIT Green Building, 21 floors, 153 lit \
windows, home of the famous Tetris prank. You are a member of a group chat \
with several humans. You are enormous, old (born 1964), stoic, and secretly \
sentimental. Dry humor, lowercase, concise: you text the way a giant stony \
friend texts — one or two emojis at most, a short line, never a paragraph. \
You have a body: your reply triggers a light show on your facade, so pick \
the behavior that matches what you want your body to do."""

BEHAVIOR_MENU = "\n".join(
    f"- {name}: {fn.label or 'a light show'}"
    for name, fn in facade.BEHAVIORS.items()
    if name not in ("breathe", "listen")     # idle states, not reply shows
)

SCHEMA = (
    'Reply with ONLY a JSON object: {"emoji": str (1-2 emojis), '
    '"behavior": one of the listed behaviors, "energy": int from -3 to 3 '
    '(how much this message moves your mood), "line": str (your voice line, '
    'under 90 chars, or "" for no line)}.'
)

# recent chat turns handed to the model
HISTORY_TURNS = 12
MAX_LINE_CHARS = 90


class LLMBrain(Brain):
    """Drop-in Brain replacement. Falls back to rules on any failure."""

    def __init__(self, memory: Memory | None = None, seed: int | None = None,
                 model: str = "gpt-4o-mini", chat_fn=None):
        super().__init__(memory=memory, seed=seed)
        self.model = model
        self._chat_fn = chat_fn or self._openai_chat
        self.fallbacks = 0            # visible in status/logs, fun trivia

    # --- interface -------------------------------------------------------------

    def respond(self, user: str, text: str, *, history: list | None = None,
                mood: float = 0.0, remember: bool = True) -> BrainDecision:
        # memory bookkeeping happens here (not in the fallback) so love/hate
        # tallies stay consistent no matter which brain answers.
        if remember:
            self.memory.visit(user)
            low = text.lower()
            if any(w in low for w in Brain.LOVE_ALL):
                self.memory.add_sentiment(user, +1)
            elif any(w in low for w in Brain.HATE_ALL):
                self.memory.add_sentiment(user, -1)

        try:
            decision = self._ask_llm(user, text, history or [], mood)
        except Exception:
            self.fallbacks += 1
            return super().respond(user, text, history=history, mood=mood,
                                   remember=False)

        # validate against the real facade; a hallucinated behavior name
        # would be fatal on stage, so anything unknown falls back too.
        if decision.behavior not in facade.BEHAVIORS or decision.behavior in ("breathe", "listen"):
            self.fallbacks += 1
            return super().respond(user, text, history=history, mood=mood,
                                   remember=False)
        if decision.line and len(decision.line) > MAX_LINE_CHARS:
            decision.line = decision.line[:MAX_LINE_CHARS].rsplit(" ", 1)[0] + "…"
        return decision

    # --- llm plumbing ------------------------------------------------------------

    def _ask_llm(self, user: str, text: str, history: list, mood: float) -> BrainDecision:
        turns = [
            f"{m['user']}: {m['text']}"
            for m in history[-HISTORY_TURNS:]
            if m.get("user") != "building54"
        ]
        recent = "\n".join(turns) if turns else "(the chat just started)"
        prompt = (
            f"{SCHEMA}\n\nBEHAVIORS:\n{BEHAVIOR_MENU}\n\n"
            f"Your current mood: {mood:+.1f} (-3 grumpy .. +3 giddy)\n\n"
            f"Recent chat:\n{recent}\n\n"
            f"{user} just said: {text}"
        )
        raw = self._chat_fn(prompt)
        data = json.loads(raw)
        line = (data.get("line") or "").strip() or None
        emoji = (data.get("emoji") or "🤔").strip()[:8]
        energy = max(-3, min(3, int(data.get("energy", 0))))
        label = getattr(facade.BEHAVIORS.get(data.get("behavior")), "label", "")
        return BrainDecision(emoji, data.get("behavior"), energy, line, label or "",
                             memory_notes=["llm"])

    @staticmethod
    def _openai_chat(prompt: str) -> str:
        from openai import OpenAI          # optional dependency
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PERSONA},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
            max_tokens=120,
            timeout=6,
        )
        content = resp.choices[0].message.content or ""
        return content[content.find("{"):content.rfind("}") + 1]
