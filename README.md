# chat54 — the Green Building group chat

The MIT Green Building (Building 54, 17×9 = 153 lit windows) as a member of your
group chat. People scan a QR code, join on their phones, and **talk to the
building**. The building replies like a person does when texting: an emoji or
two, a short voice line — and because it's a 90-meter concrete body, its real
words are **light**: every reply triggers a named facade behavior (wave-back,
blush, storm, confetti…) in that person's column of the building.

Built for Sundai Hack #140 ("Beyond Tetris: Building-Scale Physical AI"),
September 13, 2026. Drives the event simulator at
https://sundai.willsarg.com via the `gbsim` client; because the behavior layer
only uses the real building's two-method display contract (`makeframe()` /
`send(frame)` at ≤30 fps), the same code runs on the actual building on
September 29.

## How it works

```
phone (scan QR) ──ws──▶ chat54 server ──▶ brain (message → reply) ──▶ director ──▶ facade ──▶ building
        ▲                    │                                                          (17×9 Color frames, 30 fps)
        └────── building's replies appear in the same chat ────────────────────────────┘
```

- **brain** — two interchangeable brains behind one `respond()` interface:
  - `rules` (default): keyword + fuzzy intent matching, zero API keys, instant.
  - `llm`: OpenAI-backed, sees the recent group chat and the running mood, and
    picks the facade behavior from the real menu. Strict JSON contract;
    *any* failure — no key, network error, malformed JSON, hallucinated
    behavior name — falls back to the rule brain, so the demo never dies.
- **director** — a tiny mood state machine. Likes/energy accumulate into a
  persistent mood (grumpy ↔ chill ↔ giddy) that tints the idle animation and
  future replies. Crossfades between behaviors; never hard-cuts.
- **facade** — the behavior library: `draw(frame, t)` functions on a 17×9 grid
  of `Color`. This is the only layer that touches pixels.
- **server** — FastAPI + WebSockets chat room, phone-first controller page,
  prints a QR code to the terminal on startup. One owner of the display
  instance (two frame writers = flicker; the simulator README's rule #1).

## Quickstart

```bash
cd chat54
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# terminal 1 — the building (prints a QR to join)
python -m chat54.building --instance your-instance-name

# terminal 2 — open the printed URL, or scan the QR with a phone
```

Then text it. Try: `hi`, `i love you`, `you suck`, `party!!`, `storm`, `dance`,
`who are you`, `wave at Maya`, `good night`.

## Driving the real simulator

`--instance` is the adjective-animal name the simulator gave you. The building
process is the only thing that sends frames; phones only send chat text, so
there's exactly one frame writer per instance.

With no `--instance` (or `--display dummy`), a big ANSI terminal preview runs
instead — handy for developing on a plane.

### LLM brain (optional)

```bash
export OPENROUTER_API_KEY=sk-or-...   # in .env (gitignored); or OPENAI_API_KEY
python -m chat54.server --instance clever-lynx --brain llm
```

With `--brain llm`, the LLM's **only** job is the **ambient cycle**: every
15 seconds it reads the messages posted since the last cycle (in the context
of the recent chat and its mood) and picks ONE behavior expressing the
room's emotional temperature — or, if the room went quiet, the building just
waves with **zero API calls**. That bounds spend at <=4 requests/min no
matter how fast the room chats. Per-message replies stay instant and free
via the rule brain. Rate limits are respected on both sides: the sim gets
429-aware exponential backoff, the LLM a 2s minimum call spacing.

Set `CHAT54_MODEL` to override the model (defaults to
`liquid/lfm-2.5-2.6b:free` on OpenRouter, `gpt-4o-mini` on OpenAI).

## Layout

```
chat54/
  chat54/             # the app (facade, director, brain, llm_brain, memory, server, …)
  gbsim/              # vendored simulator client (from willsarg/sundai-greenbuilding-sim)
  tests/
  live_test.py        # scripted conversation against a real simulator instance
```

## Test against the simulator

```bash
python live_test.py clever-lynx https://sundai.willsarg.com/api
# watch https://sundai.willsarg.com/clever-lynx?view=close while it runs
```

Server status check (frames counter should climb): `curl -s https://sundai.willsarg.com/api/i/<name>/`

## Contract notes (from the simulator README, worth obeying)

- `send()` at most 30 fps; the sim accepts ≤40 fps per instance.
- Only one process writes frames to an instance.
- Don't put `upload_clip`/`flush`/`close` in behavior code — keep behavior code
  real-building-compatible.
