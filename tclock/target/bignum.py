"""
bignum.py - port of bignum.go

Renders large 7-segment-style digits (plus ':' and '.') using box-drawing
unicode characters, in the style of an old digital clock.
"""

HEIGHT = 5
WIDTH = 4

# Same glyph data as the Go version: each digit (0-9), then ':' then '.'
# is HEIGHT lines tall, separated by a blank line (mirrors the Go const).
_NUMBERS = """
 ━━
┃  ┃

┃  ┃
 ━━


   ┃

   ┃


 ━━
   ┃
 ━━
┃
 ━━

 ━━
   ┃
 ━━
   ┃
 ━━


┃  ┃
 ━━
   ┃


 ━━
┃
 ━━
   ┃
 ━━

 ━━
┃
 ━━
┃  ┃
 ━━

 ━━
   ┃

   ┃


 ━━
┃  ┃
 ━━
┃  ┃
 ━━

 ━━
┃  ┃
 ━━
   ┃
 ━━



::





..


"""


def _add_trailing_spaces(s: str, extra: int) -> str:
    return s + " " * (WIDTH + extra - len(s))


_raw_lines = _NUMBERS.split("\n")[1:]
NUMBER_LINES = []
for _i, _line in enumerate(_raw_lines):
    _extra = 1
    if _i >= 10 * (HEIGHT + 1):
        _extra = -1  # no trailing space for colon/dot
    NUMBER_LINES.append(_add_trailing_spaces(_line, _extra))


class Display:
    """Accumulates digits into a multi-line big-number string."""

    def __init__(self):
        self.lines = [""] * HEIGHT
        self.col = 0

    def place_digit(self, ch: str, blink: bool = False):
        if ch.isdigit():
            digit = int(ch)
        elif ch == ".":
            digit = 11 if blink else 10
        else:  # ':' or anything else treated as colon
            digit = 11 if blink else 10
        start = digit * (HEIGHT + 1)
        for i in range(HEIGHT):
            self.lines[i] += NUMBER_LINES[start + i]
        self.col += 1

    def __str__(self):
        return "\n".join(self.lines)


def time_string(num_str: str, blink: bool = False) -> str:
    d = Display()
    for c in num_str:
        d.place_digit(c, blink)
    return str(d)