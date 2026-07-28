"""
renderer.py
===========
Turns tokens into HTML. Every *block*-level render method returns HTML
ending with a single trailing '\n' (matching marked's convention); inline
render methods return HTML with no forced trailing newline.

No tokenizing/parsing logic lives here -- purely presentational.
"""
from __future__ import annotations

from utils import escape


class Renderer:
    # ------------------------------------------------------------------
    # Block renderers
    # ------------------------------------------------------------------
    def heading(self, text: str, depth: int) -> str:
        return f"<h{depth}>{text}</h{depth}>\n"

    def paragraph(self, text: str) -> str:
        return f"<p>{text}</p>\n"

    def code(self, code: str, lang: str | None) -> str:
        code_escaped = escape(code, encode=True)
        if not code.endswith('\n'):
            code_escaped_body = code_escaped
        else:
            code_escaped_body = code_escaped
        if lang:
            lang_class = escape(lang.split()[0], encode=True) if lang.split() else ''
            return f'<pre><code class="language-{lang_class}">{code_escaped_body}\n</code></pre>\n'
        return f'<pre><code>{code_escaped_body}\n</code></pre>\n'

    def blockquote(self, inner_html: str) -> str:
        return f"<blockquote>\n{inner_html}</blockquote>\n"

    def hr(self) -> str:
        return "<hr>\n"

    def html_block(self, html: str) -> str:
        text = html
        if not text.endswith('\n'):
            text += '\n'
        return text

    def list(self, body: str, ordered: bool, start) -> str:
        tag = 'ol' if ordered else 'ul'
        start_attr = ''
        if ordered and start and start != 1:
            start_attr = f' start="{start}"'
        return f"<{tag}{start_attr}>\n{body}</{tag}>\n"

    def list_item(self, text: str, task: bool, checked: bool, loose: bool) -> str:
        return f"<li>{text}</li>\n"

    def checkbox(self, checked: bool) -> str:
        checked_part = ' checked=""' if checked else ''
        return f'<input disabled=""{checked_part} type="checkbox"> '

    def table(self, header: str, body: str) -> str:
        body_html = f"<tbody>{body}</tbody>" if body else ""
        return f"<table>\n<thead>\n{header}</thead>\n{body_html}\n</table>\n"

    def table_row(self, content: str) -> str:
        return f"<tr>\n{content}</tr>\n"

    def table_cell(self, content: str, header: bool, align: str | None) -> str:
        tag = 'th' if header else 'td'
        align_attr = f' align="{align}"' if align else ''
        return f"<{tag}{align_attr}>{content}</{tag}>\n"

    # ------------------------------------------------------------------
    # Inline renderers
    # ------------------------------------------------------------------
    def strong(self, text: str) -> str:
        return f"<strong>{text}</strong>"

    def em(self, text: str) -> str:
        return f"<em>{text}</em>"

    def codespan(self, text: str) -> str:
        return f"<code>{text}</code>"

    def br(self) -> str:
        return "<br>"

    def del_(self, text: str) -> str:
        return f"<del>{text}</del>"

    def link(self, href: str, title: str | None, text: str) -> str:
        title_attr = f' title="{escape(title, encode=True)}"' if title else ''
        return f'<a href="{escape(href, encode=True)}"{title_attr}>{text}</a>'

    def image(self, href: str, title: str | None, text: str) -> str:
        title_attr = f' title="{escape(title, encode=True)}"' if title else ''
        return f'<img src="{escape(href, encode=True)}" alt="{text}"{title_attr}>'

    def text(self, text: str) -> str:
        return text

    def html_inline(self, text: str) -> str:
        return text

    def escape_(self, text: str) -> str:
        return text
