"""The building process: owns the display, renders at 30 fps.

Run standalone for a local chat-in-terminal smoke test:

    python -m chat54.building                 # ANSI preview
    python -m chat54.building --instance nm   # drive a simulator instance

The server process imports run_building_loop() to run it in a background
thread alongside the WebSocket chat room.
"""

from __future__ import annotations

import argparse
import queue
import threading
import time

from .brain import Brain, BrainDecision
from .director import Director
from .displays import open_display
from .display import Frame
from . import facade

FPS = 30
AMBIENT_PERIOD_S = 15          # the building checks the room's temperature


class Building:
    """Glue: brain + memory + director + display."""

    def __init__(self, instance: str | None = None, base_url: str | None = None,
                 memory_path: str = "chat54_memory.json", brain: str = "rules"):
        from .memory import Memory
        memory = Memory(memory_path)
        if brain == "llm":
            from .llm_brain import LLMBrain
            # the LLM's ONLY job is the 15s ambient room-read (bounded quota,
            # <=4 calls/min); per-message replies come from the instant rule
            # brain so the building always reacts immediately and for free
            self.brain = LLMBrain(memory=memory)
            self._instant = Brain(memory=memory)
        else:
            self.brain = Brain(memory=memory)
            self._instant = self.brain
        self.director = Director()
        self.display = open_display(instance, base_url)
        self.outbox: queue.Queue[dict] = queue.Queue()
        self.history: list[dict] = []          # recent chat, for LLM context
        self._ambient_pending: list[dict] = [] # messages since last ambient cycle
        self._show_lock = threading.Lock()     # one director.show at a time
        self._cd_thread: threading.Thread | None = None

    def handle_message(self, user: str, text: str) -> None:
        """Record a human message. The building does NOT reply per message —
        it stays quiet in the chat and performs the room's vibe on the next
        ambient cycle (every 15s), announced by a 3-2-1 countdown."""
        msg = {"user": user, "text": text, "t": time.time()}
        self.history.append(msg)
        self._ambient_pending.append(msg)
        self.history = self.history[-50:]

    # --- ambient cycle ----------------------------------------------------------

    def _ambient_decide(self) -> tuple:
        """One decision per cycle: LLM reads the room; quiet -> silent wave."""
        window, self._ambient_pending = self._ambient_pending, []
        if not window:
            # quiet room: default gesture, no API call, no chat spam
            return BrainDecision("👋", "wave", +1, None,
                                 "waves at the room"), False
        if hasattr(self.brain, "ambient"):
            try:
                return self.brain.ambient(window, self.history[-12:],
                                          self.director.mood), True
            except Exception:
                self.brain.fallbacks += 1
                # LLM missed: say nothing this cycle rather than double-reply
                return None, False
        # rules brain: cheap keyword temperature read
        blob = " ".join(m["text"].lower() for m in window)
        if any(w in blob for w in ("party", "yay", "birthday", "confetti", "wooo")):
            d = BrainDecision("🎉", "confetti", +3, None, "celebrates the room")
        elif any(w in blob for w in ("love", "great", "awesome", "beautiful")):
            d = BrainDecision("😊", "blush", +2, None, "glows at the room")
        elif any(w in blob for w in ("suck", "hate", "boring", "meh")):
            d = BrainDecision("😤", "grumble", -2, None, "grumbles softly")
        else:
            d = BrainDecision("👋", "wave", +1, None, "waves at the room")
        return d, False

    # Countdown mirrored into the chat, synced with the facade digits: each
    # step is DIGIT_HOLD_S + DIGIT_GAP_S on the building, and the reveal line
    # lands exactly when the queued show starts.
    COUNTDOWN_CHAT = ("3️⃣", "2️⃣", "1️⃣")

    def ambient_cycle(self) -> dict | None:
        """Run one 15s cycle: countdown 3-2-1 (facade + chat), then the vibe.

        Returns the reveal reply (what the building will say when the show
        starts), or None when it stays silent this cycle.
        """
        # if a show is mid-flight, let it finish; window is kept for next time
        if self.director._current is not facade.get("breathe"):
            return None
        decision, from_llm = self._ambient_decide()
        if decision is None:
            return None
        t0 = time.monotonic()
        with self._show_lock:
            self.director.perform_after_countdown(decision.behavior,
                                                  decision.energy)
        # mirror the countdown into the chat, timed with the facade digits
        self._cd_thread = threading.Thread(target=self._countdown_chat,
                                           args=(decision, t0), daemon=True)
        self._cd_thread.start()
        if decision.line:
            vibe = decision.vibe or "the room's vibe"
            return {
                "user": "building54",
                "text": (f"{decision.emoji}  vibe: {vibe} — showing "
                         f"{decision.behavior} — {decision.line}"),
                "behavior": decision.behavior,
                "label": decision.label,
                "vibe": decision.vibe,
                "mood": round(self.director.mood, 2),
            }
        return None

    def _countdown_chat(self, decision, t0: float) -> None:
        """Post 3/2/1 in step with the facade, then the reveal line."""
        step = facade.DIGIT_HOLD_S + facade.DIGIT_GAP_S
        for i, keycap in enumerate(self.COUNTDOWN_CHAT):
            delay = (t0 + i * step) - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self.outbox.put({"user": "building54", "text": keycap,
                             "kind": "countdown", "behavior": "countdown",
                             "mood": round(self.director.mood, 2)})
        # reveal: lands exactly as the show starts. The chat always states
        # what the brain decided: the vibe read and the show it chose.
        delay = (t0 + 3 * step) - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        vibe = decision.vibe or "the room's vibe"
        text = (f"{decision.emoji}  vibe: {vibe} — showing "
                f"{decision.behavior}"
                + (f" — {decision.line}" if decision.line else ""))
        reply = {
            "user": "building54",
            "text": text,
            "behavior": decision.behavior,
            "label": decision.label,
            "vibe": decision.vibe,
            "mood": round(self.director.mood, 2),
        }
        self.history.append({"user": "building54", "text": reply["text"],
                             "t": time.time()})
        self.outbox.put(reply)

    def start_ambient(self, stop: threading.Event,
                      period: float = AMBIENT_PERIOD_S) -> None:
        def loop():
            while not stop.wait(period):
                try:
                    self.ambient_cycle()
                except Exception:
                    pass                       # the building never crashes on a cycle
        threading.Thread(target=loop, name="chat54-ambient", daemon=True).start()

    def render_loop(self, stop: threading.Event) -> None:
        frame = self.display.makeframe()
        frame_period = 1 / FPS
        last = time.monotonic()
        while not stop.is_set():
            now = time.monotonic()
            dt = now - last
            last = now
            self.director.tick(dt)
            f = self.director.render_frame(now)
            # copy into the frame we own (frames are plain objects here)
            for r in range(f.nrows()):
                for c in range(f.ncols()):
                    frame[r][c] = f[r][c]
            self.display.send(frame)
            # simple frame pacing
            elapsed = time.monotonic() - now
            time.sleep(max(0.0, frame_period - elapsed))


