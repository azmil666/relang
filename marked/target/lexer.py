"""
lexer.py
========
Block-level tokenizer. Walks the raw markdown source top to bottom,
peeling off one block at a time (heading, paragraph, list, blockquote,
code block, table, hr, html block, link reference definition) and
producing a flat list of block Tokens (some of which, like List and
Blockquote, recursively contain further block tokens).
"""
from __future__ import annotations

import re
from typing import Optional

from tokens import (
    Space, Hr, Heading, Code, Paragraph, Text, Blockquote, ListItem,
    ListToken, HTMLBlock, Def, TableToken,
)
from inline import normalize_label
from utils import rtrim

# --------------------------------------------------------------------------
# Block regexes
# --------------------------------------------------------------------------
NEWLINE_RE = re.compile(r'^(?: *(?:\n|$))+')
HR_RE = re.compile(r'^ {0,3}((?:-[ \t]*){3,}|(?:_[ \t]*){3,}|(?:\*[ \t]*){3,})(?:\n+|$)')
HEADING_RE = re.compile(r'^ {0,3}(#{1,6})(?=\s|$)(.*)(?:\n+|$)')
FENCE_RE = re.compile(
    r'^( {0,3})(`{3,}|~{3,})([^`\n]*)\n(?:([\s\S]*?)\n)?( {0,3})\2[~`]* *(?=\n|$)(?:\n+|$)'
)
FENCE_UNCLOSED_RE = re.compile(r'^( {0,3})(`{3,}|~{3,})([^`\n]*)\n([\s\S]*)$')
INDENTED_CODE_LINE_RE = re.compile(r'^( {4}|\t)')
BLOCKQUOTE_LINE_RE = re.compile(r'^ {0,3}>')
DEF_RE = re.compile(
    r'''^ {0,3}\[((?:\[(?:\\.|[^\[\]\\])*\]|\\.|[^\[\]\\])+)\]: *\n? *'''
    r'''<?([^\s>]+)>?(?:(?:[ \t]+\n?[ \t]*|\n[ \t]*)('''
    r'''"(?:\\"?|[^"\\])*"|'(?:\\'?|[^'\\])*'|\((?:\\\)?|[^)\\])*\)))? *(?:\n+|$)'''
)

HTML_BLOCK_TAGS = (
    r'address|article|aside|base|basefont|blockquote|body|caption|center|col|'
    r'colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|'
    r'footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|'
    r'li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|'
    r'search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul'
)
HTML_BLOCK_START_RE = re.compile(
    r'^ {0,3}(?:'
    r'<(script|pre|textarea|style)(?:\s|>|$)'                     # type 1
    r'|<!--'                                                        # type 2
    r'|<\?'                                                         # type 3
    r'|<![A-Za-z]'                                                  # type 4
    r'|<!\[CDATA\['                                                 # type 5
    r'|</?(' + HTML_BLOCK_TAGS + r')(?:\s|/?>|$)'                    # type 6
    r'|</?[a-zA-Z][\w\-]*(?:\s[^>]*)?/?>\s*$'                        # type 7 (approx)
    r')', re.IGNORECASE
)

LHEADING_RE = re.compile(r'^([^\n]+)\n {0,3}(=+|-+) *(?:\n+|$)')

BULLET_RE = re.compile(r'^ {0,3}([*+-]|\d{1,9}[.)])')

TABLE_DELIM_CELL_RE = re.compile(r'^ *:?-+:? *$')


