"""
utils.py
========
Small, pure helper functions shared by the lexer, inline lexer and
renderer. Kept dependency-free and side-effect-free.
"""
from __future__ import annotations

import re
from html.entities import html5 as _HTML5_ENTITIES

# --------------------------------------------------------------------------
# HTML escaping (matches marked's `escape()` helper)
# --------------------------------------------------------------------------
_ESCAPE_REPLACEMENTS = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
}
_ESCAPE_REPLACE_RE = re.compile(r'[&<>"\']')
_ESCAPE_REPLACE_NO_ENCODE_RE = re.compile(
    r'[<>"\']|&(?!(#\d+|#[Xx][a-fA-F0-9]+|\w+);)'
)


def escape(html: str, encode: bool = False) -> str:
    """Escape &, <, >, ", ' for safe HTML output.

    When encode is False (the default used almost everywhere in marked),
    an ampersand that is already part of a valid entity is left alone.
    """
    pattern = _ESCAPE_REPLACE_RE if encode else _ESCAPE_REPLACE_NO_ENCODE_RE

    def _sub(m: re.Match) -> str:
        c = m.group(0)
        first = c[0]
        return _ESCAPE_REPLACEMENTS.get(first, c)

    return pattern.sub(_sub, html)


# --------------------------------------------------------------------------
# Unescape HTML entities (used when resolving link/title text, code, etc.)
# --------------------------------------------------------------------------
_ENTITY_RE = re.compile(r'&(#(?:\d+)|#[Xx][a-fA-F0-9]+|\w+);')


def _decode_entity(entity_body: str) -> str:
    if entity_body.startswith('#'):
        try:
            if entity_body[1] in 'xX':
                code = int(entity_body[2:], 16)
            else:
                code = int(entity_body[1:], 10)
            if code == 0:
                return '\ufffd'
            return chr(code)
        except (ValueError, OverflowError):
            return '&' + entity_body + ';'
    name = entity_body + ';'
    if name in _HTML5_ENTITIES:
        return _HTML5_ENTITIES[name]
    return '&' + entity_body + ';'


def unescape(html: str) -> str:
    """Decode HTML entities, e.g. for use inside link hrefs / titles."""
    def repl(m: re.Match) -> str:
        return _decode_entity(m.group(1))
    return _ENTITY_RE.sub(repl, html)


# --------------------------------------------------------------------------
# Backslash-escape decoding (for final text nodes)
# --------------------------------------------------------------------------
_BACKSLASH_ESCAPE_CHARS = re.escape(r"""\`*{}[]()#+-.!_>~|"'$%&,/:;<=?@^""")
_UNESCAPE_TEST = re.compile(r'\\([' + _BACKSLASH_ESCAPE_CHARS + r'])')


def unescape_backslashes(text: str) -> str:
    return _UNESCAPE_TEST.sub(lambda m: m.group(1), text)


# --------------------------------------------------------------------------
# Misc helpers
# --------------------------------------------------------------------------
def clean_url_href(href: str) -> str:
    """Mirror marked's cleanUrl: trims and leaves the URL otherwise intact."""
    return href.strip()


def rtrim(text: str, char: str, invert: bool = False) -> str:
    """Trim trailing repeats of `char` from `text` (mirrors marked's rtrim)."""
    if not text:
        return text
    i = len(text)
    while i > 0:
        c = text[i - 1]
        if (c == char) != invert:
            i -= 1
        else:
            break
    return text[:i]


def find_closing_bracket(s: str, open_close: str = "[]") -> int:
    """Given a string starting just after an opening bracket char, find the
    index of the matching closing bracket, honoring nesting. Returns -1 if
    not found."""
    open_ch, close_ch = open_close[0], open_close[1]
    if open_ch not in s:
        return -1
    level = 1
    for i, ch in enumerate(s):
        if ch == '\\':
            continue
        elif ch == open_ch:
            level += 1
        elif ch == close_ch:
            level -= 1
            if level == 0:
                return i
    return -1
