"""Play every behavior in sequence against a simulator instance.

Use it to tune brightness/pacing by eye in the viewer:
    python tuning_tour.py clever-lynx https://sundai.willsarg.com/api
Watch: https://sundai.willsarg.com/<name>?view=close   (?fx=0 disables the
sim's GPU bloom if you want to see raw cells.)
"""
import sys
import threading
import time

from chat54 import facade
from chat54.building import Building

instance = sys.argv[1] if len(sys.argv) > 1 else "clever-lynx"
base_url = sys.argv[2] if len(sys.argv) > 2 else "https://sundai.willsarg.com/api"

building = Building(instance=instance, base_url=base_url)
stop = threading.Event()
threading.Thread(target=building.render_loop, args=(stop,), daemon=True).start()

print(f"tuning tour on {instance} — watch https://sundai.willsarg.com/{instance}?view=close")
time.sleep(3)
print("idle (breathe) for reference...")
time.sleep(4)

for name, fn in facade.BEHAVIORS.items():
    if name in ("breathe", "listen"):
        continue
    print(f"  {name:<10} gain={facade.gain_for(name):.2f}  {fn.duration_ms}ms  — {fn.label}")
    building.director.on_reply(name, 0)
    time.sleep(fn.duration_ms / 1000 + 2.0)      # show + settle gap

print("back to idle. done in 5s.")
time.sleep(5)
stop.set()