def _is_table_delim_row(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|') and not line.endswith('\\|'):
        line = line[:-1]
    cells = _split_table_row(line)
    if not cells:
        return False
    for cell in cells:
        if not TABLE_DELIM_CELL_RE.match(cell):
            return False
    return True


def _split_table_row(row: str) -> list:
    """Split a table row on unescaped pipes."""
    cells = []
    cur = []
    i = 0
    n = len(row)
    while i < n:
        ch = row[i]
        if ch == '\\' and i + 1 < n:
            cur.append(ch)
            cur.append(row[i + 1])
            i += 2
            continue
        if ch == '|':
            cells.append(''.join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    cells.append(''.join(cur))
    return cells


class Lexer:
    """Produces a flat list of block-level tokens from raw markdown."""

    def __init__(self):
        self.links: dict = {}

    # ------------------------------------------------------------------
    def lex(self, src: str) -> list:
        src = src.replace('\r\n', '\n').replace('\r', '\n')
        src = src.replace('\t', '    ')
        tokens = self._block_tokens(src, top=True)
        return tokens

    # ------------------------------------------------------------------
    def _block_tokens(self, src: str, top: bool = False) -> list:
        tokens: list = []
        src = self._collect_defs(src, tokens)

        while src:
            # blank lines
            m = NEWLINE_RE.match(src)
            if m and m.end() > 0:
                consumed = m.group(0)
                if len(consumed) > 1:
                    tokens.append(Space())
                src = src[m.end():]
                if not src:
                    break

            # fenced code
            m = FENCE_RE.match(src)
            if m:
                raw = m.group(0)
                lang = m.group(3).strip().split(' ')[0] if m.group(3) else ''
                body = m.group(4) or ''
                tokens.append(Code(raw=raw, text=body, lang=lang or None))
                src = src[m.end():]
                continue

            # unclosed fence -> rest of document is code
            m = FENCE_UNCLOSED_RE.match(src)
            if m and top:
                lang = m.group(3).strip().split(' ')[0] if m.group(3) else ''
                body = m.group(4)
                body = re.sub(r'\n$', '', body)
                tokens.append(Code(raw=src, text=body, lang=lang or None))
                src = ''
                continue

            # indented code
            if INDENTED_CODE_LINE_RE.match(src):
                lines = src.split('\n')
                code_lines = []
                consumed_lines = 0
                for line in lines:
                    if INDENTED_CODE_LINE_RE.match(line) or line.strip() == '':
                        code_lines.append(line)
                        consumed_lines += 1
                    else:
                        break
                # strip trailing blank lines from the code block (kept as Space token)
                while code_lines and code_lines[-1].strip() == '':
                    code_lines.pop()
                raw_lines = lines[:consumed_lines]
                text = '\n'.join(
                    re.sub(r'^( {4}|\t)', '', l) if l.strip() else ''
                    for l in code_lines
                )
                raw = '\n'.join(raw_lines)
                remainder_start = len(raw)
                # account for following newline(s)
                rest = src[len(raw):]
                nl = re.match(r'^\n+', rest)
                if nl:
                    raw += nl.group(0)
                tokens.append(Code(raw=raw, text=text))
                src = src[len(raw):]
                continue

            # horizontal rule
            m = HR_RE.match(src)
            if m:
                tokens.append(Hr(raw=m.group(0)))
                src = src[m.end():]
                continue

            # ATX heading
            m = HEADING_RE.match(src)
            if m:
                depth = len(m.group(1))
                text = m.group(2).strip()
                text = re.sub(r'^#+\s*$', '', text)
                text = re.sub(r' +#+$', '', text)
                tokens.append(Heading(raw=m.group(0), depth=depth, text=text))
                src = src[m.end():]
                continue

            # blockquote
            if BLOCKQUOTE_LINE_RE.match(src):
                raw, inner = self._extract_blockquote(src)
                bq_tokens = self._block_tokens(inner)
                tokens.append(Blockquote(raw=raw, text=inner, tokens=bq_tokens))
                src = src[len(raw):]
                continue

            # lists
            m = BULLET_RE.match(src)
            if m:
                consumed_len, list_tok = self._extract_list(src)
                if list_tok is not None:
                    tokens.append(list_tok)
                    src = src[consumed_len:]
                    continue

            # html block
            m = HTML_BLOCK_START_RE.match(src)
            if m:
                raw = self._extract_html_block(src)
                if raw:
                    tokens.append(HTMLBlock(raw=raw, text=raw.rstrip('\n')))
                    src = src[len(raw):]
                    continue

            # GFM table
            table_tok, table_len = self._try_table(src)
            if table_tok is not None:
                tokens.append(table_tok)
                src = src[table_len:]
                continue

            # setext heading
            m = LHEADING_RE.match(src)
            if m and not re.match(r'^ {0,3}>', m.group(1)) and not BULLET_RE.match(m.group(1)):
                depth = 1 if m.group(2)[0] == '=' else 2
                text = m.group(1).strip()
                tokens.append(Heading(raw=m.group(0), depth=depth, text=text))
                src = src[m.end():]
                continue

            # paragraph (catch-all)
            raw, text, consumed = self._extract_paragraph(src)
            tokens.append(Paragraph(raw=raw, text=text))
            src = src[consumed:]

        return tokens

    # ------------------------------------------------------------------
    def _collect_defs(self, src: str, tokens: list) -> str:
        """Scan leading link reference definitions (marked scans for defs
        interleaved with blocks; for simplicity + practical correctness we
        pull ALL top-level defs out greedily as they're encountered during
        normal block scanning, so this is actually a no-op pre-pass and
        real def extraction happens in _block_tokens via _try_def)."""
        return src

    # ------------------------------------------------------------------
    def _extract_paragraph(self, src: str):
        lines = src.split('\n')
        para_lines = [lines[0]]
        i = 1
        while i < len(lines):
            line = lines[i]
            if line.strip() == '':
                break
            if (HEADING_RE.match(line) or HR_RE.match(line) or
                    BLOCKQUOTE_LINE_RE.match(line) or
                    HTML_BLOCK_START_RE.match(line) or
                    (BULLET_RE.match(line) and not re.match(r'^\d', line.strip()[:1] or '')) or
                    re.match(r'^ {0,3}(`{3,}|~{3,})', line)):
                break
            if i == 1 and re.match(r'^ {0,3}(=+|-+) *$', line):
                # this would've been caught by LHEADING_RE already; skip
                pass
            para_lines.append(line)
            i += 1
        raw_lines = lines[:i]
        raw = '\n'.join(raw_lines)
        rest = src[len(raw):]
        nl = re.match(r'^\n+', rest)
        if nl:
            raw += nl.group(0)
        text = '\n'.join(raw_lines).strip()
        text = rtrim(text, '\n')
        return raw, text, len(raw)

    # ------------------------------------------------------------------
    def _extract_blockquote(self, src: str):
        lines = src.split('\n')
        bq_lines = []
        i = 0
        blank_run = 0
        while i < len(lines):
            line = lines[i]
            if BLOCKQUOTE_LINE_RE.match(line):
                stripped = re.sub(r'^ {0,3}> ?', '', line)
                bq_lines.append(stripped)
                blank_run = 0
                i += 1
            elif line.strip() == '':
                # lazy continuation ends on blank line unless next is also '>'
                if i + 1 < len(lines) and BLOCKQUOTE_LINE_RE.match(lines[i + 1]):
                    bq_lines.append('')
                    i += 1
                else:
                    break
            elif (HEADING_RE.match(line) or HR_RE.match(line) or
                    BULLET_RE.match(line) or HTML_BLOCK_START_RE.match(line)):
                break
            else:
                # lazy continuation line (paragraph continuation)
                bq_lines.append(line)
                i += 1
        raw_lines = lines[:i]
        raw = '\n'.join(raw_lines)
        rest = src[len(raw):]
        nl = re.match(r'^\n+', rest)
        if nl:
            raw += nl.group(0)
        inner = '\n'.join(bq_lines)
        return raw, inner

    # ------------------------------------------------------------------
    def _extract_html_block(self, src: str) -> str:
        lines = src.split('\n')
        first = lines[0]
        m = re.match(r'^ {0,3}<(script|pre|textarea|style)(?:\s|>|$)', first, re.IGNORECASE)
        if m:
            tag = m.group(1).lower()
            end_re = re.compile(r'</' + tag + r'\s*>', re.IGNORECASE)
            collected = []
            for idx, line in enumerate(lines):
                collected.append(line)
                if end_re.search(line):
                    raw_lines = lines[:idx + 1]
                    raw = '\n'.join(raw_lines)
                    rest = src[len(raw):]
                    nl = re.match(r'^\n+', rest)
                    if nl:
                        raw += nl.group(0)
                    return raw
            raw = '\n'.join(lines)
            return raw

        if re.match(r'^ {0,3}<!--', first):
            collected = []
            for idx, line in enumerate(lines):
                collected.append(line)
                if '-->' in line:
                    raw_lines = lines[:idx + 1]
                    raw = '\n'.join(raw_lines)
                    rest = src[len(raw):]
                    nl = re.match(r'^\n+', rest)
                    if nl:
                        raw += nl.group(0)
                    return raw
            return '\n'.join(lines)

        # generic block: consume until blank line
        collected = []
        for idx, line in enumerate(lines):
            if idx > 0 and line.strip() == '':
                raw_lines = lines[:idx]
                raw = '\n'.join(raw_lines) + '\n'
                rest = src[len(raw):]
                nl = re.match(r'^\n*', rest)
                return raw
            collected.append(line)
        return '\n'.join(collected) + ('\n' if src.endswith('\n') else '')

    # ------------------------------------------------------------------
    def _try_table(self, src: str):
        lines = src.split('\n')
        if len(lines) < 2:
            return None, 0
        header_line = lines[0]
        delim_line = lines[1]
        if '|' not in header_line and '|' not in delim_line:
            return None, 0
        if not _is_table_delim_row(delim_line):
            return None, 0

        def parse_row(line):
            line = line.strip()
            if line.startswith('|'):
                line = line[1:]
            if line.endswith('|') and not line.endswith('\\|'):
                line = line[:-1]
            return [c.strip() for c in _split_table_row(line)]

        header_cells = parse_row(header_line)
        delim_cells = parse_row(delim_line)
        align = []
        for d in delim_cells:
            d = d.strip()
            left = d.startswith(':')
            right = d.endswith(':')
            if left and right:
                align.append('center')
            elif left:
                align.append('left')
            elif right:
                align.append('right')
            else:
                align.append(None)

        row_lines = []
        i = 2
        while i < len(lines):
            line = lines[i]
            if line.strip() == '':
                break
            if (HEADING_RE.match(line) or HR_RE.match(line) or
                    BLOCKQUOTE_LINE_RE.match(line)):
                break
            row_lines.append(line)
            i += 1

        raw_lines = lines[:i]
        raw = '\n'.join(raw_lines)
        rest = src[len(raw):]
        nl = re.match(r'^\n+', rest)
        if nl:
            raw += nl.group(0)

        rows = [parse_row(rl) for rl in row_lines]
        ncols = len(header_cells)
        norm_rows = []
        for r in rows:
            r = r[:ncols] + [''] * (ncols - len(r)) if len(r) < ncols else r[:ncols]
            norm_rows.append(r)

        tok = TableToken(
            raw=raw,
            raw_header=header_cells,
            align=align,
            raw_rows=norm_rows,
        )
        return tok, len(raw)

    # ------------------------------------------------------------------
    def _extract_list(self, src: str):
        first_match = BULLET_RE.match(src)
        marker_text = first_match.group(1)
        ordered = marker_text[0].isdigit()
        if ordered:
            bullet_re = re.compile(r'^ {0,3}(\d{1,9})([.)])(?: |$|\n)')
            start_m = re.match(r'^ {0,3}(\d{1,9})[.)]', src)
            start_val = int(start_m.group(1)) if start_m else 1
        else:
            bullet_re = re.compile(r'^ {0,3}([*+-])(?: |$|\n)')
            start_val = ''

        items_raw = []
        pos = 0
        remaining = src
        while True:
            m = bullet_re.match(remaining)
            if not m:
                break
            marker_len = m.end()
            # `bullet_re` already consumes exactly one space (or eol) after
            # the marker itself, so `marker_len` is the indent for the
            # common case "- text". If there are *additional* spaces before
            # the content starts, fold those in too (up to 3 more; 4+ means
            # the extra spaces are themselves indented-code content).
            after_marker = remaining[marker_len:]
            if after_marker == '' or after_marker.startswith('\n'):
                indent = marker_len
            else:
                sp_m2 = re.match(r'^ +', after_marker)
                extra = len(sp_m2.group(0)) if sp_m2 else 0
                indent = marker_len + (extra if extra <= 3 else 0)

            item_raw, item_len = self._extract_list_item_raw(remaining, indent)
            if item_len == 0:
                break
            items_raw.append(item_raw)
            remaining = remaining[item_len:]
            pos += item_len
            # peek: does next chunk continue the list (same bullet pattern)?
            if not bullet_re.match(remaining):
                break

        if not items_raw:
            return 0, None

        raw = src[:pos]
        loose = False
        item_tokens = []
        for idx, raw_item in enumerate(items_raw):
            content, checked_state = self._strip_item_marker_and_task(raw_item, ordered)
            item_is_loose = (
                '\n\n' in content.strip('\n')
                or (idx < len(items_raw) - 1 and raw_item.endswith('\n\n'))
            )
            inner_tokens = self._block_tokens(content)
            if any(isinstance(t, Space) for t in inner_tokens) or item_is_loose:
                loose = True
            task = checked_state is not None
            checked = bool(checked_state)
            item_tokens.append(ListItem(
                raw=raw_item, text=content.strip('\n'),
                task=task, checked=checked, tokens=inner_tokens,
            ))

        for it in item_tokens:
            it.loose = loose

        list_tok = ListToken(
            raw=raw, ordered=ordered, start=start_val, loose=loose, items=item_tokens,
        )
        return pos, list_tok

    def _strip_item_marker_and_task(self, raw_item: str, ordered: bool):
        lines = raw_item.split('\n')
        first = lines[0]
        if ordered:
            m = re.match(r'^ {0,3}\d{1,9}[.)] ?', first)
        else:
            m = re.match(r'^ {0,3}[*+-] ?', first)
        marker_len = m.end() if m else 0
        rest_first = first[marker_len:]
        task_m = re.match(r'^\[( |x|X)\] ', rest_first)
        checked_state = None
        if task_m:
            checked_state = task_m.group(1).lower() == 'x'
            rest_first = rest_first[task_m.end():]

        dedent = marker_len
        out_lines = [rest_first]
        for line in lines[1:]:
            if line.startswith(' ' * dedent):
                out_lines.append(line[dedent:])
            elif line.strip() == '':
                out_lines.append('')
            else:
                out_lines.append(line.lstrip())
        return '\n'.join(out_lines), checked_state

    def _extract_list_item_raw(self, src: str, indent: int):
        lines = src.split('\n')
        item_lines = [lines[0]]
        i = 1
        blank_streak = 0
        while i < len(lines):
            line = lines[i]
            if line.strip() == '':
                # a blank line: item continues if the following non-blank
                # line is indented enough, otherwise item ends here
                j = i + 1
                while j < len(lines) and lines[j].strip() == '':
                    j += 1
                if j < len(lines) and (lines[j].startswith(' ' * indent) or lines[j].strip() == ''):
                    item_lines.append('')
                    i += 1
                    continue
                else:
                    item_lines.append('')
                    i += 1
                    break
            elif line.startswith(' ' * indent):
                item_lines.append(line)
                i += 1
            elif re.match(r'^ {0,3}([*+-]|\d{1,9}[.)])(?: |$)', line):
                break
            else:
                break
        while item_lines and item_lines[-1] == '':
            item_lines.pop()
        raw = '\n'.join(item_lines)
        rest = src[len(raw):]
        nl = re.match(r'^\n+', rest)
        trailing = ''
        if nl:
            trailing = nl.group(0)
            raw_full = raw + trailing
        else:
            raw_full = raw
        return raw_full, len(raw_full)


def scan_link_defs(src: str) -> tuple:
    """Pre-pass: strip out all top-level link reference definitions from the
    source, returning (remaining_src_with_defs_blanked, defs_dict).
    marked resolves *all* defs before parsing paragraphs/etc, regardless of
    where in the document they occur, so we do the same as a first pass.
    """
    defs: dict = {}
    out_lines = []
    lines = src.split('\n')
    i = 0
    n = len(lines)
    while i < n:
        chunk = '\n'.join(lines[i:i + 4])
        m = DEF_RE.match(chunk)
        if m and re.match(r'^ {0,3}\[', lines[i]):
            tag = normalize_label(m.group(1))
            href = m.group(2)
            title = m.group(3)
            if title:
                title = title[1:-1]
            if tag not in defs:
                defs[tag] = {'href': href, 'title': title}
            consumed_text = m.group(0)
            consumed_lines = consumed_text.count('\n')
            if not consumed_text.endswith('\n'):
                consumed_lines += 1
            i += max(consumed_lines, 1)
            continue
        out_lines.append(lines[i])
        i += 1
    return '\n'.join(out_lines), defs
