#!/usr/bin/env python3
"""
marked.py
=========
CLI entry point + top-level `marked(src)` function tying together the
Lexer -> Parser -> Renderer pipeline.

Usage:
    python3 marked.py < input.md
    echo "# hi" | python3 marked.py
"""
from __future__ import annotations

import sys

from lexer import Lexer, scan_link_defs
from parser import Parser
from renderer import Renderer

# Deeply nested constructs (blockquotes, lists) recurse one Python stack
# frame per nesting level in both the lexer and the parser. marked.js has
# no such limit (JS engines typically allow much deeper recursion), so we
# raise Python's default limit to match realistic pathological inputs.
sys.setrecursionlimit(10000)


def marked(src: str) -> str:
    """Compile a markdown string to an HTML string."""
    if src is None:
        return ''
    # Normalize line endings up front (also done again in Lexer.lex, but
    # link-def scanning needs it normalized too).
    src = src.replace('\r\n', '\n').replace('\r', '\n')

    # Pass 1: pull out all link reference definitions anywhere in the doc.
    stripped_src, defs = scan_link_defs(src)

    # Pass 2: block-level tokenize the remaining source.
    lexer = Lexer()
    tokens = lexer.lex(stripped_src)

    # Pass 3: parse + render.
    parser = Parser(links=defs, renderer=Renderer())
    html = parser.parse(tokens)
    return html


def main() -> int:
    src = sys.stdin.read()
    html = marked(src)
    sys.stdout.write(html)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
