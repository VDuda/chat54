"""What will the building display? Feed distinct chat vibes through both
brains and print the facade decision for each.

Usage: python display_options_test.py
"""
import os
import tempfile

from chat54.llm_brain import LLMBrain, _load_dotenv
from chat54.building import Building
from chat54.display import Display, Frame
from chat54.memory import Memory

_load_dotenv()

SCENARIOS = [
    ("hype party", [
        ("maya", "LETS GOOO we just got the thing working!"),
        ("leo", "PARTY TIME everyone!!"),
        ("sam", "yayyy we did it 🎉"),
    ]),
    ("affectionate", [
        ("maya", "i love this building so much"),
        ("leo", "you're beautiful, you know that?"),
    ]),
    ("frustrated", [
        ("maya", "this wifi sucks"),
        ("leo", "ugh everything is broken today"),
        ("sam", "worst hack ever lol"),
    ]),
    ("calm tech talk", [
        ("maya", "the websocket handler uses asyncio.to_thread"),
        ("leo", "yeah we should add retry with backoff"),
        ("sam", "pushed the fix to main"),
    ]),
    ("mysterious/curious", [
        ("maya", "what if the building is watching us right now"),
        ("leo", "which window are you behind?"),
    ]),
]

print("=" * 72)
print("RULES brain (keyword table, instant, free)")
print("=" * 72)
os.chdir(tempfile.mkdtemp())
import chat54.building as bm


class Null(Display):
    def makeframe(self):
        return Frame()

    def send(self, f):
        pass


bm.open_display = lambda i, b=None: Null()
b = Building(brain="rules")
for vibe, msgs in SCENARIOS:
    for u, t in msgs:
        b.handle_message(u, t)
    decision, _ = b._ambient_decide()
    print(f"{vibe:<18} -> shows {decision.behavior:<9} "
          f"(energy {decision.energy:+d})")

print()
print("=" * 72)
print("LLM brain (reads the actual conversation)")
print("=" * 72)
llm = LLMBrain(memory=Memory("/tmp/chat54_disp_test.json"))
for vibe, msgs in SCENARIOS:
    window = [{"user": u, "text": t} for u, t in msgs]
    try:
        d = llm.ambient(window, window, 0.5)
        fb = ""
    except Exception:
        llm.fallbacks += 1
        d = None
        fb = "  (fell back to rules)"
    if d:
        print(f"{vibe:<18} -> shows {d.behavior:<9} {d.emoji} "
              f"\"{d.line or ''}\" (energy {d.energy:+d}){fb}")
    else:
        print(f"{vibe:<18} -> silent this cycle{fb}")

print(f"\nLLM fallbacks: {llm.fallbacks}/{len(SCENARIOS)}")
print("\nWhatever it picks, the sequence on the building is always:")
print("  3 ... 2 ... 1 ...  (warm glowing digits, ~3s)")
print("  then the chosen show, then back to breathing idle")
