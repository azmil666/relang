"""
inline.py
=========
Inline-level tokenizer. Converts a run of inline markdown source into a
flat-but-nestable list of inline tokens (Text, Strong, Em, Codespan, Link,
Image, Br, Del, Escape, HTMLInline, Checkbox).

This mirrors the *behaviour* of marked's InlineLexer/Tokenizer, implemented
independently in Python with regexes tuned to match marked's GFM ruleset.
"""
from __future__ import annotations

import re
from typing import Optional

from tokens import (
    InlineText, Escape, HTMLInline, Link, Image, Strong, Em, Codespan, Br,
    Del, Checkbox,
)
from utils import escape, unescape, find_closing_bracket, rtrim

# --------------------------------------------------------------------------
# Regexes
# --------------------------------------------------------------------------
ESCAPE_RE = re.compile(r'^\\([!"#$%&\'()*+,\-./:;<=>?@\[\]\\^_`{|}~])')

AUTOLINK_RE = re.compile(
    r'^<([a-zA-Z][a-zA-Z0-9+.\-]{1,31}:[^\s\x00-\x1f<>]*|'
    r'[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~\-]+@[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
    r'(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)+)>'
)

URL_AUTOLINK_RE = re.compile(
    r'^((?:ftp|https?)://|www\.)([a-zA-Z0-9\-]+\.?)+[^\s<]*',
)

# raw inline HTML tag
_TAG_NAME = r'[a-zA-Z][a-zA-Z0-9\-]*'
_ATTR = r'''(?:\s+[a-zA-Z:_][\w.:\-]*(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?)'''
HTML_TAG_RE = re.compile(
    r'^(?:'
    r'<' + _TAG_NAME + _ATTR + r'*\s*/?>'         # open tag
    r'|</' + _TAG_NAME + r'\s*>'                   # close tag
    r'|<!--(?:-?[^>-])*(?:-{2,}>|>)'                # comment
    r'|<\?[\s\S]*?\?>'                              # processing instruction
    r'|<![a-zA-Z]+\s[\s\S]*?>'                      # declaration
    r'|<!\[CDATA\[[\s\S]*?\]\]>'                    # CDATA
    r')'
)

CODESPAN_RE = re.compile(r'^(`+)([^`]|[^`][\s\S]*?[^`])\1(?!`)')

BR_RE = re.compile(r'^( {2,}|\\)\n(?!\s*$)')

DEL_RE = re.compile(r'^(~~?)(?=[^\s~])([\s\S]*?[^\s~])\1(?=[^~]|$)')

# emphasis / strong: use marked's punctuation-aware approach (simplified but
# handles the common + GFM-tested cases: **, __, *, _, ***, ___, and mixed
# nesting)
_PUNCT = r'''!"#$%&'()*+,\-./:;<=>?@\[\]`^{}|~'''

EM_STRONG_L_DELIM = re.compile(
    r'^(?:\*\*(?=[*])|\*\*[^\s*]|\*(?=[^\s*])|__(?=[^\s_])|_(?=[^\s_]))'
)


def _make_link_paren_matcher(s: str) -> Optional[re.Match]:
    return None


LINK_LABEL_RE = re.compile(r'^!?\[((?:\[[^\[\]]*\]|\\.|[^\[\]\\])*)\]')

LINK_HREF_TITLE_RE = re.compile(
    r'''^\(\s*(<(?:\\[<>]?|[^\s<>\\])*>|(?:\\[()]?|\([^\s\x00-\x1f\\]*\)|[^\s\x00-\x1f()\\])*?)'''
    r'''(?:\s+("(?:\\"?|[^"\\])*"|'(?:\\'?|[^'\\])*'|\((?:\\\)?|[^)\\])*\)))?\s*\)'''
)

REFLINK_RE = re.compile(r'^!?\[((?:\[[^\[\]]*\]|\\.|[^\[\]\\])*)\]\s*\[((?:\\.|[^\[\]\\])*)\]')
NOLINK_RE = re.compile(r'^!?\[((?:\[[^\[\]]*\]|\\.|[^\[\]\\])*)\]')

ENTITY_INLINE_RE = re.compile(r'&(#\d+|#[Xx][a-fA-F0-9]+|[a-zA-Z][a-zA-Z0-9]{1,31});')


