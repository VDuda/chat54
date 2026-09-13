"""Throwaway: objective metrics for every behavior (mean/peak/tail/cuts).

"headroom" = head-room to full white (how much brighter the sim's bloom
could push). Sim demo clips keep idle-ish content near 0.1-0.3 mean.
"""
from chat54 import facade
from chat54.display import Frame, Color

def lum(c):
    return 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b

print(f"{'behavior':<10} {'mean':>5} {'peak':>4} {'head':>5} {'lit%':>4} {'tail%':>5}  cuts")
for name, fn in facade.BEHAVIORS.items():
    dur = fn.duration_ms / 1000
    means, peak, last_lit, prev_end = [], 0, 0.0, None
    cuts = []
    steps = 24
    for i in range(steps + 1):
        t = dur * i / steps
        f = Frame()
        fn(f, t)
        g = facade.gain_for(name)
        if g != 1.0:
            for r in range(f.nrows()):
                for c in range(f.ncols()):
                    col = f[r][c]
                    f[r][c] = Color(col.r * g, col.g * g, col.b * g)
        cells = [lum(f[r][c]) for r in range(f.nrows()) for c in range(f.ncols())]
        mean = sum(cells) / len(cells)
        means.append(mean)
        peak = max(peak, max(cells))
        lit = sum(1 for v in cells if v > 8) / len(cells)
        if i >= steps - 4:                      # last quarter
            last_lit = max(last_lit, lit)
        if prev_end is not None and i > 0:
            jump = abs(mean - prev_end)
            if jump > 25:
                cuts.append(f"t={t:.2f}s:+{jump:.0f}")
        prev_end = mean
    print(f"{name:<10} {sum(means)/len(means):5.1f} {peak:4.0f} {255-peak:5.0f} "
          f"{max(lit for i, m in enumerate(means) if m > 4) * 0 + last_lit * 100:4.0f} "
          f"{last_lit * 100:5.0f}  {', '.join(cuts) or '-'}")
