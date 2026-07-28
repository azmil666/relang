#!/usr/bin/env python3
"""
qrterminal.py

A Python 3 port of the Go project "qrterminal" (https://github.com/mdp/qrterminal).

Renders QR codes to a terminal using:
  * ANSI-colored full blocks
  * Unicode half blocks
  * Sixel graphics (when supported)

The boolean QR matrix itself is generated using the third-party `qrcode`
package; every other piece of behaviour (quiet zone handling, block
rendering, sixel encoding, terminal detection, CLI parsing) is implemented
from scratch.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from typing import List, TextIO

import qrcode
import qrcode.constants


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Full-block rendering: each QR module is drawn as two spaces with an ANSI
# background color, then the color is reset.
WHITE: str = "\x1b[47m  \x1b[0m"
BLACK: str = "\x1b[40m  \x1b[0m"

# Half-block rendering: two vertically stacked QR modules are collapsed into
# a single terminal character using Unicode block-element glyphs.
BLACK_WHITE: str = "\u2580"  # top module black, bottom module white ("▀")
WHITE_BLACK: str = "\u2584"  # top module white, bottom module black ("▄")
BLACK_BLACK: str = "\u2588"  # both modules black                  ("█")
WHITE_WHITE: str = " "       # both modules white                  (" ")

# Quiet zone width, expressed in QR modules, surrounding the code on every
# side, matching the default used by the reference Go implementation.
QUIET_ZONE: int = 2

# Sixel escape sequences and scaling factor (pixels-per-module).
SIXEL_BEGIN: str = "\x1bPq"
SIXEL_END: str = "\x1b\\"
SIXEL_BLOCK_SIZE: int = 4

VALID_LEVELS = ("L", "M", "Q", "H")

_LEVEL_MAP = {
    "L": qrcode.constants.ERROR_CORRECT_L,
    "M": qrcode.constants.ERROR_CORRECT_M,
    "Q": qrcode.constants.ERROR_CORRECT_Q,
    "H": qrcode.constants.ERROR_CORRECT_H,
}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class Config:
    """Rendering configuration, mirroring the Go qrterminal.Config struct."""

    level: str = "L"
    writer: TextIO = field(default_factory=lambda: sys.stdout)

    half_blocks: bool = True

    black_char: str = BLACK
    white_char: str = WHITE
    black_white_char: str = BLACK_WHITE
    white_black_char: str = WHITE_BLACK
    black_black_char: str = BLACK_BLACK
    white_white_char: str = WHITE_WHITE

    quiet_zone: int = QUIET_ZONE

    with_sixel: bool = False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_level(level: str) -> str:
    """Validate a QR error-correction level string, returning it upper-cased.

    Raises ValueError if the level is not one of L, M, Q, H.
    """
    normalized = level.strip().upper()
    if normalized not in VALID_LEVELS:
        raise ValueError(
            f"invalid recovery level {level!r}: must be one of "
            f"{', '.join(VALID_LEVELS)}"
        )
    return normalized


# ---------------------------------------------------------------------------
# Terminal / sixel detection
# ---------------------------------------------------------------------------


def is_sixel_supported() -> bool:
    """Best-effort detection of whether the current terminal supports Sixel.

    There is no fully portable way to query this without doing an
    interactive DA1/DA2 handshake with the terminal, so this implements the
    common heuristic of inspecting well-known environment variables.
    """
    term = os.environ.get("TERM", "")
    term_program = os.environ.get("TERM_PROGRAM", "")

    if "sixel" in term.lower():
        return True

    known_sixel_terms = {
        "mlterm",
        "yaft-256color",
        "foot",
        "foot-extra",
        "st-256color-sixel",
    }
    if term in known_sixel_terms:
        return True

    known_sixel_term_programs = {"iTerm.app", "WezTerm", "mintty"}
    if term_program in known_sixel_term_programs:
        return True

    # GNOME's VTE-based terminals (gnome-terminal, etc.) do not implement
    # Sixel, even though they otherwise look fairly capable.
    if os.environ.get("VTE_VERSION"):
        return False

    if os.environ.get("MLTERM"):
        return True

    return False


# ---------------------------------------------------------------------------
# QR matrix generation
# ---------------------------------------------------------------------------


def _build_qr_matrix(text: str, level: str) -> List[List[bool]]:
    """Build the raw boolean QR matrix (no quiet zone) for `text`."""
    normalized_level = validate_level(level)
    qr = qrcode.QRCode(
        error_correction=_LEVEL_MAP[normalized_level],
        box_size=1,
        border=0,
    )
    qr.add_data(text)
    qr.make(fit=True)
    raw_matrix = qr.get_matrix()
    # qrcode returns True/False already, but normalize defensively in case a
    # future version returns truthy non-bool values.
    return [[bool(cell) for cell in row] for row in raw_matrix]


def _padded_matrix(matrix: List[List[bool]], quiet_zone: int) -> List[List[bool]]:
    """Return `matrix` surrounded by `quiet_zone` modules of white padding."""
    size = len(matrix)
    width = size + 2 * quiet_zone
    padded: List[List[bool]] = []

    blank_row = [False] * width
    for _ in range(quiet_zone):
        padded.append(list(blank_row))

    for row in matrix:
        padded_row = [False] * quiet_zone + list(row) + [False] * quiet_zone
        padded.append(padded_row)

    for _ in range(quiet_zone):
        padded.append(list(blank_row))

    return padded


# ---------------------------------------------------------------------------
# Rendering: full blocks
# ---------------------------------------------------------------------------


def write_full_blocks(matrix: List[List[bool]], config: Config) -> None:
    """Render `matrix` using two-ANSI-colored-space full blocks per module."""
    padded = _padded_matrix(matrix, config.quiet_zone)
    writer = config.writer

    lines: List[str] = []
    for row in padded:
        cells = [config.black_char if cell else config.white_char for cell in row]
        lines.append("".join(cells))

    writer.write("\n".join(lines))
    writer.write("\n")


# ---------------------------------------------------------------------------
# Rendering: half blocks
# ---------------------------------------------------------------------------


def write_half_blocks(matrix: List[List[bool]], config: Config) -> None:
    """Render `matrix` collapsing vertical module pairs into one character."""
    padded = _padded_matrix(matrix, config.quiet_zone)
    writer = config.writer
    height = len(padded)
    width = len(padded[0]) if height else 0

    lines: List[str] = []
    row_index = 0
    while row_index < height:
        top_row = padded[row_index]
        bottom_row = padded[row_index + 1] if row_index + 1 < height else [False] * width

        chars: List[str] = []
        for col_index in range(width):
            top = top_row[col_index]
            bottom = bottom_row[col_index]
            if top and bottom:
                chars.append(config.black_black_char)
            elif (not top) and (not bottom):
                chars.append(config.white_white_char)
            elif top and not bottom:
                chars.append(config.black_white_char)
            else:
                chars.append(config.white_black_char)

        lines.append("".join(chars))
        row_index += 2

    writer.write("\n".join(lines))
    writer.write("\n")


# ---------------------------------------------------------------------------
# Rendering: sixel
# ---------------------------------------------------------------------------


def write_sixel(matrix: List[List[bool]], config: Config) -> None:
    """Render `matrix` as a Sixel graphic scaled by SIXEL_BLOCK_SIZE pixels
    per QR module, with a two-color (white/black) palette.
    """
    padded = _padded_matrix(matrix, config.quiet_zone)
    dim = len(padded)
    block = SIXEL_BLOCK_SIZE
    pixel_width = dim * block
    pixel_height = dim * block
    writer = config.writer

    def is_black_pixel(x: int, y: int) -> bool:
        module_x = x // block
        module_y = y // block
        if 0 <= module_y < dim and 0 <= module_x < dim:
            return padded[module_y][module_x]
        return False

    out: List[str] = []
    out.append(SIXEL_BEGIN)
    out.append(f'"1;1;{pixel_width};{pixel_height}')
    out.append("#0;2;100;100;100")  # color register 0 -> white
    out.append("#1;2;0;0;0")        # color register 1 -> black

    band_start = 0
    while band_start < pixel_height:
        band_layers: List[str] = []
        for color in (0, 1):
            row_chars: List[str] = []
            has_pixel = False
            for x in range(pixel_width):
                bits = 0
                for bit in range(6):
                    y = band_start + bit
                    if y < pixel_height:
                        black = is_black_pixel(x, y)
                        wants_color = black if color == 1 else (not black)
                        if wants_color:
                            bits |= 1 << bit
                            has_pixel = True
                row_chars.append(chr(63 + bits))
            if has_pixel:
                band_layers.append(f"#{color}" + "".join(row_chars))
        out.append("$".join(band_layers))
        out.append("-")
        band_start += 6

    out.append(SIXEL_END)
    writer.write("".join(out))
    writer.write("\n")


# ---------------------------------------------------------------------------
# High level generate functions
# ---------------------------------------------------------------------------


def generate_with_config(text: str, config: Config) -> None:
    """Generate and write a QR code for `text` using an explicit `config`."""
    matrix = _build_qr_matrix(text, config.level)

    if config.with_sixel:
        write_sixel(matrix, config)
    elif config.half_blocks:
        write_half_blocks(matrix, config)
    else:
        write_full_blocks(matrix, config)


def generate(text: str, level: str = "L", writer: TextIO = None) -> None:
    """Generate a QR code for `text` using full-block rendering."""
    if writer is None:
        writer = sys.stdout
    config = Config(level=level, writer=writer, half_blocks=False)
    generate_with_config(text, config)


def generate_half_block(text: str, level: str = "L", writer: TextIO = None) -> None:
    """Generate a QR code for `text` using half-block rendering."""
    if writer is None:
        writer = sys.stdout
    config = Config(level=level, writer=writer, half_blocks=True)
    generate_with_config(text, config)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

__version__ = "3.0.0"


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qrterminal",
        description="Render a QR code to the terminal.",
        add_help=True,
    )
    parser.add_argument(
        "-l",
        dest="level",
        default="L",
        metavar="LEVEL",
        help="QR Code recovery level: L, M, Q or H (default: L)",
    )
    parser.add_argument(
        "-q",
        dest="quiet_zone",
        type=int,
        default=QUIET_ZONE,
        metavar="N",
        help=f"Quiet zone size, in QR modules (default: {QUIET_ZONE})",
    )
    parser.add_argument(
        "-s",
        dest="block_size",
        type=int,
        default=1,
        choices=(1, 2),
        metavar="SIZE",
        help="Block size: 1 - Small (half blocks), 2 - Large (full blocks)",
    )
    parser.add_argument(
        "-v",
        dest="show_version",
        action="store_true",
        help="Print version information and exit",
    )
    parser.add_argument(
        "text",
        nargs="*",
        help="Text to encode. If omitted, read from stdin until EOF.",
    )
    return parser


def main(argv: List[str] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.show_version:
        print(f"qrterminal version {__version__}")
        return 0

    try:
        level = validate_level(args.level)
    except ValueError as exc:
        print(f"qrterminal: {exc}", file=sys.stderr)
        return 1

    if args.text:
        content = " ".join(args.text)
    else:
        content = sys.stdin.read()
        content = content.rstrip("\n")

    if not content:
        print("qrterminal: no content provided", file=sys.stderr)
        return 1

    config = Config(
        level=level,
        writer=sys.stdout,
        half_blocks=(args.block_size == 1),
        quiet_zone=args.quiet_zone,
    )

    generate_with_config(content, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())