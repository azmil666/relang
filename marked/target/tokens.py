"""
tokens.py
=========
Dataclass definitions for every block-level and inline-level token produced
by the lexer/inline-lexer and consumed by the parser/renderer.

These are intentionally "dumb" data containers -- no rendering logic lives
here. Each token mirrors the shape of the token objects produced by the
JS `marked` lexer (fields kept close to the original names so behaviour is
easy to cross-check), but expressed as typed Python dataclasses instead of
loose JS objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# --------------------------------------------------------------------------
# Base
# --------------------------------------------------------------------------
@dataclass
class Token:
    """Base class for all tokens. `raw` is the exact source text consumed."""
    raw: str = ""


# --------------------------------------------------------------------------
# Block-level tokens
# --------------------------------------------------------------------------
@dataclass
class Space(Token):
    """One or more blank lines between blocks."""
    pass


@dataclass
class Hr(Token):
    """Horizontal rule (---, ***, ___)."""
    pass


@dataclass
class Heading(Token):
    depth: int = 1
    text: str = ""           # raw inline source (pre inline-parse)
    tokens: list = field(default_factory=list)  # parsed inline tokens


@dataclass
class Code(Token):
    """Indented or fenced code block."""
    text: str = ""
    lang: Optional[str] = None
    escaped: bool = False


@dataclass
class Paragraph(Token):
    text: str = ""
    tokens: list = field(default_factory=list)


@dataclass
class Text(Token):
    """Block-level 'loose' text token (used inside list items)."""
    text: str = ""
    tokens: list = field(default_factory=list)


@dataclass
class Blockquote(Token):
    text: str = ""
    tokens: list = field(default_factory=list)  # nested block tokens


@dataclass
class ListItem(Token):
    text: str = ""
    task: bool = False
    checked: bool = False
    loose: bool = False
    tokens: list = field(default_factory=list)


@dataclass
class ListToken(Token):
    ordered: bool = False
    start: object = ""     # '' or int
    loose: bool = False
    items: list = field(default_factory=list)  # list[ListItem]


@dataclass
class HTMLBlock(Token):
    text: str = ""
    pre: bool = False
    block: bool = True


@dataclass
class Def(Token):
    tag: str = ""
    href: str = ""
    title: Optional[str] = None


@dataclass
class TableToken(Token):
    header: list = field(default_factory=list)   # list[list[InlineToken]]
    align: list = field(default_factory=list)     # list[Optional[str]]
    rows: list = field(default_factory=list)       # list[list[list[InlineToken]]]
    raw_header: list = field(default_factory=list)
    raw_rows: list = field(default_factory=list)


# --------------------------------------------------------------------------
# Inline-level tokens
# --------------------------------------------------------------------------
@dataclass
class InlineText(Token):
    text: str = ""


@dataclass
class Escape(Token):
    text: str = ""


@dataclass
class HTMLInline(Token):
    text: str = ""


@dataclass
class Link(Token):
    href: str = ""
    title: Optional[str] = None
    text: str = ""
    tokens: list = field(default_factory=list)


@dataclass
class Image(Token):
    href: str = ""
    title: Optional[str] = None
    text: str = ""


@dataclass
class Strong(Token):
    text: str = ""
    tokens: list = field(default_factory=list)


@dataclass
class Em(Token):
    text: str = ""
    tokens: list = field(default_factory=list)


@dataclass
class Codespan(Token):
    text: str = ""


@dataclass
class Br(Token):
    pass


@dataclass
class Del(Token):
    text: str = ""
    tokens: list = field(default_factory=list)


@dataclass
class Checkbox(Token):
    checked: bool = False
