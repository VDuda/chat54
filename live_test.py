"""Drive the real simulator instance with a scripted conversation.

Usage:  python live_test.py <instance-name> [base-url]
Watch:  https://sundai.willsarg.com/<instance-name>?view=close
"""
import sys
import threading
import time

from chat54.building import Building

instance = sys.argv[1] if len(sys.argv) > 1 else "clever-lynx"
base_url = sys.argv[2] if len(sys.argv) > 2 else "https://sundai.willsarg.com/api"

building = Building(instance=instance, base_url=base_url)
stop = threading.Event()
threading.Thread(target=building.render_loop, args=(stop,), daemon=True).start()

print(f"streaming to {instance} — watch https://sundai.willsarg.com/{instance}?view=close")


def say(text, pause=3.5):
    r = building.handle_message("maya", text)
    print(f"  {text!r:20} -> {r['text']}  [{r['behavior']}]")
    time.sleep(pause)


print("idle breathing for 4s...")
time.sleep(4)
say("hello!")
say("i love you")
say("party!!")
say("who are you?")
say("goodnight")
print("back to idle for 4s, then done.")
time.sleep(4)
stop.set()
print("done. frames keep playing until the instance goes idle.")
