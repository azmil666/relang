"""
lexer.py — C tokenizer for PicoC Python interpreter.

Converts a C source string into a flat list of Token objects.
Handles: keywords, identifiers, integer/float/char/string literals,
all operators, and preprocessor directives.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional
import re


class TT(Enum):
    """Token types."""
    # Literals
    INT_LIT    = auto()
    FLOAT_LIT  = auto()
    CHAR_LIT   = auto()
    STRING_LIT = auto()
    # Identifiers & keywords
    IDENT      = auto()
    # Keywords
    KW_INT = auto(); KW_CHAR = auto(); KW_SHORT = auto(); KW_LONG = auto()
    KW_FLOAT = auto(); KW_DOUBLE = auto(); KW_VOID = auto()
    KW_UNSIGNED = auto(); KW_SIGNED = auto()
    KW_STRUCT = auto(); KW_UNION = auto(); KW_ENUM = auto()
    KW_TYPEDEF = auto(); KW_EXTERN = auto(); KW_STATIC = auto()
    KW_CONST = auto(); KW_VOLATILE = auto(); KW_REGISTER = auto(); KW_AUTO = auto()
    KW_IF = auto(); KW_ELSE = auto()
    KW_WHILE = auto(); KW_DO = auto(); KW_FOR = auto()
    KW_BREAK = auto(); KW_CONTINUE = auto(); KW_RETURN = auto()
    KW_SWITCH = auto(); KW_CASE = auto(); KW_DEFAULT = auto()
    KW_GOTO = auto(); KW_SIZEOF = auto()
    KW_NULL = auto()
    KW_BOOL = auto(); KW_TRUE = auto(); KW_FALSE = auto()
    # Preprocessor
    PP_DEFINE  = auto(); PP_INCLUDE  = auto()
    PP_IF      = auto(); PP_IFDEF    = auto(); PP_IFNDEF   = auto()
    PP_ELSE    = auto(); PP_ELIF     = auto(); PP_ENDIF    = auto()
    PP_UNDEF   = auto(); PP_PRAGMA   = auto(); PP_LINE     = auto()
    PP_ERROR   = auto()
    # Punctuation / operators
    LPAREN = auto(); RPAREN = auto()
    LBRACE = auto(); RBRACE = auto()
    LBRACKET = auto(); RBRACKET = auto()
    SEMICOLON = auto(); COLON = auto(); COMMA = auto()
    DOT = auto(); ARROW = auto(); ELLIPSIS = auto()
    PLUS = auto(); MINUS = auto(); STAR = auto(); SLASH = auto(); PERCENT = auto()
    AMP = auto(); PIPE = auto(); CARET = auto(); TILDE = auto()
    BANG = auto(); QUESTION = auto()
    LT = auto(); GT = auto(); LE = auto(); GE = auto(); EQ = auto(); NEQ = auto()
    AND = auto(); OR = auto()  # && ||
    SHL = auto(); SHR = auto()  # << >>
    ASSIGN = auto()
    PLUS_ASSIGN = auto(); MINUS_ASSIGN = auto(); STAR_ASSIGN = auto()
    SLASH_ASSIGN = auto(); PERCENT_ASSIGN = auto()
    AMP_ASSIGN = auto(); PIPE_ASSIGN = auto(); CARET_ASSIGN = auto()
    SHL_ASSIGN = auto(); SHR_ASSIGN = auto()
    INC = auto(); DEC = auto()  # ++ --
    HASH = auto()   # standalone # in macro
    # Special
    EOF = auto()
    NEWLINE = auto()  # significant inside preprocessor


KEYWORDS = {
    'int': TT.KW_INT, 'char': TT.KW_CHAR, 'short': TT.KW_SHORT,
    'long': TT.KW_LONG, 'float': TT.KW_FLOAT, 'double': TT.KW_DOUBLE,
    'void': TT.KW_VOID, 'unsigned': TT.KW_UNSIGNED, 'signed': TT.KW_SIGNED,
    'struct': TT.KW_STRUCT, 'union': TT.KW_UNION, 'enum': TT.KW_ENUM,
    'typedef': TT.KW_TYPEDEF, 'extern': TT.KW_EXTERN, 'static': TT.KW_STATIC,
    'const': TT.KW_CONST, 'volatile': TT.KW_VOLATILE,
    'register': TT.KW_REGISTER, 'auto': TT.KW_AUTO,
    'if': TT.KW_IF, 'else': TT.KW_ELSE, 'while': TT.KW_WHILE,
    'do': TT.KW_DO, 'for': TT.KW_FOR,
    'break': TT.KW_BREAK, 'continue': TT.KW_CONTINUE, 'return': TT.KW_RETURN,
    'switch': TT.KW_SWITCH, 'case': TT.KW_CASE, 'default': TT.KW_DEFAULT,
    'goto': TT.KW_GOTO, 'sizeof': TT.KW_SIZEOF,
    'NULL': TT.KW_NULL,
    '_Bool': TT.KW_BOOL, 'bool': TT.KW_BOOL,
    'true': TT.KW_TRUE, 'false': TT.KW_FALSE,
}


@dataclass
class Token:
    type: TT
    value: object    # str/int/float/None
    line: int = 0
    col: int = 0

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, L{self.line})"


class LexError(Exception):
    def __init__(self, msg, line=0):
        super().__init__(f"Lex error line {line}: {msg}")
        self.line = line


def _unescape(s: str) -> str:
    """Process C escape sequences in a string."""
    result = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s):
            n = s[i+1]
            i += 2
            if n == 'n':   result.append('\n')
            elif n == 't': result.append('\t')
            elif n == 'r': result.append('\r')
            elif n == '\\': result.append('\\')
            elif n == '\'': result.append('\'')
            elif n == '"':  result.append('"')
            elif n == '0':  result.append('\0')
            elif n == 'a':  result.append('\a')
            elif n == 'b':  result.append('\b')
            elif n == 'f':  result.append('\f')
            elif n == 'v':  result.append('\v')
            elif n == 'x':
                # hex escape
                hex_str = ''
                while i < len(s) and s[i] in '0123456789abcdefABCDEF':
                    hex_str += s[i]; i += 1
                result.append(chr(int(hex_str, 16)) if hex_str else '\x00')
            elif n.isdigit():
                # octal escape
                oct_str = n
                for _ in range(2):
                    if i < len(s) and s[i] in '01234567':
                        oct_str += s[i]; i += 1
                result.append(chr(int(oct_str, 8)))
            else:
                result.append(n)
        else:
            result.append(c); i += 1
    return ''.join(result)


def tokenize(source: str, filename: str = '<input>') -> List[Token]:
    """Main tokenizer. Returns a list of Token objects."""
    tokens: List[Token] = []
    i = 0
    n = len(source)
    line = 1
    col = 1

    def cur():
        return source[i] if i < n else ''

    def peek(offset=1):
        j = i + offset
        return source[j] if j < n else ''

    def advance():
        nonlocal i, col
        c = source[i]
        i += 1
        col += 1
        return c

    def add(tt, val=None):
        tokens.append(Token(tt, val, line, col))

    while i < n:
        start_col = col
        c = cur()

        # ── Whitespace (except newline) ──
        if c in ' \t\r\f\v':
            advance(); continue

        # ── Newline ──
        if c == '\n':
            advance()
            line += 1; col = 1
            continue

        # ── Line comments ──
        if c == '/' and peek() == '/':
            while i < n and cur() != '\n':
                advance()
            continue

        # ── Block comments ──
        if c == '/' and peek() == '*':
            advance(); advance()  # consume /*
            while i < n:
                if cur() == '*' and peek() == '/':
                    advance(); advance(); break
                if cur() == '\n':
                    line += 1; col = 1
                advance()
            continue

        # ── Preprocessor directives ──
        if c == '#':
            advance()  # consume #
            # skip whitespace between # and directive name
            while i < n and cur() in ' \t':
                advance()
            if i < n and (cur().isalpha() or cur() == '_'):
                name = ''
                while i < n and (cur().isalnum() or cur() == '_'):
                    name += advance()
                pp_map = {
                    'define':  TT.PP_DEFINE,  'include': TT.PP_INCLUDE,
                    'if':      TT.PP_IF,      'ifdef':   TT.PP_IFDEF,
                    'ifndef':  TT.PP_IFNDEF,  'else':    TT.PP_ELSE,
                    'elif':    TT.PP_ELIF,    'endif':   TT.PP_ENDIF,
                    'undef':   TT.PP_UNDEF,   'pragma':  TT.PP_PRAGMA,
                    'line':    TT.PP_LINE,    'error':   TT.PP_ERROR,
                }
                tt = pp_map.get(name, TT.HASH)
                # Capture rest of line as the directive body
                rest = ''
                while i < n and cur() != '\n':
                    if cur() == '\\' and peek() == '\n':
                        advance(); advance()
                        line += 1; col = 1
                        rest += ' '
                    else:
                        rest += advance()
                add(tt, (name, rest.strip()))
            else:
                add(TT.HASH, None)
            continue

        # ── String literals ──
        if c == '"':
            advance()
            s = ''
            while i < n and cur() != '"':
                if cur() == '\\':
                    s += advance()
                    if i < n: s += advance()
                elif cur() == '\n':
                    line += 1; col = 1
                    s += advance()
                else:
                    s += advance()
            if i < n: advance()  # closing "
            add(TT.STRING_LIT, _unescape(s))
            continue

        # ── Char literals ──
        if c == "'":
            advance()
            s = ''
            while i < n and cur() != "'":
                if cur() == '\\':
                    s += advance()
                    if i < n: s += advance()
                else:
                    s += advance()
            if i < n: advance()  # closing '
            unescaped = _unescape(s)
            val = ord(unescaped[0]) if unescaped else 0
            add(TT.CHAR_LIT, val)
            continue

        # ── Numeric literals ──
        if c.isdigit() or (c == '.' and peek().isdigit()):
            num_str = ''
            is_float = False
            if c == '0' and peek() in 'xX':
                # Hex
                num_str += advance() + advance()
                while i < n and (cur() in '0123456789abcdefABCDEF'):
                    num_str += advance()
            elif c == '0' and peek() in '01234567' and peek() != '8' and peek() != '9':
                # Octal
                num_str += advance()
                while i < n and cur() in '01234567':
                    num_str += advance()
            else:
                while i < n and cur().isdigit():
                    num_str += advance()
                if i < n and cur() == '.' and peek() != '.':
                    is_float = True
                    num_str += advance()
                    while i < n and cur().isdigit():
                        num_str += advance()
                if i < n and cur() in 'eE':
                    is_float = True
                    num_str += advance()
                    if i < n and cur() in '+-':
                        num_str += advance()
                    while i < n and cur().isdigit():
                        num_str += advance()
            # Suffixes: u, l, ul, f
            suffix = ''
            while i < n and cur().lower() in 'ulfh':
                suffix += advance().lower()
            if 'f' in suffix or is_float and 'f' in suffix:
                is_float = True
            if is_float:
                try:
                    add(TT.FLOAT_LIT, (float(num_str), suffix))
                except ValueError:
                    add(TT.FLOAT_LIT, (0.0, suffix))
            else:
                try:
                    if num_str.startswith('0x') or num_str.startswith('0X'):
                        add(TT.INT_LIT, (int(num_str, 16), suffix))
                    elif num_str.startswith('0') and len(num_str) > 1:
                        add(TT.INT_LIT, (int(num_str, 8), suffix))
                    else:
                        add(TT.INT_LIT, (int(num_str or '0'), suffix))
                except ValueError:
                    add(TT.INT_LIT, (0, suffix))
            continue

        # ── Identifiers & keywords ──
        if c.isalpha() or c == '_':
            word = ''
            while i < n and (cur().isalnum() or cur() == '_'):
                word += advance()
            tt = KEYWORDS.get(word, TT.IDENT)
            add(tt, word)
            continue

        # ── Operators & punctuation ──
        advance()  # consume current char

        if c == '(':  add(TT.LPAREN); continue
        if c == ')':  add(TT.RPAREN); continue
        if c == '{':  add(TT.LBRACE); continue
        if c == '}':  add(TT.RBRACE); continue
        if c == '[':  add(TT.LBRACKET); continue
        if c == ']':  add(TT.RBRACKET); continue
        if c == ';':  add(TT.SEMICOLON); continue
        if c == ',':  add(TT.COMMA); continue
        if c == '~':  add(TT.TILDE); continue
        if c == '?':  add(TT.QUESTION); continue

        if c == ':':
            add(TT.COLON); continue

        if c == '.':
            if cur() == '.' and peek() == '.':
                advance(); advance()
                add(TT.ELLIPSIS); continue
            add(TT.DOT); continue

        if c == '-':
            if cur() == '>':  advance(); add(TT.ARROW); continue
            if cur() == '-':  advance(); add(TT.DEC); continue
            if cur() == '=':  advance(); add(TT.MINUS_ASSIGN); continue
            add(TT.MINUS); continue

        if c == '+':
            if cur() == '+':  advance(); add(TT.INC); continue
            if cur() == '=':  advance(); add(TT.PLUS_ASSIGN); continue
            add(TT.PLUS); continue

        if c == '*':
            if cur() == '=':  advance(); add(TT.STAR_ASSIGN); continue
            add(TT.STAR); continue

        if c == '/':
            if cur() == '=':  advance(); add(TT.SLASH_ASSIGN); continue
            add(TT.SLASH); continue

        if c == '%':
            if cur() == '=':  advance(); add(TT.PERCENT_ASSIGN); continue
            add(TT.PERCENT); continue

        if c == '&':
            if cur() == '&':  advance(); add(TT.AND); continue
            if cur() == '=':  advance(); add(TT.AMP_ASSIGN); continue
            add(TT.AMP); continue

        if c == '|':
            if cur() == '|':  advance(); add(TT.OR); continue
            if cur() == '=':  advance(); add(TT.PIPE_ASSIGN); continue
            add(TT.PIPE); continue

        if c == '^':
            if cur() == '=':  advance(); add(TT.CARET_ASSIGN); continue
            add(TT.CARET); continue

        if c == '!':
            if cur() == '=':  advance(); add(TT.NEQ); continue
            add(TT.BANG); continue

        if c == '=':
            if cur() == '=':  advance(); add(TT.EQ); continue
            add(TT.ASSIGN); continue

        if c == '<':
            if cur() == '<':
                advance()
                if cur() == '=': advance(); add(TT.SHL_ASSIGN); continue
                add(TT.SHL); continue
            if cur() == '=':  advance(); add(TT.LE); continue
            add(TT.LT); continue

        if c == '>':
            if cur() == '>':
                advance()
                if cur() == '=': advance(); add(TT.SHR_ASSIGN); continue
                add(TT.SHR); continue
            if cur() == '=':  advance(); add(TT.GE); continue
            add(TT.GT); continue

        # Unknown char — skip silently
        # (handles things like '\' at end of line)

    add(TT.EOF)
    return tokens
