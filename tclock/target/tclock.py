#!/usr/bin/env python3
"""
tclock.py - Python port of the Go `tclock` terminal clock.

Supports: digital 7-segment style clock, analog (ASCII) clock, 24h format,
seconds on/off, colon blink, countdown / until modes, basic named/hex color,
and tailing a file (or stdin) while showing the clock in a corner.

NOT ported (tied to the Go `ansipixels` sub-pixel/image blending library,
with no direct equivalent in the standard library):
  - antialiased image-based analog clock (-aa)
  - mouse drag-to-place / bounce / breathing color-blend animation
  - the glowing color "disc" drawn behind the digits

Usage examples:
  python tclock.py
  python tclock.py -analog
  python tclock.py -24 -no-seconds
  python tclock.py -countdown 5m
  python tclock.py -until "3:05 pm"
  python tclock.py -tail somefile.log
  python tclock.py -color blue
"""
import argparse
import os
import shutil
import sys
import time
from datetime import datetime, timedelta

import analog
import bignum
import duration as dur

RESET = "\x1b[0m"
CURSOR_HOME = "\x1b[H"
CLEAR_LINE = "\x1b[K"      # clear from cursor to end of current line
CLEAR_DOWN = "\x1b[J"      # clear from cursor to end of screen
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
ALT_SCREEN_ON = "\x1b[?1049h"   # switch to a dedicated full-screen buffer
ALT_SCREEN_OFF = "\x1b[?1049l"  # restore the normal scrollback buffer


def _write(s: str):
    """
    Write raw bytes to stdout, bypassing Python's text-mode newline
    translation (which on Windows turns every '\\n' into '\\r\\n', even
    inside a string that already has an explicit '\\r\\n').
    """
    sys.stdout.buffer.write(s.encode("utf-8"))
    sys.stdout.buffer.flush()


