"""Live test: LLMBrain against OpenRouter (uses .env key, real network).

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

for text in [
    "hey building, how's the weather up there?",
    "we're hacking on you all day today, hope that's ok",
    "maya thinks you're the prettiest building in boston",
]:
    t0 = time.time()
    d = b.respond("maya", text, history=history, mood=0.5)
    dt = time.time() - t0
    print(f"{text!r}")
    print(f"  -> {d.emoji}  {d.line or '(no line)'}  [{d.behavior}] energy={d.energy} "
          f"({dt:.1f}s, fallbacks={b.fallbacks})")
    history.append({"user": "maya", "text": text})
    history.append({"user": "building54", "text": d.emoji + " " + (d.line or "")})
