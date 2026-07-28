"""
parser.py
=========
Consumes the block-token list produced by `lexer.Lexer`, resolves inline
markdown within each block via `inline.InlineLexer`, and calls the
`renderer.Renderer` to produce final HTML. This is the "middle" stage of
the pipeline -- it owns tree-walking, not tokenizing or presentation.
"""
from __future__ import annotations

from tokens import (
    Space, Hr, Heading, Code, Paragraph, Text, Blockquote, ListItem,
    ListToken, HTMLBlock, Def, TableToken,
    InlineText, Escape, HTMLInline, Link, Image, Strong, Em, Codespan, Br, Del,
)
from inline import InlineLexer
from renderer import Renderer


class Parser:
    def __init__(self, links: dict, renderer: Renderer | None = None):
        self.renderer = renderer or Renderer()
        self.inline_lexer = InlineLexer(links)

    # ------------------------------------------------------------------
    def parse(self, tokens: list) -> str:
        out = []
        for tok in tokens:
            out.append(self._render_block(tok))
        return ''.join(out)

    # ------------------------------------------------------------------
    def _render_block(self, tok) -> str:
        if isinstance(tok, Space):
            return ''
        if isinstance(tok, Hr):
            return self.renderer.hr()
        if isinstance(tok, Heading):
            inline_tokens = self.inline_lexer.tokenize(tok.text)
            html = self._render_inline_tokens(inline_tokens)
            return self.renderer.heading(html, tok.depth)
        if isinstance(tok, Code):
            return self.renderer.code(tok.text, tok.lang)
        if isinstance(tok, Paragraph):
            inline_tokens = self.inline_lexer.tokenize(tok.text)
            html = self._render_inline_tokens(inline_tokens)
            return self.renderer.paragraph(html)
        if isinstance(tok, Blockquote):
            inner = self.parse(tok.tokens)
            return self.renderer.blockquote(inner)
        if isinstance(tok, HTMLBlock):
            return self.renderer.html_block(tok.text)
        if isinstance(tok, ListToken):
            return self._render_list(tok)
        if isinstance(tok, TableToken):
            return self._render_table(tok)
        if isinstance(tok, Def):
            return ''
        # Fallback for stray inline-ish block wrappers
        return ''

    # ------------------------------------------------------------------
    def _render_list(self, tok: ListToken) -> str:
        body_parts = []
        for item in tok.items:
            body_parts.append(self._render_list_item(item, tok.loose))
        body = ''.join(body_parts)
        return self.renderer.list(body, tok.ordered, tok.start)

    def _render_list_item(self, item: ListItem, loose: bool) -> str:
        if item.task:
            prefix = self.renderer.checkbox(item.checked)
        else:
            prefix = ''

        block_tokens = item.tokens
        if not loose:
            # tight list item: if the single block is a Paragraph, render
            # just its inline content (no wrapping <p>)
            if len(block_tokens) == 1 and isinstance(block_tokens[0], Paragraph):
                inline_tokens = self.inline_lexer.tokenize(block_tokens[0].text)
                html = prefix + self._render_inline_tokens(inline_tokens)
                return self.renderer.list_item(html, item.task, item.checked, loose)
            elif block_tokens and isinstance(block_tokens[0], Paragraph):
                # first para inline, rest rendered as blocks
                first_inline = self.inline_lexer.tokenize(block_tokens[0].text)
                parts = [prefix + self._render_inline_tokens(first_inline)]
                rest_html = self.parse(block_tokens[1:])
                if rest_html:
                    parts.append('\n' + rest_html.rstrip('\n'))
                html = ''.join(parts)
                return self.renderer.list_item(html, item.task, item.checked, loose)
            else:
                html = prefix + self.parse(block_tokens).rstrip('\n')
                return self.renderer.list_item(html, item.task, item.checked, loose)
        else:
            html = prefix + self.parse(block_tokens)
            html = html.rstrip('\n')
            return self.renderer.list_item(html, item.task, item.checked, loose)

    # ------------------------------------------------------------------
    def _render_table(self, tok: TableToken) -> str:
        header_cells = []
        for i, cell_src in enumerate(tok.raw_header):
            align = tok.align[i] if i < len(tok.align) else None
            inline_tokens = self.inline_lexer.tokenize(cell_src)
            html = self._render_inline_tokens(inline_tokens)
            header_cells.append(self.renderer.table_cell(html, True, align))
        header_row = self.renderer.table_row(''.join(header_cells))

        body_rows = []
        for row in tok.raw_rows:
            row_cells = []
            for i, cell_src in enumerate(row):
                align = tok.align[i] if i < len(tok.align) else None
                inline_tokens = self.inline_lexer.tokenize(cell_src)
                html = self._render_inline_tokens(inline_tokens)
                row_cells.append(self.renderer.table_cell(html, False, align))
            body_rows.append(self.renderer.table_row(''.join(row_cells)))

        return self.renderer.table(header_row, ''.join(body_rows))

    # ------------------------------------------------------------------
    def _render_inline_tokens(self, tokens: list) -> str:
        out = []
        for tok in tokens:
            out.append(self._render_inline(tok))
        return ''.join(out)

    def _render_inline(self, tok) -> str:
        if isinstance(tok, InlineText):
            return self.renderer.text(tok.text)
        if isinstance(tok, Escape):
            return self.renderer.escape_(tok.text)
        if isinstance(tok, HTMLInline):
            return self.renderer.html_inline(tok.text)
        if isinstance(tok, Br):
            return self.renderer.br()
        if isinstance(tok, Codespan):
            return self.renderer.codespan(tok.text)
        if isinstance(tok, Strong):
            inner = self._render_inline_tokens(tok.tokens)
            return self.renderer.strong(inner)
        if isinstance(tok, Em):
            inner = self._render_inline_tokens(tok.tokens)
            return self.renderer.em(inner)
        if isinstance(tok, Del):
            inner = self._render_inline_tokens(tok.tokens)
            return self.renderer.del_(inner)
        if isinstance(tok, Link):
            inner = self._render_inline_tokens(tok.tokens) if tok.tokens else tok.text
            return self.renderer.link(tok.href, tok.title, inner)
        if isinstance(tok, Image):
            return self.renderer.image(tok.href, tok.title, tok.text)
        return ''
