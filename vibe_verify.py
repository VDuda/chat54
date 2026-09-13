"""Verify the ambient LLM brain is driven by the chat discussion.

Part 1: capture the actual prompt — prove the conversation is the input.
Part 2: two different conversations -> different vibe reads and shows.
"""
import os
import tempfile

from chat54.llm_brain import LLMBrain, _load_dotenv
from chat54.memory import Memory

_load_dotenv()

# --- part 1: the prompt contains the discussion ------------------------------
seen = {}
llm = LLMBrain(memory=Memory("/tmp/chat54_vibe.json"),
               chat_fn=lambda p: (seen.__setitem__("p", p),
                                  '{"emoji":"👋","behavior":"wave","energy":1,'
                                  '"line":"ok","vibe":"calm"}')[1],
               min_interval=0.0)
window = [{"user": "maya", "text": "demo is in ten minutes, i'm nervous"},
          {"user": "leo", "text": "breathe. we tested this all week"}]
llm.ambient(window, window, 0.5)
p = seen["p"]
print("PROMPT CHECKS")
print("  contains maya's message:  ", "demo is in ten minutes" in p)
print("  contains leo's message:   ", "breathe. we tested this all week" in p)
print("  has NEW-messages section: ", "NEW messages since you last looked" in p)
print("  has mood context:         ", "Your current mood" in p)
print("  has behavior menu:        ", "BEHAVIORS:" in p)

# --- part 2: content decides the outcome (real API) --------------------------
print("\nTWO CONVERSATIONS THROUGH THE REAL BRAIN")
real = LLMBrain(memory=Memory("/tmp/chat54_vibe2.json"))
for name, msgs in [
    ("celebration", [("maya", "WE SHIPPED IT! it works on the real building!"),
                     ("leo", "champagne tonight!!")]),
    ("pre-demo nerves", [("maya", "demo is in ten minutes, i'm nervous"),
                         ("leo", "what if the wifi drops again")]),
]:
    window = [{"user": u, "text": t} for u, t in msgs]
    try:
        d = real.ambient(window, window, 0.5)
        print(f"  {name:<16} -> vibe={d.vibe!r:22} show={d.behavior:<9} "
              f"energy={d.energy:+d}  {d.line or ''}")
    except Exception as e:
        print(f"  {name:<16} -> fell back ({e})")
