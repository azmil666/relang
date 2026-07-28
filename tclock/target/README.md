# tclock (Python port)

A Python port of the Go `tclock` terminal clock (digital/analog clock,
countdown timer, and file-tailing clock overlay).

## Files

- `tclock.py` — CLI entry point, argument parsing, drawing, and the main loop
- `bignum.py` — big 7-segment-style digit renderer (port of `bignum.go`)
- `analog.py` — ASCII analog clock face renderer (simplified port of `analog.go`)
- `duration.py` — duration/date parsing with `d` (day) / `w` (week) units (port of `duration.go`)

## Requirements

Python 3.8+, standard library only (no third-party packages).
On Windows, run from `cmd.exe`, PowerShell, or Windows Terminal — all support
the ANSI escape codes used here.

## Run

```bash
python tclock.py
python tclock.py -analog
python tclock.py -24 -no-seconds
python tclock.py -countdown 5m
python tclock.py -countdown 3w2d10h
python tclock.py -until "3:05 pm"
python tclock.py -color blue
python tclock.py -tail somefile.log
python tclock.py -tail -          # tail stdin
```

While running:
- `a` — toggle analog mode
- `c` — toggle continuous (sub-second) analog updates
- `q` or Ctrl-C — quit (aborts a countdown if one is running)

## Flags

| Flag | Meaning |
|---|---|
| `-24` | 24-hour time format |
| `-analog` | ASCII analog clock face instead of digital digits |
| `-no-seconds` | Hide the seconds field / second hand |
| `-no-blink` | Don't blink the colon |
| `-box` | Draw a simple box around the digital time |
| `-color NAME\|RRGGBB` | Foreground color |
| `-c` | Continuous (sub-second) analog updates |
| `-countdown DURATION` | Count down from a duration (`5m`, `3w2d10h`, etc.) |
| `-until "TIME"` | Count down until a date/time |
| `-text "..."` | Extra text under the clock (`"none"` to suppress) |
| `-tail FILE` | Tail a file (or `-` for stdin) while showing the clock |

## What's different from the Go original

The Go version is built on a custom terminal-graphics library
(`fortio.org/terminal/ansipixels`) that does true-color ANSI blending,
half-character-cell ("sub-pixel") line drawing, and image scaling to
terminal cells. There's no drop-in equivalent for that in Python's standard
library, so a few features were **intentionally left out** rather than
half-ported:

- **Antialiased image-based analog clock (`-aa`)** — the original renders
  hands into a real image buffer and downsamples it to terminal cells with
  anti-aliasing. This port's `-analog` mode uses a plain-character grid
  instead (still shows the correct hands and hour marks, just blockier).
- **Mouse click-and-drag placement, bounce, and "breathing" color pulse** —
  these depend on raw mouse tracking and per-pixel color blending from the
  original library.
- **The glowing color "disc" behind the digits** — a blended-color circle
  drawn behind the big digits; omitted since it relied on the same
  sub-pixel blending code.

Everything else — digital/analog modes, 24h format, seconds/blink toggles,
countdown & until modes (including day/week duration parsing), color
selection, boxed digits, and file/stdin tailing — is fully ported and
functional.