class InlineLexer:
    """Tokenizes inline markdown source into a list of inline Token objects."""

    def __init__(self, links: dict):
        # links: dict[normalized-label] -> {'href': str, 'title': Optional[str]}
        self.links = links or {}

    # ------------------------------------------------------------------
    def tokenize(self, src: str, in_link: bool = False, in_emphasis: bool = False) -> list:
        tokens = []
        text_buffer = []

        def flush_text():
            if text_buffer:
                tokens.append(InlineText(text=escape("".join(text_buffer), encode=False)))
                text_buffer.clear()

        while src:
            # escape
            m = ESCAPE_RE.match(src)
            if m:
                flush_text()
                tokens.append(Escape(text=escape(m.group(1))))
                src = src[m.end():]
                continue

            # inline html tag
            m = HTML_TAG_RE.match(src)
            if m:
                flush_text()
                tokens.append(HTMLInline(text=m.group(0)))
                src = src[m.end():]
                continue

            # autolink <scheme:...> / <email>
            m = AUTOLINK_RE.match(src)
            if m:
                flush_text()
                text = m.group(1)
                if '@' in text and '://' not in text and not re.match(r'^[a-zA-Z][a-zA-Z0-9+.\-]*:', text):
                    href = 'mailto:' + text
                else:
                    href = text
                tokens.append(Link(href=href, title=None, text=escape(text), tokens=[InlineText(text=escape(text))]))
                src = src[m.end():]
                continue

            # GFM bare url autolink
            m = URL_AUTOLINK_RE.match(src)
            if m and not in_link:
                url = m.group(0)
                url = rtrim(url, '.', invert=False)
                # trim trailing punctuation commonly excluded by marked
                while url and url[-1] in ')]}.,;:!?\'"' and url.count('(') < url.count(')'):
                    url = url[:-1]
                trimmed_len = len(url)
                flush_text()
                href = url if '://' in url else 'http://' + url
                tokens.append(Link(href=href, title=None, text=escape(url), tokens=[InlineText(text=escape(url))]))
                src = src[trimmed_len:]
                continue

            # code span
            m = CODESPAN_RE.match(src)
            if m:
                flush_text()
                content = m.group(2)
                content = re.sub(r'\n', ' ', content)
                if re.match(r'^ ', content) and re.search(r'[^ ]', content) and content.endswith(' '):
                    content = content[1:-1]
                tokens.append(Codespan(text=escape(content, encode=True)))
                src = src[m.end():]
                continue

            # line break
            m = BR_RE.match(src)
            if m:
                flush_text()
                tokens.append(Br())
                src = src[m.end(1):]
                continue

            # images / links
            m = LINK_LABEL_RE.match(src)
            if m:
                consumed = self._try_link(src, in_link)
                if consumed is not None:
                    flush_text()
                    tok, length = consumed
                    tokens.append(tok)
                    src = src[length:]
                    continue

            m = REFLINK_RE.match(src) or NOLINK_RE.match(src)
            if m:
                consumed = self._try_reflink(src, in_link)
                if consumed is not None:
                    flush_text()
                    tok, length = consumed
                    tokens.append(tok)
                    src = src[length:]
                    continue

            # strong / em
            prev_char = text_buffer[-1][-1] if text_buffer and text_buffer[-1] else ''
            consumed = self._try_emphasis(src, in_link, prev_char)
            if consumed is not None:
                flush_text()
                tok, length = consumed
                tokens.append(tok)
                src = src[length:]
                continue

            # strikethrough (GFM)
            m = DEL_RE.match(src)
            if m:
                flush_text()
                inner = m.group(2)
                tokens.append(Del(text=inner, tokens=self.tokenize(inner, in_link)))
                src = src[m.end():]
                continue

            # html entity -- passed through as-is; it's already valid HTML
            m = ENTITY_INLINE_RE.match(src)
            if m:
                text_buffer.append(m.group(0))
                src = src[m.end():]
                continue

            # plain text: consume up to the next special char, or up to a
            # hard-break sequence (2+ trailing spaces before a newline) so
            # BR_RE gets a chance to match it on the next iteration.
            m = re.match(
                r'^[\s\S]+?(?=[\\<!\[_*`~^&]| {2,}\n|https?://|ftp://|www\.|$)', src
            )
            if m and m.group(0):
                text_buffer.append(m.group(0))
                src = src[m.end():]
                continue
            else:
                # fallback: consume one character to guarantee progress
                text_buffer.append(src[0])
                src = src[1:]

        flush_text()
        return tokens

    # ------------------------------------------------------------------
    def _try_link(self, src: str, in_link: bool):
        m = LINK_LABEL_RE.match(src)
        if not m:
            return None
        is_image = src[0] == '!'
        label = m.group(1)
        rest = src[m.end():]
        hm = LINK_HREF_TITLE_RE.match(rest)
        if not hm:
            return None
        href_raw = hm.group(1)
        title_raw = hm.group(2)

        if href_raw.startswith('<') and href_raw.endswith('>'):
            href = href_raw[1:-1]
        else:
            href = href_raw
        href = unescape(href).strip() if False else href
        href = self._resolve_escapes(href)

        title = None
        if title_raw:
            title = title_raw[1:-1]
            title = self._resolve_escapes(title)

        total_len = m.end() + hm.end()

        if is_image:
            return Image(href=href, title=title, text=escape(label)), total_len
        else:
            if in_link:
                # nested links are not allowed; treat as plain text (rare edge case)
                pass
            inner_tokens = self.tokenize(label, in_link=True)
            return Link(href=href, title=title, text=label, tokens=inner_tokens), total_len

    def _resolve_escapes(self, s: str) -> str:
        return re.sub(r'\\([!"#$%&\'()*+,\-./:;<=>?@\[\]\\^_`{|}~])', r'\1', s)

    # ------------------------------------------------------------------
    def _try_reflink(self, src: str, in_link: bool):
        is_image = src[0] == '!'
        m = REFLINK_RE.match(src)
        if m and m.group(2).strip():
            label = m.group(1)
            ref_label = m.group(2)
        else:
            m = NOLINK_RE.match(src)
            if not m:
                return None
            label = m.group(1)
            ref_label = label

        key = re.sub(r'\s+', ' ', ref_label).strip().lower()
        link_def = self.links.get(key)
        if not link_def:
            return None

        total_len = m.end()
        href = link_def['href']
        title = link_def.get('title')

        if is_image:
            return Image(href=href, title=title, text=escape(label)), total_len
        else:
            inner_tokens = self.tokenize(label, in_link=True)
            return Link(href=href, title=title, text=label, tokens=inner_tokens), total_len

    # ------------------------------------------------------------------
    def _try_emphasis(self, src: str, in_link: bool, prev_char: str = ''):
        """Detect **strong**, *em*, ***strong-em***, __strong__, _em_ with
        left/right flanking delimiter rules approximating marked's."""
        c = src[0]
        if c not in ('*', '_'):
            return None

        m = re.match(r'^(\*{1,3}|_{1,3})', src)
        if not m:
            return None
        delim = m.group(1)
        marker = delim[0]
        dlen = len(delim)

        # underscore emphasis is not allowed intraword: reject if the char
        # immediately before the opening run is itself a word character.
        if marker == '_' and prev_char and re.match(r'\w', prev_char):
            return None

        # try longest delimiter runs first: 3, then 2, then 1
        for n in (min(dlen, 3), 2, 1):
            if n > dlen:
                continue
            open_delim = marker * n
            if not src.startswith(open_delim):
                continue
            body = src[n:]
            if not body or body[0] in (' ', '\t', '\n'):
                continue
            idx = 0
            found_end = -1
            while True:
                pos = body.find(open_delim, idx)
                if pos == -1:
                    break
                # can't be escaped, and preceding char must not be whitespace
                if pos > 0 and body[pos - 1] in (' ', '\t', '\n'):
                    idx = pos + 1
                    continue
                # count backslashes immediately before
                bs = 0
                k = pos - 1
                while k >= 0 and body[k] == '\\':
                    bs += 1
                    k -= 1
                if bs % 2 == 1:
                    idx = pos + 1
                    continue
                # underscore closing delim must not be followed by a word char
                if marker == '_':
                    after_pos = pos + n
                    if after_pos < len(body) and re.match(r'\w', body[after_pos]):
                        idx = pos + 1
                        continue
                found_end = pos
                break
            if found_end == -1:
                continue
            inner = body[:found_end]
            if not inner:
                continue
            total_len = n + found_end + n
            if n == 3:
                # *** => strong(em())
                inner_tokens = self.tokenize(inner, in_link)
                em_tok = Em(text=inner, tokens=inner_tokens)
                return Strong(text=inner, tokens=[em_tok]), total_len
            elif n == 2:
                inner_tokens = self.tokenize(inner, in_link)
                return Strong(text=inner, tokens=inner_tokens), total_len
            else:
                inner_tokens = self.tokenize(inner, in_link)
                return Em(text=inner, tokens=inner_tokens), total_len
        return None


def normalize_label(label: str) -> str:
    return re.sub(r'\s+', ' ', label).strip().lower()
