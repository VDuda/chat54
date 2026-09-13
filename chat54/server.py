"""FastAPI chat room: phones join via QR, everyone talks to the building.

- GET  /        controller page (phone-first)
- GET  /qr.svg  QR code pointing at this server on the LAN
- WS   /ws      join/chat protocol: {"type":"join","name":..} then {"type":"chat","text":..}
                 server pushes {"type":"msg","user","text","behavior","mood"}

The building runs its render loop in a background thread and is the only
frame writer for the display instance.
"""

from __future__ import annotations

import asyncio
import json
import queue
import socket
import threading
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from .building import Building, run_building_loop

app = FastAPI(title="chat54")

building = Building()          # dummy display until main() maybe rebinds it
stop_event = threading.Event()


class Room:
    """Fan-out of chat messages to every connected phone."""

    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def join(self, ws: WebSocket):
        async with self.lock:
            self.clients.add(ws)

    async def leave(self, ws: WebSocket):
        async with self.lock:
            self.clients.discard(ws)

    async def broadcast(self, payload: dict):
        data = json.dumps(payload)
        async with self.lock:
            targets = list(self.clients)
        for ws in targets:
            try:
                await ws.send_text(data)
            except Exception:
                await self.leave(ws)


room = Room()
_outbox_task = None                     # strong ref so the task is never GC'd


@app.on_event("startup")
async def start_outbox_pump():
    """Single fan-out for everything the building says (replies + ambient)."""
    global _outbox_task

    async def poller():
        while True:
            try:
                reply = await asyncio.to_thread(building.outbox.get, True, 1.0)
                await room.broadcast({"type": "msg", **reply})
            except queue.Empty:
                await asyncio.sleep(0.1)
            except Exception:
                await asyncio.sleep(0.5)   # never let the pump die
    _outbox_task = asyncio.create_task(poller())


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse((STATIC_DIR / "index.html").read_text())


@app.get("/qr.svg")
async def qr_svg():
    import qrcode
    url = lan_url()
    qr = qrcode.QRCode(border=2, box_size=1)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    n = len(matrix)
    rects = [f'<rect x="{x}" y="{y}" width="1" height="1"/>'
             for y, row in enumerate(matrix)
             for x, dark in enumerate(row) if dark]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" '
           f'width="{n * 8}" height="{n * 8}" shape-rendering="crispEdges">'
           f'<rect width="{n}" height="{n}" fill="white"/><g fill="black">'
           + "".join(rects) + "</g></svg>")
    return Response(content=svg, media_type="image/svg+xml")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    await room.join(ws)
    name = "anon"
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            if msg.get("type") == "join":
                name = (msg.get("name") or "anon").strip()[:24] or "anon"
                await room.broadcast({
                    "type": "msg", "user": "building54",
                    "text": f"👋 {name} joined. i can see you down there.",
                    "behavior": "wave", "mood": building.director.mood,
                })
                continue
            if msg.get("type") == "chat":
                text = (msg.get("text") or "").strip()[:280]
                if not text:
                    continue
                await room.broadcast({"type": "msg", "user": name, "text": text})
                # the brain can take a couple of seconds; keep the socket
                # loop responsive by moving the work off the event loop. The
                # building's reply is fanned out by the outbox pump below.
                await asyncio.to_thread(building.handle_message, name, text)
    except WebSocketDisconnect:
        pass
    finally:
        await room.leave(ws)


def lan_url() -> str:
    """Best-effort LAN address so the QR works from a phone on the same wifi."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return f"http://{ip}:8000"


def main() -> None:
    import argparse
    import uvicorn
    global building, stop_event

    ap = argparse.ArgumentParser(description="chat54 server")
    ap.add_argument("--instance", default=None,
                    help="simulator instance name (omit for ANSI terminal preview)")
    ap.add_argument("--base-url", default="https://sundai.willsarg.com/api")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--brain", default="rules", choices=["rules", "llm"],
                    help="llm needs OPENAI_API_KEY and the openai package; "
                         "falls back to rules on any failure")
    args = ap.parse_args()

    print("chat54 server starting")
    if args.instance:
        building = Building(instance=args.instance, base_url=args.base_url,
                            brain=args.brain)
        print(f"streaming to {args.instance}: "
              f"https://sundai.willsarg.com/{args.instance}?view=close")
    else:
        print("no --instance given: showing ANSI preview in this terminal")
    stop_event = threading.Event()
    threading.Thread(target=run_building_loop, args=(building, stop_event),
                     daemon=True).start()
    building.start_ambient(stop_event)     # 15s room-temperature cycle

    print(f"join the group chat: {lan_url()}   (QR at /qr.svg)")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()

# static assets (controller css/js inline in index.html; mount not needed)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
