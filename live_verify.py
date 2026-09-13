"""Live verify: chat stays silent -> at ~15s the building counts down 3-2-1
-> then shows the room's emotion. Polls the sim's actual frame content.

Usage: python live_verify.py <instance> [base-url]
"""
import json
import sys
import threading
import time
import urllib.request

from chat54.building import Building

instance = sys.argv[1] if len(sys.argv) > 1 else "clever-lynx"
base = "https://sundai.willsarg.com"
status_url = f"{base}/api/i/{instance}/"
frame_url = f"{base}/api/i/{instance}/frame"

T0 = time.monotonic()


def log(msg):
    print(f"[{time.monotonic() - T0:5.1f}s] {msg}", flush=True)


def fetch_frame():
    req = urllib.request.Request(
        frame_url, headers={"User-Agent": "chat54-verify/1"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r)                      # 17 rows x 9 cols x [r,g,b]


def describe(grid):
    lit = sum(1 for row in grid for px in row if px[0] + px[1] + px[2] > 24)
    warm = sum(1 for row in grid for px in row
               if px[0] > 120 and px[0] > px[2] + 30)
    return f"lit={lit:3d} warm={warm:3d}"


building = Building(instance=instance, base_url=f"{base}/api", brain="llm")
stop = threading.Event()
threading.Thread(target=building.render_loop, args=(stop,), daemon=True).start()
building.start_ambient(stop, period=15.0)

log(f"streaming to {instance}; watching the real frame content")

# fan-out thread: print whatever the building says (announce lines)
def drain():
    while True:
        r = building.outbox.get()
        log(f"BUILDING SAYS: {r['text']}  -> countdown then [{r['behavior']}]")
threading.Thread(target=drain, daemon=True).start()

# frame watcher: sample the sim every 2s
def watch():
    last = ""
    while not stop.wait(2.0):
        try:
            d = describe(fetch_frame())
            if d != last:
                log(f"building shows: {d}")
                last = d
        except Exception as e:
            log(f"(frame fetch failed: {e})")
threading.Thread(target=watch, daemon=True).start()

log("the room starts chatting (building stays silent)...")
building.handle_message("maya", "this building is absolutely incredible tonight")
building.handle_message("leo", "best hack sundai has ever seen, honestly")
building.handle_message("maya", "i could stare at those windows forever")

time.sleep(36)                                  # cover one full 15s cycle + show
stop.set()
log("done")
