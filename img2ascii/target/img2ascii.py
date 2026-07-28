#!/usr/bin/env python3
"""
img2ascii.py

Convert an image into ASCII art, with optional ANSI TrueColor rendering.

This is a Python re-implementation of the C "img2ascii" project. It
preserves the original CLI and behavior while re-implementing the core
image-to-ASCII conversion logic manually (no external ASCII-art or
color libraries). Pillow is used only to open, convert (to RGB), and
resize images.
"""

import argparse
import sys
from typing import List, Tuple

from PIL import Image

DEFAULT_PALETTE = (
    "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
)


def parse_args(argv: List[str] = None) -> argparse.Namespace:
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="img2ascii",
        description="Convert an image into ASCII art.",
    )
    parser.add_argument(
        "-i", "--input", required=True, help="required input image"
    )
    parser.add_argument(
        "-o", "--output", default=None, help="optional output text file"
    )
    parser.add_argument(
        "-w", "--width", type=int, default=100,
        help="desired output width in characters",
    )
    parser.add_argument(
        "-c", "--chars", default=None, help="custom ASCII palette"
    )
    parser.add_argument(
        "-g", "--grayscale", action="store_true",
        help="disable ANSI colors",
    )
    parser.add_argument(
        "-p", "--print", dest="print_output", action="store_true",
        help="print to terminal",
    )
    parser.add_argument(
        "-r", "--reverse", action="store_true",
        help="reverse character palette",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true",
        help="print debug information",
    )

    args = parser.parse_args(argv)

    # If -o is omitted, automatically enable printing.
    if not args.output:
        args.print_output = True

    return args


def build_palette(chars: str, reverse: bool) -> str:
    """Build the ASCII palette to use, applying reversal if requested.

    Raises:
        ValueError: if the resulting palette is empty.
    """
    palette = chars if chars is not None else DEFAULT_PALETTE

    if not palette:
        raise ValueError("Palette must not be empty.")

    if reverse:
        palette = palette[::-1]

    return palette


def load_image(path: str) -> Image.Image:
    """Open an image file and convert it to RGB mode.

    Raises:
        OSError: if the image cannot be opened.
    """
    image = Image.open(path)
    image = image.convert("RGB")
    return image


def resize_image(image: Image.Image, width: int) -> Image.Image:
    """Resize an image to the requested character width.

    Maintains aspect ratio while compensating for the fact that
    terminal characters are roughly twice as tall as they are wide.

    Raises:
        ValueError: if width is not a positive integer.
    """
    if width <= 0:
        raise ValueError("Width must be a positive integer.")

    original_width, original_height = image.size

    new_width = width
    new_height = int(original_height * new_width / original_width / 2)

    if new_height < 1:
        new_height = 1

    resized = image.resize((new_width, new_height))
    return resized


def get_intensity(r: int, g: int, b: int) -> int:
    """Compute the perceived luminance/intensity of an RGB pixel."""
    intensity = round(0.299 * r + 0.587 * g + 0.114 * b)
    return intensity


def pixel_to_char(intensity: int, palette: str) -> str:
    """Map an intensity value (0-255) to a character in the palette."""
    palette_len = len(palette)

    if palette_len == 1:
        return palette[0]

    index = int(intensity / (255 / (palette_len - 1)))

    if index < 0:
        index = 0
    if index >= palette_len:
        index = palette_len - 1

    return palette[index]


def render_grayscale(image: Image.Image, palette: str) -> str:
    """Render an image as plain (uncolored) ASCII art."""
    width, height = image.size
    pixels = image.load()

    rows: List[str] = []

    for y in range(height):
        row_chars: List[str] = []
        for x in range(width):
            r, g, b = pixels[x, y]
            intensity = get_intensity(r, g, b)
            row_chars.append(pixel_to_char(intensity, palette))
        rows.append("".join(row_chars))

    return "\n".join(rows) + "\n"


def render_rgb(image: Image.Image, palette: str) -> str:
    """Render an image as ANSI TrueColor ASCII art.

    Only emits a new color escape sequence when the RGB value changes
    from the previous pixel, to keep output size reasonable.
    """
    width, height = image.size
    pixels = image.load()

    output_parts: List[str] = []

    prev_r = -1
    prev_g = -1
    prev_b = -1

    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            intensity = get_intensity(r, g, b)
            char = pixel_to_char(intensity, palette)

            if r != prev_r or g != prev_g or b != prev_b:
                output_parts.append(f"\033[38;2;{r};{g};{b}m")
                prev_r, prev_g, prev_b = r, g, b

            output_parts.append(char)
        output_parts.append("\n")

    output_parts.append("\033[0m")

    return "".join(output_parts)


def write_output(text: str, path: str) -> None:
    """Write rendered ASCII art to a file.

    Raises:
        OSError: if the file cannot be written.
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def print_debug_info(
    input_path: str,
    output_path: str,
    original_size: Tuple[int, int],
    output_size: Tuple[int, int],
    palette: str,
    mode: str,
) -> None:
    """Print debug information about the current run."""
    print("---- DEBUG ----", file=sys.stderr)
    print(f"Input file:        {input_path}", file=sys.stderr)
    print(f"Output file:       {output_path if output_path else '(none)'}",
          file=sys.stderr)
    print(f"Original dims:     {original_size[0]}x{original_size[1]}",
          file=sys.stderr)
    print(f"Output dims:       {output_size[0]}x{output_size[1]}",
          file=sys.stderr)
    print(f"Palette length:    {len(palette)}", file=sys.stderr)
    print(f"Palette:           {palette}", file=sys.stderr)
    print(f"Rendering mode:    {mode}", file=sys.stderr)
    print("---------------", file=sys.stderr)


def main(argv: List[str] = None) -> int:
    """Entry point. Returns a process exit code."""
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        # argparse already printed a usage/error message.
        return exc.code if isinstance(exc.code, int) else 2

    try:
        palette = build_palette(args.chars, args.reverse)
    except ValueError as exc:
        print(f"Error: invalid palette: {exc}", file=sys.stderr)
        return 1

    try:
        image = load_image(args.input)
    except FileNotFoundError:
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: could not open image '{args.input}': {exc}",
              file=sys.stderr)
        return 1

    original_size = image.size

    try:
        resized = resize_image(image, args.width)
    except ValueError as exc:
        print(f"Error: invalid width: {exc}", file=sys.stderr)
        return 1

    mode = "grayscale" if args.grayscale else "rgb"

    if args.grayscale:
        rendered = render_grayscale(resized, palette)
    else:
        rendered = render_rgb(resized, palette)

    if args.debug:
        print_debug_info(
            args.input,
            args.output,
            original_size,
            resized.size,
            palette,
            mode,
        )

    if args.output:
        try:
            write_output(rendered, args.output)
        except OSError as exc:
            print(f"Error: could not write output file "
                  f"'{args.output}': {exc}", file=sys.stderr)
            return 1

    if args.print_output:
        print(rendered)

    return 0


if __name__ == "__main__":
    sys.exit(main())
