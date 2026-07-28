"""
analog.py - port of analog.go

Renders an ASCII-art analog clock face into a grid of characters, using the
same hand-length ratios and per-hand colors as the Go source (hour=orange,
minute=blue, second=green). The vertical axis is scaled by 1/2 to correct
for terminal character cells being roughly twice as tall as wide (the Go
original achieves the same correction via half-character-cell "subpixel"
drawing, using 2x vertical resolution internally).

Note: the original also anti-aliases and blends hand colors at the pixel
level; this port draws solid single-resolution characters instead, since
there is no equivalent terminal pixel-blending library in the standard
library.
"""
import math

HOUR_COLOR = (255, 0xA7, 10)      # matches analog.go DrawHands hour color
MINUTE_COLOR = (0x2C, 0x59, 0xD4)  # #2C59D4
SECOND_COLOR = (0x50, 0x80, 0x50)
FACE_COLOR = None  # use terminal default for numbers/dots/center

HOUR_CHAR = "#"
MINUTE_CHAR = "*"
SECOND_CHAR = "."
CENTER_CHAR = "+"

RESET = "\x1b[0m"


def _fg(rgb):
    if rgb is None:
        return ""
    r, g, b = rgb
    return f"\x1b[38;2;{r};{g};{b}m"


def _rotate_from_12(theta: float, radius: float):
    return -math.sin(theta) * radius, -math.cos(theta) * radius


def _calculate_angle(max_v: float, value: float) -> float:
    return 2.0 * math.pi * (max_v - value) / max_v


def _angle_coords(max_v: float, value: float, radius: float):
    """Returns (dx, dy) in the same double-density units used by the Go source."""
    return _rotate_from_12(_calculate_angle(max_v, value), radius)


def _to_char(cx, cy, dx, dy):
    """Map a (dx, dy) offset in double-density units to an integer (x, y) character cell."""
    return cx + round(dx), cy + round(dy / 2.0)


def _bresenham(x0: int, y0: int, x1: int, y1: int):
    points = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
    return points


def render(now, width: int, height: int, show_seconds: bool = True, continuous: bool = False):
    """
    Render an analog clock into a list of `height` ANSI-colored strings,
    each rendering to `width` chars wide. `now` is a datetime.datetime.
    Colors are baked into the returned strings (each line ends with a reset),
    so callers should NOT wrap these lines in another foreground color.
    """
    width = max(width, 15)
    height = max(height, 8)
    r = min(width // 2, height) - 1
    r = max(r, 6)
    cx = width // 2
    cy = height // 2

    grid = [[(" ", None)] * width for _ in range(height)]

    def plot(x, y, ch, color):
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] = (ch, color)

    def draw_hand(dx, dy, ch, color):
        x1, y1 = _to_char(cx, cy, dx, dy)
        for (x, y) in _bresenham(cx, cy, x1, y1):
            plot(x, y, ch, color)

    sec = now.second + (now.microsecond / 1e6 if continuous else 0.0)
    minute = now.minute
    hour = now.hour

    m = minute + sec / 60.0
    # Same ratios as Go's DrawHands: hour .47r, minute .80r, second .90r.
    hx, hy = _angle_coords(12, (hour % 12) + m / 60.0, 0.47 * r)
    mx, my = _angle_coords(60, m, 0.80 * r)

    draw_hand(hx, hy, HOUR_CHAR, HOUR_COLOR)
    draw_hand(mx, my, MINUTE_CHAR, MINUTE_COLOR)
    if show_seconds:
        sx, sy = _angle_coords(60, sec, 0.90 * r)
        draw_hand(sx, sy, SECOND_CHAR, SECOND_COLOR)

    # Clock face: hour numbers (and minute tick dots if seconds are shown).
    for n in range(1, 61):
        nx, ny = _angle_coords(60, n % 60, float(r))
        x, y = _to_char(cx, cy, nx, ny)
        if n % 5 == 0:
            label = str(n // 5)
            lx = x - (1 if len(label) > 1 else 0)
            for i, ch in enumerate(label):
                plot(lx + i, y, ch, FACE_COLOR)
        elif show_seconds:
            plot(x, y, "\u00b7", FACE_COLOR)  # middle dot

    plot(cx, cy, CENTER_CHAR, FACE_COLOR)

    # Render each row to a single ANSI string, only emitting color codes on change.
    lines = []
    for row in grid:
        parts = []
        current = "__unset__"
        for ch, color in row:
            if color != current:
                parts.append(_fg(color) if color else RESET)
                current = color
            parts.append(ch)
        parts.append(RESET)
        lines.append("".join(parts))
    return lines