"""Live verification of the LLM brain against OpenRouter (real network).

Shows: context awareness (it reads the chat + mood), decision quality,
throttle spacing, memory, and the fallback counter.

Usage: python llm_live_test.py
"""
import os
import time

from chat54.llm_brain import LLMBrain, _load_dotenv
from chat54.memory import Memory

_load_dotenv()
assert os.environ.get("OPENROUTER_API_KEY"), "put OPENROUTER_API_KEY in .env"

b = LLMBrain(memory=Memory("/tmp/chat54_llm_test.json"))
history = []
t_last = None

CONVERSATION = [
    ("maya", "hey building, what's the view like from up there?"),
    ("leo",  "we're hacking on you all day, hope that's ok"),
    ("maya", "i think you're the prettiest building in boston"),
    ("leo",  "party tonight!!"),
    ("maya", "what did leo just say we're doing?"),   # context recall test
    ("maya", "actually you're kind of boring"),       # negativity test
]

for user, text in CONVERSATION:
    t0 = time.time()
    d = b.respond(user, text, history=history, mood=b.__dict__.get("_fake_mood", 0.5))
    dt = time.time() - t0
    gap = f"{t0 - t_last:4.1f}s after prev call" if t_last else "first call"
    t_last = t0
    fb = " (FELL BACK to rules)" if d.memory_notes != ["llm"] else ""
    print(f"{user}: {text!r}")
    print(f"   -> {d.emoji}  {d.line or '(no line)'}  [{d.behavior}] "
          f"energy={d.energy:+d}  call={dt:.1f}s, {gap}{fb}")
    history.append({"user": user, "text": text})
    history.append({"user": "building54", "text": d.emoji + "  " + (d.line or "")})

print(f"\nfinal: fallbacks={b.fallbacks}/{len(CONVERSATION)} messages")