def run_building_loop(building: Building, stop: threading.Event) -> None:
    building.render_loop(stop)


def main() -> None:
    ap = argparse.ArgumentParser(description="chat54 building process")
    ap.add_argument("--instance", default=None,
                    help="simulator instance name (omit for ANSI preview)")
    ap.add_argument("--base-url", default=None,
                    help="override simulator API base URL")
    ap.add_argument("--brain", default="rules", choices=["rules", "llm"],
                    help="llm needs OPENAI_API_KEY and the openai package; "
                         "falls back to rules on any failure")
    args = ap.parse_args()

    building = Building(instance=args.instance, base_url=args.base_url,
                        brain=args.brain)
    stop = threading.Event()
    threading.Thread(target=run_building_loop, args=(building, stop),
                     daemon=True).start()
    building.start_ambient(stop)

    def drain():
        while True:
            r = building.outbox.get()
            print(f"building54: {r['text']}   [{r['behavior']}]")
    threading.Thread(target=drain, daemon=True).start()

    print("chat54 building is up. type as a chat user and press enter. ^C to quit.")
    print(f"the building reads the room every {AMBIENT_PERIOD_S}s: "
          "3-2-1 on the facade, then the vibe. it does not reply to each message.")
    user = "terminal"
    try:
        while True:
            text = input("> ").strip()
            if not text:
                continue
            building.handle_message(user, text)
    except (KeyboardInterrupt, EOFError):
        stop.set()


if __name__ == "__main__":
    main()
