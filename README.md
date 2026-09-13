# chat54 — the Green Building group chat

The MIT Green Building (Building 54, 17×9 = 153 lit windows) joins your group
chat. People scan a QR code and talk among themselves on their phones — and
every 15 seconds the building **reads the room** and performs the group's
emotional temperature in light. It never replies to individual messages; it
answers the *vibe*. Before every performance it counts down **3 … 2 … 1** on
both media at once: giant warm digits on the glass, keycaps in the chat.

Built for Sundai Hack #140 ("Beyond Tetris: Building-Scale Physical AI"),
September 13, 2026. Drives the event simulator at https://sundai.willsarg.com
via the vendored `gbsim` client; because the behavior layer only uses the real
building's two-method display contract (`makeframe()` / `send(frame)` at
≤30 fps), the same code runs on the actual building on September 29.

## What a cycle looks like

```
people chat among themselves          building: (breathing idle, silent)
        │
        ▼ every 15s
   ┌─ room quiet? ── yes ──▶ silent wave, zero API calls
   └─ new messages?
        └─ brain reads ONLY the messages since last cycle (context: recent
           chat + mood) and picks ONE show: vibe read + facade behavior
        ▼
FACADE: 3 … 2 … 1   (big warm digits, ~3s)      CHAT: 3️⃣ 2️⃣ 1️⃣ (big keycaps)
FACADE: the show (confetti, blush, grumble…)    CHAT: 🎉 vibe: hyped — showing confetti — line
        ▼
back to breathing idle
```

The reveal message in chat **names the decision**: the vibe the brain read
("hyped", "tense", "focused"…), the show it chose, and a short in-persona
line. Explicit requests outrank the vibe read: "dance for me" makes it dance.

## The show vocabulary

| show | looks like | triggered by |
|---|---|---|
| `confetti` | colorful cells popping and raining | real celebration, "party", requests |
| `blush` | pink bloom spreading up the tower | love, compliments |
| `grumble` | red flicker rising from lower floors | negativity, storms |
| `dance` | rainbow equalizer columns | "dance for me", high energy |
| `heartbeat` | two warm thumps from the center | affection, "heartbeat", reassurance |
| `wave` | diagonal sweep up and down | default — calm talk, quiet rooms |
| `look` | bright scanning band, side to side | direction, alertness, tension |
| `story` | slow rainbow rolling up | "who are you" |
| `bow`, `goodnight` | center pulse / floors dimming with one winking window | thanks / goodnight |

Idle between cycles: `breathe` (dim aurora) tinted by the persistent mood, and
`listen`. Brightness is calibrated per show in `FACADE_GAIN` (facade.py)
against the simulator's core-lift + bloom rendering.

## Quickstart

```bash
cd chat54
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# the whole show — building + chat room + QR (recommended)
python -m chat54.server --instance clever-lynx

# phones: open the printed URL or scan /qr.svg (same wifi as the laptop)
# watch:  https://sundai.willsarg.com/clever-lynx?view=close
```

With no `--instance`, the building renders as an ANSI preview in the terminal
instead — full functionality, no network.

## Brains

Two interchangeable brains behind one interface:

- **`rules`** (default) — keyword + fuzzy matching, instant, free, no API key.
  The 15s ambient read uses a request-first keyword table (dance, heartbeat,
  goodnight, storm, then vibe words).
- **`llm`** — an LLM's *only* job is the 15s ambient read: it sees the NEW
  messages since last cycle, the recent chat, the mood, and the real behavior
  menu, and returns strict JSON (emoji, behavior, energy, line, 1–3-word vibe
  read). Every failure — no key, timeout, empty content, hallucinated
  behavior — falls back to rules or to silence for that cycle. Quota is
  bounded at ≤4 calls/min (0 when the room is quiet); calls are throttled ≥2s
  apart.

```bash
# .env (gitignored): OPENROUTER_API_KEY=sk-or-...   (or OPENAI_API_KEY)
python -m chat54.server --instance clever-lynx --brain llm
# CHAT54_MODEL overrides the model (default liquid/lfm-2.5-2.6b:free on
# OpenRouter, gpt-4o-mini on OpenAI). The free liquid model reasons
# mandatorily; reasoning is capped at 600 tokens to avoid empty answers.
```

## Rate limits, respected

- **Simulator: ≤40 fps per instance, total.** The render loop is 30 fps and
  the frame pump spaces POSTs ≥1/30s (no bursts), backs off exponentially
  1.5s→10s on 429, and recovers on success. **One frame writer per instance**
  — server *or* `live_test.py` *or* `tuning_tour.py`, never two at once.
- **OpenRouter free tier:** one call per 15s cycle, throttled, zero when quiet.

## Layout

```
chat54/
  chat54/
    display.py     # the real building's contract, verbatim (Color/Frame/Display)
    facade.py      # 13 behaviors + countdown digits + FACADE_GAIN table
    director.py    # mood machine, crossfades, countdown→show chaining
    brain.py       # rules brain: requests + vibe keywords, per-user memory
    llm_brain.py   # LLM ambient room-read (OpenRouter/OpenAI), strict JSON
    memory.py      # per-user sentiment/visits, JSON persisted
    building.py    # 30fps loop, ambient 15s cycle, countdown chat mirror, jsonl log
    displays.py    # GBSimDisplay (sim) / ANSI DummyDisplay
    server.py      # FastAPI + WebSocket room + QR + outbox fan-out
    static/        # phone controller page (countdown keycaps, quick actions)
  gbsim/           # vendored sim client (from willsarg/sundai-greenbuilding-sim)
  tests/           # 59 tests: brains, facade, director, ambient, backoff
  live_test.py     # scripted conversation against a sim instance
  tuning_tour.py   # play every show in sequence for by-eye tuning
  tune_report.py   # luminance metrics per behavior (mean/peak/tail/cuts)
  display_options_test.py  # what each chat vibe displays, both brains
  vibe_verify.py   # prove the LLM reads the discussion (prompt capture + live)
  live_verify.py   # end-to-end timeline vs the sim's real frame content
```

## State on disk (gitignored)

- `chat54_memory.json` — per-user sentiment/visits ("back again, vlad?")
- `chat_log.jsonl` — every chat message (user, text, timestamp)

Usernames are trimmed and lowercased, so "Vlad Duda" and "vlad duda" are one
friend, not two.

## Testing utilities

```bash
python -m pytest tests/ -q                                    # 59 tests, offline
python live_test.py clever-lynx https://sundai.willsarg.com/api
python tuning_tour.py clever-lynx https://sundai.willsarg.com/api
python display_options_test.py        # shows what each vibe displays (4 API calls)
python vibe_verify.py                 # proves the chat is the LLM's input
curl -s https://sundai.willsarg.com/api/i/<name>/   # frames counter = health
```

## Contract notes (from the simulator README, worth obeying)

- `send()` at most 30 fps; the sim accepts ≤40 fps per instance, total.
- Only one process writes frames to an instance (two = 429 fights).
- Behavior code only touches `Frame`/`Color` — keep it real-building-compatible
  (no `upload_clip`/`flush`/`close` outside display plumbing).
- Demo-day wifi: phones and laptop on the same network; venue wifi often
  isolates clients — use a phone hotspot for laptop + phones.
