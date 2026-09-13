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

from .brain import Brain
from .director import Director
from .displays import open_display
from .display import Frame

FPS = 30


class Building:
    """Glue: brain + memory + director + display."""

    def __init__(self, instance: str | None = None, base_url: str | None = None,
                 memory_path: str = "chat54_memory.json", brain: str = "rules"):
        from .memory import Memory
        memory = Memory(memory_path)
        if brain == "llm":
            from .llm_brain import LLMBrain
            self.brain = LLMBrain(memory=memory)
        else:
            self.brain = Brain(memory=memory)
        self.director = Director()
        self.display = open_display(instance, base_url)
        self.outbox: queue.Queue[dict] = queue.Queue()
        self.history: list[dict] = []          # recent chat, for LLM context

    def handle_message(self, user: str, text: str) -> dict:
        """Process one chat message; returns the building's reply dict."""
        self.history.append({"user": user, "text": text})
        decision = self.brain.respond(user, text,
                                      history=self.history[-12:],
                                      mood=self.director.mood)
        self.director.on_reply(decision.behavior, decision.energy)
        reply = {
            "user": "building54",
            "text": decision.emoji + ("  " + decision.line if decision.line else ""),
            "behavior": decision.behavior,
            "label": decision.label,
            "mood": round(self.director.mood, 2),
        }
        self.history.append({"user": "building54", "text": reply["text"]})
        self.history = self.history[-50:]
        self.outbox.put(reply)
        return reply

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

    print("chat54 building is up. type as a chat user and press enter. ^C to quit.")
    user = "terminal"
    try:
        while True:
            text = input("> ").strip()
            if not text:
                continue
            reply = building.handle_message(user, text)
            print(f"building54: {reply['text']}   [{reply['behavior']}]")
    except (KeyboardInterrupt, EOFError):
        stop.set()


if __name__ == "__main__":
    main()