def _enable_windows_ansi():
    """
    Turn on VT100/ANSI escape-code processing for the Windows console.
    Without this, older cmd.exe / PowerShell hosts print escape codes as
    literal text instead of interpreting them, so "clear screen" never
    happens and every redraw just prints below the last one.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        STD_OUTPUT_HANDLE = -11
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return
        kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except Exception:
        pass  # best effort; worst case we fall back to the old (buggy) behavior

_NAMED_COLORS = {
    "none": None,
    "black": (0, 0, 0),
    "red": (255, 0, 0),
    "green": (0, 200, 0),
    "yellow": (230, 230, 0),
    "orange": (255, 140, 0),
    "blue": (60, 100, 255),
    "purple": (160, 60, 200),
    "cyan": (0, 200, 200),
    "gray": (140, 140, 140),
    "darkgray": (80, 80, 80),
    "white": (255, 255, 255),
    "brightred": (255, 80, 80),
    "brightgreen": (80, 255, 80),
    "brightyellow": (255, 255, 120),
    "brightblue": (120, 160, 255),
    "brightpurple": (200, 120, 255),
    "brightcyan": (120, 255, 255),
}


def parse_color(spec: str):
    """Parse a color name, RRGGBB hex, or 'r,g,b' style string into an (r,g,b) tuple, or None."""
    if spec is None:
        return None
    s = spec.strip()
    if s == "":
        return None
    low = s.lower()
    if low in _NAMED_COLORS:
        return _NAMED_COLORS[low]
    if len(s) == 6 and all(c in "0123456789abcdefABCDEF" for c in s):
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    if "," in s:
        parts = s.split(",")
        if len(parts) == 3:
            try:
                vals = [float(p) for p in parts]
                if max(vals) <= 1.0:  # treat as 0..1 fractions
                    return tuple(int(round(v * 255)) for v in vals)
                return tuple(int(round(v)) for v in vals)
            except ValueError:
                pass
    raise ValueError(f"Unrecognized color: {spec!r}")


def fg(rgb):
    if rgb is None:
        return ""
    r, g, b = rgb
    return f"\x1b[38;2;{r};{g};{b}m"


def duration_ddhhmm(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    minutes = (total_seconds // 60) % 60
    hours = (total_seconds // 3600) % 24
    if delta >= timedelta(hours=24):
        days = total_seconds // 86400
        return f"{days:02d}:{hours:02d}:{minutes:02d}"
    if delta >= timedelta(hours=1):
        return f"{hours:02d}:{minutes:02d}"
    return f"{minutes:02d}"


def duration_string(delta: timedelta, with_seconds: bool) -> str:
    s = duration_ddhhmm(delta)
    if with_seconds:
        s += f":{int(delta.total_seconds()) % 60:02d}"
    return s


# --- Non-blocking single key read, cross platform -----------------------

class KeyReader:
    def __init__(self):
        self.is_windows = os.name == "nt"
        if not self.is_windows:
            import termios
            import tty
            self._termios = termios
            self._tty = tty
            self._fd = sys.stdin.fileno()
            self._old = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)

    def read_key(self):
        """Return a single character if available (non-blocking), else None."""
        if self.is_windows:
            import msvcrt
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                try:
                    return ch.decode("utf-8", errors="ignore")
                except Exception:
                    return None
            return None
        else:
            import select
            r, _, _ = select.select([sys.stdin], [], [], 0)
            if r:
                return sys.stdin.read(1)
            return None

    def close(self):
        if not self.is_windows:
            self._termios.tcsetattr(self._fd, self._termios.TCSADRAIN, self._old)


def term_size():
    sz = shutil.get_terminal_size(fallback=(80, 24))
    return sz.columns, sz.lines


# --- Drawing --------------------------------------------------------------

def build_frame(cfg, now, num_display, blink):
    """Return the list of terminal rows to print for this frame."""
    cols, rows = term_size()
    if cfg.analog and not cfg.count_down:
        lines = analog.render(now, cols, rows - (2 if cfg.text else 0),
                               show_seconds=cfg.seconds, continuous=cfg.continuous)
    else:
        block = bignum.time_string(num_display, blink and cfg.blink_enabled)
        block_lines = block.split("\n")
        bw = max(len(l) for l in block_lines)
        if cfg.boxed:
            top = "╭" + "─" * (bw + 2) + "╮"
            bot = "╰" + "─" * (bw + 2) + "╯"
            lines_ = [top] + ["│ " + l.ljust(bw) + " │" for l in block_lines] + [bot]
        else:
            lines_ = block_lines
        pad_top = max((rows - len(lines_)) // 2, 0)
        lines = [""] * pad_top
        for l in lines_:
            pad_left = max((cols - len(l)) // 2, 0)
            lines.append(" " * pad_left + l)
    return lines


def write_frame(cfg, lines, already_colored=False):
    color = "" if already_colored else fg(cfg.color_rgb)
    reset = "" if already_colored else RESET
    all_lines = list(lines)
    if cfg.text:
        cols, _ = term_size()
        pad_left = max((cols - len(cfg.text)) // 2, 0)
        all_lines.append(" " * pad_left + cfg.text)

    out = [CURSOR_HOME]
    last = len(all_lines) - 1
    for i, l in enumerate(all_lines):
        out.append(color + l + reset + CLEAR_LINE)
        if i != last:
            out.append("\r\n")
    out.append(CLEAR_DOWN)  # wipe any leftover from a previous, taller frame
    _write("".join(out))


class Config:
    def __init__(self, args):
        self.format24 = args.twentyfour
        self.seconds = not args.no_seconds
        self.blink_enabled = not args.no_blink
        self.boxed = args.box
        self.analog = args.analog
        self.continuous = args.c
        self.text = "" if args.text == "none" else args.text
        self.color_rgb = parse_color(args.color)
        self.count_down = False
        self.end = None
        self.tail_path = args.tail

    def format_time(self, now: datetime) -> str:
        if self.format24:
            f = "%H:%M"
        else:
            f = "%I:%M"
        if self.seconds:
            f += ":%S"
        s = now.strftime(f)
        if not self.format24 and s.startswith("0"):
            s = s[1:]
        return s


def build_argparser():
    p = argparse.ArgumentParser(
        prog="tclock",
        description="Terminal clock: digital/analog, countdown, and file tailing.")
    p.add_argument("-24", dest="twentyfour", action="store_true", help="Use 24-hour time format")
    p.add_argument("-analog", action="store_true", help="Analog clock with hour/minute/second hands")
    p.add_argument("-no-seconds", action="store_true", help="Don't show seconds")
    p.add_argument("-no-blink", action="store_true", help="Don't blink the colon")
    p.add_argument("-box", action="store_true", help="Draw a simple box outline around the time")
    p.add_argument("-color", default="red", help="Color name or RRGGBB hex")
    p.add_argument("-c", action="store_true", help="Analog clock updates continuously instead of per-second")
    p.add_argument("-countdown", default=None, help='Countdown duration, e.g. "5m", "3w2d10h"')
    p.add_argument("-until", default=None, help='Countdown until date/time, e.g. "3:05 pm" or "2025-12-25 15:05:00"')
    p.add_argument("-text", default="", help='Extra text under the clock ("none" to disable default countdown text)')
    p.add_argument("-tail", default="", help='Tail the given filename ("-" for stdin) while showing the clock')
    return p


def run_interactive(cfg):
    key_reader = KeyReader()
    tail_file = None
    if cfg.tail_path:
        if cfg.tail_path == "-":
            tail_file = sys.stdin
        else:
            tail_file = open(cfg.tail_path, "r", buffering=1)

    _write(ALT_SCREEN_ON + HIDE_CURSOR)
    blink = False
    prev_second = None
    try:
        while True:
            now = datetime.now()
            if cfg.count_down:
                left = cfg.end - now
                if left.total_seconds() < 0:
                    _write(CURSOR_HOME + f"\a\aTime's up, reached at {now:%H:%M:%S}" + CLEAR_LINE + CLEAR_DOWN)
                    return 0
                num_display = duration_string(left, cfg.seconds)
            else:
                num_display = cfg.format_time(now)

            if now.second != prev_second or cfg.continuous:
                blink = not blink if now.second != prev_second else blink
                prev_second = now.second
                is_analog = cfg.analog and not cfg.count_down
                lines = build_frame(cfg, now, num_display, blink)
                write_frame(cfg, lines, already_colored=is_analog)

            if tail_file is not None:
                line = None
                try:
                    import select
                    if cfg.tail_path == "-" or os.name != "nt":
                        r, _, _ = select.select([tail_file], [], [], 0)
                        if r:
                            line = tail_file.readline()
                except Exception:
                    pass
                if line:
                    _write(line.replace("\n", "\r\n"))

            key = key_reader.read_key()
            if key:
                if key in ("q", "\x03"):
                    if cfg.count_down:
                        _write(CURSOR_HOME + f"Countdown aborted at {now:%H:%M:%S}" + CLEAR_LINE + CLEAR_DOWN)
                        return 1
                    return 0
                if key in ("a", "A"):
                    cfg.analog = not cfg.analog
                if key in ("c", "C"):
                    cfg.continuous = not cfg.continuous

            time.sleep(0.05)
    finally:
        key_reader.close()
        _write(SHOW_CURSOR + ALT_SCREEN_OFF)
        if tail_file is not None and tail_file is not sys.stdin:
            tail_file.close()


def main(argv=None):
    _enable_windows_ansi()
    p = build_argparser()
    args = p.parse_args(argv)
    cfg = Config(args)

    now = datetime.now()
    if args.countdown:
        try:
            delta = dur.parse(args.countdown)
        except dur.DurationParseError as e:
            print(f"Invalid countdown duration: {e}", file=sys.stderr)
            return 1
        cfg.count_down = True
        cfg.end = now + delta
    if args.until:
        try:
            cfg.end = dur.parse_datetime(now, args.until)
        except dur.DateTimeParseError as e:
            print(f"Invalid until time: {e}", file=sys.stderr)
            return 1
        cfg.count_down = True

    if cfg.count_down and cfg.text == "" and args.text != "none":
        fmt = "%H:%M" if cfg.format24 else "%I:%M"
        to_str = cfg.end.strftime(fmt)
        if cfg.end - now >= timedelta(hours=24):
            to_str = cfg.end.strftime("%Y-%m-%d ") + to_str
        extra = ""
        if not cfg.format24 and cfg.end.hour >= 12:
            extra = " pm"
        cfg.text = f"Countdown to {to_str}{extra}"

    return run_interactive(cfg)


if __name__ == "__main__":
    sys.exit(main())