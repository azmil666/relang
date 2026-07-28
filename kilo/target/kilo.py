#!/usr/bin/env python3
"""
Kilo -- A very simple editor, ported line-for-line in spirit from the
original C implementation by Salvatore "antirez" Sanfilippo.

This is a behavior-preserving Python port of kilo.c. It does not depend on
curses; it emits VT100 escape sequences directly, exactly like the original.

Original copyright notice (C) 2016 Salvatore Sanfilippo <antirez at gmail dot com>
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the conditions of the original
BSD-style license are met (see the original kilo.c header).
"""

import atexit
import errno
import fcntl
import os
import re
import signal
import struct
import sys
import termios
import time
from dataclasses import dataclass, field
from typing import List, Optional

KILO_VERSION = "0.0.1"

# ============================= Syntax highlight types =======================

HL_NORMAL = 0
HL_NONPRINT = 1
HL_COMMENT = 2      # Single line comment.
HL_MLCOMMENT = 3    # Multi-line comment.
HL_KEYWORD1 = 4
HL_KEYWORD2 = 5
HL_STRING = 6
HL_NUMBER = 7
HL_MATCH = 8        # Search match.

HL_HIGHLIGHT_STRINGS = 1 << 0
HL_HIGHLIGHT_NUMBERS = 1 << 1

UINT32_MAX = 0xFFFFFFFF


@dataclass
class EditorSyntax:
    filematch: List[str]
    keywords: List[str]
    singleline_comment_start: bytes
    multiline_comment_start: bytes
    multiline_comment_end: bytes
    flags: int


# C / C++
C_HL_extensions = [".c", ".h", ".cpp", ".hpp", ".cc"]
C_HL_keywords = [
    # C Keywords
    "auto", "break", "case", "continue", "default", "do", "else", "enum",
    "extern", "for", "goto", "if", "register", "return", "sizeof", "static",
    "struct", "switch", "typedef", "union", "volatile", "while", "NULL",

    # C++ Keywords
    "alignas", "alignof", "and", "and_eq", "asm", "bitand", "bitor", "class",
    "compl", "constexpr", "const_cast", "deltype", "delete", "dynamic_cast",
    "explicit", "export", "false", "friend", "inline", "mutable", "namespace",
    "new", "noexcept", "not", "not_eq", "nullptr", "operator", "or", "or_eq",
    "private", "protected", "public", "reinterpret_cast", "static_assert",
    "static_cast", "template", "this", "thread_local", "throw", "true", "try",
    "typeid", "typename", "virtual", "xor", "xor_eq",

    # C types
    "int|", "long|", "double|", "float|", "char|", "unsigned|", "signed|",
    "void|", "short|", "auto|", "const|", "bool|",
]

HLDB = [
    EditorSyntax(
        C_HL_extensions,
        C_HL_keywords,
        b"//", b"/*", b"*/",
        HL_HIGHLIGHT_STRINGS | HL_HIGHLIGHT_NUMBERS,
    )
]

# =============================== KEY_ACTION =================================

KEY_NULL = 0
CTRL_C = 3
CTRL_D = 4
CTRL_F = 6
CTRL_H = 8
TAB = 9
CTRL_L = 12
ENTER = 13
CTRL_Q = 17
CTRL_S = 19
CTRL_U = 21
ESC = 27
BACKSPACE = 127
# Soft codes, not really reported by the terminal directly.
ARROW_LEFT = 1000
ARROW_RIGHT = 1001
ARROW_UP = 1002
ARROW_DOWN = 1003
DEL_KEY = 1004
HOME_KEY = 1005
END_KEY = 1006
PAGE_UP = 1007
PAGE_DOWN = 1008


# ================================ Row model ==================================

@dataclass
class Erow:
    idx: int = 0
    size: int = 0
    rsize: int = 0
    chars: bytearray = field(default_factory=bytearray)   # includes trailing NUL
    render: bytearray = field(default_factory=bytearray)  # includes trailing NUL
    hl: bytearray = field(default_factory=bytearray)
    hl_oc: int = 0


@dataclass
class EditorConfig:
    cx: int = 0
    cy: int = 0
    rowoff: int = 0
    coloff: int = 0
    screenrows: int = 0
    screencols: int = 0
    numrows: int = 0
    rawmode: int = 0
    row: List[Erow] = field(default_factory=list)
    dirty: int = 0
    filename: Optional[str] = None
    statusmsg: str = ""
    statusmsg_time: float = 0.0
    syntax: Optional[EditorSyntax] = None


E = EditorConfig()

orig_termios = None


# ======================= Low level terminal handling =========================

def disableRawMode(fd: int) -> None:
    global orig_termios
    if E.rawmode:
        try:
            termios.tcsetattr(fd, termios.TCSAFLUSH, orig_termios)
        except termios.error:
            pass
        E.rawmode = 0


def editorAtExit() -> None:
    disableRawMode(sys.stdin.fileno())


def enableRawMode(fd: int) -> int:
    global orig_termios
    if E.rawmode:
        return 0
    if not os.isatty(fd):
        return -1
    atexit.register(editorAtExit)
    try:
        orig_termios = termios.tcgetattr(fd)
    except termios.error:
        return -1

    raw = termios.tcgetattr(fd)
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = raw

    iflag &= ~(termios.BRKINT | termios.ICRNL | termios.INPCK |
               termios.ISTRIP | termios.IXON)
    oflag &= ~(termios.OPOST)
    cflag |= termios.CS8
    lflag &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
    cc[termios.VMIN] = 0
    cc[termios.VTIME] = 1  # 100 ms timeout (unit is tenths of a second)

    raw = [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
    try:
        termios.tcsetattr(fd, termios.TCSAFLUSH, raw)
    except termios.error:
        return -1
    E.rawmode = 1
    return 0


def editorReadKey(fd: int) -> int:
    """Read a key from the terminal (raw mode), handling escape sequences."""
    c = None
    while c is None:
        data = os.read(fd, 1)
        if len(data) == 1:
            c = data[0]
        # nread == 0 (timeout): keep looping, matching the original C busy-wait.

    while True:
        if c != ESC:
            return c

        d1 = os.read(fd, 1)
        if len(d1) == 0:
            return ESC
        d2 = os.read(fd, 1)
        if len(d2) == 0:
            return ESC
        b0, b1 = d1[0], d2[0]

        if b0 == ord('['):
            if ord('0') <= b1 <= ord('9'):
                d3 = os.read(fd, 1)
                if len(d3) == 0:
                    return ESC
                b2 = d3[0]
                if b2 == ord('~'):
                    if b1 == ord('3'):
                        return DEL_KEY
                    if b1 == ord('5'):
                        return PAGE_UP
                    if b1 == ord('6'):
                        return PAGE_DOWN
            else:
                if b1 == ord('A'):
                    return ARROW_UP
                if b1 == ord('B'):
                    return ARROW_DOWN
                if b1 == ord('C'):
                    return ARROW_RIGHT
                if b1 == ord('D'):
                    return ARROW_LEFT
                if b1 == ord('H'):
                    return HOME_KEY
                if b1 == ord('F'):
                    return END_KEY
        elif b0 == ord('O'):
            if b1 == ord('H'):
                return HOME_KEY
            if b1 == ord('F'):
                return END_KEY
        # No match: fall through and re-loop (c is still ESC), mirroring the
        # original switch-inside-while(1) fallthrough behavior.


def getCursorPosition(ifd: int, ofd: int):
    """Query the cursor position via ESC[6n. Returns (rows, cols) or None."""
    try:
        if os.write(ofd, b"\x1b[6n") != 4:
            return None
    except OSError:
        return None

    buf = bytearray()
    while len(buf) < 31:
        try:
            d = os.read(ifd, 1)
        except OSError:
            break
        if len(d) != 1:
            break
        buf += d
        if d == b"R":
            break

    if len(buf) < 2 or buf[0] != ESC or buf[1] != ord('['):
        return None
    m = re.match(rb"(\d+);(\d+)", bytes(buf[2:]))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def getWindowSize(ifd: int, ofd: int):
    """Return (rows, cols) of the terminal, or None on failure."""
    try:
        packed = fcntl.ioctl(ofd, termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0))
        rows, cols, _, _ = struct.unpack('HHHH', packed)
        if cols != 0:
            return rows, cols
    except OSError:
        pass

    # ioctl failed (or returned 0 cols): fall back to querying the terminal.
    pos = getCursorPosition(ifd, ofd)
    if pos is None:
        return None
    orig_row, orig_col = pos

    try:
        if os.write(ofd, b"\x1b[999C\x1b[999B") != 12:
            return None
    except OSError:
        return None

    pos2 = getCursorPosition(ifd, ofd)
    if pos2 is None:
        return None
    rows, cols = pos2

    seq = ("\x1b[%d;%dH" % (orig_row, orig_col)).encode()
    try:
        os.write(ofd, seq)
    except OSError:
        pass  # Can't recover...
    return rows, cols


# ===================== Syntax highlight color scheme =========================

def is_separator(c: int) -> bool:
    if c == 0:
        return True
    if chr(c).isspace():
        return True
    if chr(c) in ",.()+-/*=~%[];":
        return True
    return False


def editorRowHasOpenComment(row: Erow) -> int:
    if (row.hl and row.rsize and row.hl[row.rsize - 1] == HL_MLCOMMENT and
            (row.rsize < 2 or (row.render[row.rsize - 2] != ord('*') or
                                row.render[row.rsize - 1] != ord('/')))):
        return 1
    return 0


def editorUpdateSyntax(row: Erow) -> None:
    row.hl = bytearray(row.rsize)  # all HL_NORMAL (0) initially

    if E.syntax is None:
        return

    keywords = E.syntax.keywords
    scs = E.syntax.singleline_comment_start
    mcs = E.syntax.multiline_comment_start
    mce = E.syntax.multiline_comment_end
    render = row.render
    n = row.rsize

    def ch(k: int) -> int:
        return render[k] if 0 <= k < n else 0

    i = 0
    while i < n and chr(render[i]).isspace():
        i += 1

    prev_sep = 1
    in_string = 0
    in_comment = 0

    if row.idx > 0 and editorRowHasOpenComment(E.row[row.idx - 1]):
        in_comment = 1

    while i < n:
        c = render[i]
        c1 = ch(i + 1)

        # Handle // comments.
        if prev_sep and len(scs) >= 2 and c == scs[0] and c1 == scs[1]:
            for k in range(i, row.size):
                if k < len(row.hl):
                    row.hl[k] = HL_COMMENT
            return

        # Handle multi line comments.
        if in_comment:
            if i < len(row.hl):
                row.hl[i] = HL_MLCOMMENT
            if c == mce[0] and c1 == mce[1]:
                if i + 1 < len(row.hl):
                    row.hl[i + 1] = HL_MLCOMMENT
                i += 2
                in_comment = 0
                prev_sep = 1
                continue
            else:
                prev_sep = 0
                i += 1
                continue
        elif len(mcs) >= 2 and c == mcs[0] and c1 == mcs[1]:
            if i < len(row.hl):
                row.hl[i] = HL_MLCOMMENT
            if i + 1 < len(row.hl):
                row.hl[i + 1] = HL_MLCOMMENT
            i += 2
            in_comment = 1
            prev_sep = 0
            continue

        # Handle "" and ''
        if in_string:
            if i < len(row.hl):
                row.hl[i] = HL_STRING
            if c == ord('\\'):
                if i + 1 < len(row.hl):
                    row.hl[i + 1] = HL_STRING
                i += 2
                prev_sep = 0
                continue
            if c == in_string:
                in_string = 0
            i += 1
            continue
        else:
            if c == ord('"') or c == ord("'"):
                in_string = c
                if i < len(row.hl):
                    row.hl[i] = HL_STRING
                i += 1
                prev_sep = 0
                continue

        # Handle non-printable chars.
        if not (32 <= c < 127):
            if i < len(row.hl):
                row.hl[i] = HL_NONPRINT
            i += 1
            prev_sep = 0
            continue

        # Handle numbers.
        if ((chr(c).isdigit() and (prev_sep or (i > 0 and row.hl[i - 1] == HL_NUMBER))) or
                (c == ord('.') and i > 0 and row.hl[i - 1] == HL_NUMBER)):
            if i < len(row.hl):
                row.hl[i] = HL_NUMBER
            i += 1
            prev_sep = 0
            continue

        # Handle keywords and lib calls.
        if prev_sep:
            matched = False
            for kw in keywords:
                kw2 = kw.endswith('|')
                base = kw[:-1] if kw2 else kw
                klen = len(base)
                base_bytes = base.encode()
                if (bytes(render[i:i + klen]) == base_bytes and
                        is_separator(ch(i + klen))):
                    hltype = HL_KEYWORD2 if kw2 else HL_KEYWORD1
                    for k in range(i, i + klen):
                        if k < len(row.hl):
                            row.hl[k] = hltype
                    i += klen
                    matched = True
                    break
            if matched:
                prev_sep = 0
                continue

        # Not special chars.
        prev_sep = is_separator(c)
        i += 1

    # Propagate syntax change to the next row if the open comment state
    # changed. This may recursively affect all the following rows in the file.
    oc = editorRowHasOpenComment(row)
    if row.hl_oc != oc and row.idx + 1 < E.numrows:
        editorUpdateSyntax(E.row[row.idx + 1])
    row.hl_oc = oc


def editorSyntaxToColor(hl: int) -> int:
    if hl in (HL_COMMENT, HL_MLCOMMENT):
        return 36  # cyan
    if hl == HL_KEYWORD1:
        return 33  # yellow
    if hl == HL_KEYWORD2:
        return 32  # green
    if hl == HL_STRING:
        return 35  # magenta
    if hl == HL_NUMBER:
        return 31  # red
    if hl == HL_MATCH:
        return 34  # blue
    return 37  # white


def editorSelectSyntaxHighlight(filename: str) -> None:
    for s in HLDB:
        for pat in s.filematch:
            idx = filename.find(pat)
            if idx != -1:
                patlen = len(pat)
                if not pat.startswith('.') or (idx + patlen == len(filename)):
                    E.syntax = s
                    return


# ======================= Editor rows implementation ==========================

def _realloc(buf: bytearray, newsize: int) -> bytearray:
    if newsize <= len(buf):
        return bytearray(buf[:newsize])
    return bytearray(buf) + bytearray(newsize - len(buf))


def editorUpdateRow(row: Erow) -> None:
    tabs = 0
    for j in range(row.size):
        if row.chars[j] == TAB:
            tabs += 1

    allocsize = row.size + tabs * 8 + 1
    if allocsize > UINT32_MAX:
        print("Some line of the edited file is too long for kilo")
        sys.exit(1)

    render = bytearray(allocsize)
    idx = 0
    for j in range(row.size):
        if row.chars[j] == TAB:
            render[idx] = ord(' ')
            idx += 1
            while (idx + 1) % 8 != 0:
                render[idx] = ord(' ')
                idx += 1
        else:
            render[idx] = row.chars[j]
            idx += 1

    row.rsize = idx
    row.render = render[:idx] + bytearray(1)  # trailing NUL, like the C buffer

    editorUpdateSyntax(row)


def editorInsertRow(at: int, s: bytes, length: int) -> None:
    if at > E.numrows:
        return
    row = Erow()
    row.size = length
    row.chars = bytearray(s[:length]) + bytearray(1)  # NUL-terminated
    row.hl = bytearray()
    row.hl_oc = 0
    row.render = bytearray()
    row.rsize = 0
    row.idx = at
    E.row.insert(at, row)
    for j in range(at + 1, len(E.row)):
        E.row[j].idx = j
    editorUpdateRow(E.row[at])
    E.numrows += 1
    E.dirty += 1


def editorFreeRow(row: Erow) -> None:
    row.render = bytearray()
    row.chars = bytearray()
    row.hl = bytearray()


def editorDelRow(at: int) -> None:
    if at >= E.numrows:
        return
    editorFreeRow(E.row[at])
    del E.row[at]
    for j in range(at, len(E.row)):
        E.row[j].idx = j
    E.numrows -= 1
    E.dirty += 1


def editorRowsToString() -> bytes:
    buf = bytearray()
    for row in E.row:
        buf += bytes(row.chars[:row.size])
        buf += b'\n'
    return bytes(buf)


def editorRowInsertChar(row: Erow, at: int, c: int) -> None:
    if at > row.size:
        padlen = at - row.size
        row.chars = _realloc(row.chars, row.size + padlen + 2)
        row.chars[row.size:row.size + padlen] = b' ' * padlen
        row.chars[row.size + padlen + 1] = 0
        row.size += padlen + 1
    else:
        row.chars = _realloc(row.chars, row.size + 2)
        n = row.size - at + 1
        tmp = bytes(row.chars[at:at + n])
        row.chars[at + 1:at + 1 + n] = tmp
        row.size += 1
    row.chars[at] = c
    editorUpdateRow(row)
    E.dirty += 1


def editorRowAppendString(row: Erow, s: bytes, length: int) -> None:
    row.chars = _realloc(row.chars, row.size + length + 1)
    row.chars[row.size:row.size + length] = s[:length]
    row.size += length
    row.chars[row.size] = 0
    editorUpdateRow(row)
    E.dirty += 1


def editorRowDelChar(row: Erow, at: int) -> None:
    if row.size <= at:
        return
    n = row.size - at
    tmp = bytes(row.chars[at + 1:at + 1 + n])
    row.chars[at:at + n] = tmp
    # NOTE: matches the original ordering exactly -- editorUpdateRow() is
    # called with the OLD row.size (not yet decremented), reproducing the
    # original's off-by-one stale-byte quirk until the next row edit.
    editorUpdateRow(row)
    row.size -= 1
    E.dirty += 1


def editorInsertChar(c: int) -> None:
    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx
    row = E.row[filerow] if filerow < E.numrows else None

    if row is None:
        while E.numrows <= filerow:
            editorInsertRow(E.numrows, b'', 0)
    row = E.row[filerow]
    editorRowInsertChar(row, filecol, c)
    if E.cx == E.screencols - 1:
        E.coloff += 1
    else:
        E.cx += 1
    E.dirty += 1


def editorInsertNewline() -> None:
    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx
    row = E.row[filerow] if filerow < E.numrows else None

    if row is None:
        if filerow == E.numrows:
            editorInsertRow(filerow, b'', 0)
        else:
            return
    else:
        if filecol >= row.size:
            filecol = row.size
        if filecol == 0:
            editorInsertRow(filerow, b'', 0)
        else:
            editorInsertRow(filerow + 1, bytes(row.chars[filecol:row.size]), row.size - filecol)
            row = E.row[filerow]
            row.chars[filecol] = 0
            row.size = filecol
            editorUpdateRow(row)

    if E.cy == E.screenrows - 1:
        E.rowoff += 1
    else:
        E.cy += 1
    E.cx = 0
    E.coloff = 0


def editorDelChar() -> None:
    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx
    row = E.row[filerow] if filerow < E.numrows else None

    if row is None or (filecol == 0 and filerow == 0):
        return
    if filecol == 0:
        filecol = E.row[filerow - 1].size
        editorRowAppendString(E.row[filerow - 1], bytes(row.chars[:row.size]), row.size)
        editorDelRow(filerow)
        row = None
        if E.cy == 0:
            E.rowoff -= 1
        else:
            E.cy -= 1
        E.cx = filecol
        if E.cx >= E.screencols:
            shift = (E.screencols - E.cx) + 1
            E.cx -= shift
            E.coloff += shift
    else:
        editorRowDelChar(row, filecol - 1)
        if E.cx == 0 and E.coloff:
            E.coloff -= 1
        else:
            E.cx -= 1
    if row is not None:
        editorUpdateRow(row)
    E.dirty += 1


def editorOpen(filename: str) -> int:
    E.dirty = 0
    E.filename = filename

    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        return 1
    except OSError as e:
        sys.stderr.write("Opening file: %s\n" % (e.strerror or str(e)))
        sys.exit(1)

    lines = data.split(b'\n')
    if data.endswith(b'\n'):
        lines = lines[:-1]

    for line in lines:
        if line.endswith(b'\r'):
            line = line[:-1]
        editorInsertRow(E.numrows, line, len(line))

    E.dirty = 0
    return 0


def editorSave() -> int:
    buf = editorRowsToString()
    fd = -1
    try:
        fd = os.open(E.filename, os.O_RDWR | os.O_CREAT, 0o644)
        os.ftruncate(fd, len(buf))
        n = os.write(fd, buf)
        if n != len(buf):
            raise OSError("short write")
        os.close(fd)
        E.dirty = 0
        editorSetStatusMessage("%d bytes written on disk" % len(buf))
        return 0
    except OSError as e:
        if fd != -1:
            try:
                os.close(fd)
            except OSError:
                pass
        msg = e.strerror if e.strerror else str(e)
        editorSetStatusMessage("Can't save! I/O error: %s" % msg)
        return 1


# ============================= Terminal update ===============================

class Abuf:
    __slots__ = ("b",)

    def __init__(self):
        self.b = bytearray()

    def append(self, data: bytes) -> None:
        self.b += data


def editorRefreshScreen() -> None:
    ab = Abuf()

    ab.append(b"\x1b[?25l")  # Hide cursor.
    ab.append(b"\x1b[H")     # Go home.

    for y in range(E.screenrows):
        filerow = E.rowoff + y

        if filerow >= E.numrows:
            if E.numrows == 0 and y == E.screenrows // 3:
                welcome = ("Kilo editor -- verison %s\x1b[0K\r\n" % KILO_VERSION).encode()
                welcomelen = len(welcome)
                padding = (E.screencols - welcomelen) // 2
                if padding > 0:
                    ab.append(b"~")
                    padding -= 1
                if padding > 0:
                    ab.append(b" " * padding)
                ab.append(welcome)
            else:
                ab.append(b"~\x1b[0K\r\n")
            continue

        r = E.row[filerow]
        length = r.rsize - E.coloff
        current_color = -1
        if length > 0:
            if length > E.screencols:
                length = E.screencols
            c = r.render[E.coloff:E.coloff + length]
            hl = r.hl[E.coloff:E.coloff + length] if r.hl else bytearray(length)
            for j in range(length):
                if j < len(hl) and hl[j] == HL_NONPRINT:
                    ab.append(b"\x1b[7m")
                    cj = c[j]
                    sym = chr((ord('@') + cj) & 0xFF) if cj <= 26 else '?'
                    ab.append(sym.encode('latin-1', errors='replace'))
                    ab.append(b"\x1b[0m")
                elif j >= len(hl) or hl[j] == HL_NORMAL:
                    if current_color != -1:
                        ab.append(b"\x1b[39m")
                        current_color = -1
                    ab.append(bytes(c[j:j + 1]))
                else:
                    color = editorSyntaxToColor(hl[j])
                    if color != current_color:
                        current_color = color
                        ab.append(("\x1b[%dm" % color).encode())
                    ab.append(bytes(c[j:j + 1]))
        ab.append(b"\x1b[39m")
        ab.append(b"\x1b[0K")
        ab.append(b"\r\n")

    # Status row 1.
    ab.append(b"\x1b[0K")
    ab.append(b"\x1b[7m")
    fname = (E.filename or "")[:20]
    status = "%.20s - %d lines %s" % (fname, E.numrows, "(modified)" if E.dirty else "")
    rstatus = "%d/%d" % (E.rowoff + E.cy + 1, E.numrows)
    status_b = status.encode()
    rstatus_b = rstatus.encode()
    slen = len(status_b)
    rlen = len(rstatus_b)
    if slen > E.screencols:
        slen = E.screencols
    ab.append(status_b[:slen])
    length = slen
    while length < E.screencols:
        if E.screencols - length == rlen:
            ab.append(rstatus_b)
            break
        else:
            ab.append(b" ")
            length += 1
    ab.append(b"\x1b[0m\r\n")

    # Status row 2 (message line).
    ab.append(b"\x1b[0K")
    msg = E.statusmsg.encode()
    if len(msg) and (time.time() - E.statusmsg_time) < 5:
        ab.append(msg[:E.screencols] if len(msg) > E.screencols else msg)

    # Position the cursor, accounting for TAB expansion.
    cx = 1
    filerow = E.rowoff + E.cy
    row = E.row[filerow] if filerow < E.numrows else None
    if row is not None:
        for j in range(E.coloff, E.cx + E.coloff):
            if j < row.size and row.chars[j] == TAB:
                cx += 7 - (cx % 8)
            cx += 1

    ab.append(("\x1b[%d;%dH" % (E.cy + 1, cx)).encode())
    ab.append(b"\x1b[?25h")  # Show cursor.

    try:
        os.write(sys.stdout.fileno(), bytes(ab.b))
    except OSError:
        pass


def editorSetStatusMessage(fmt: str, *args) -> None:
    msg = (fmt % args) if args else fmt
    E.statusmsg = msg[:79]
    E.statusmsg_time = time.time()


# =============================== Find mode ===================================

KILO_QUERY_LEN = 256


def editorFind(fd: int) -> None:
    query = ""
    last_match = -1
    find_next = 0
    saved_hl_line = -1
    saved_hl: Optional[bytearray] = None

    def restore_hl():
        nonlocal saved_hl, saved_hl_line
        if saved_hl is not None:
            E.row[saved_hl_line].hl = bytearray(saved_hl)
            saved_hl = None

    saved_cx, saved_cy = E.cx, E.cy
    saved_coloff, saved_rowoff = E.coloff, E.rowoff

    while True:
        editorSetStatusMessage("Search: %s (Use ESC/Arrows/Enter)", query)
        editorRefreshScreen()

        c = editorReadKey(fd)
        if c in (DEL_KEY, CTRL_H, BACKSPACE):
            if len(query) != 0:
                query = query[:-1]
            last_match = -1
        elif c in (ESC, ENTER):
            if c == ESC:
                E.cx, E.cy = saved_cx, saved_cy
                E.coloff, E.rowoff = saved_coloff, saved_rowoff
            restore_hl()
            editorSetStatusMessage("")
            return
        elif c in (ARROW_RIGHT, ARROW_DOWN):
            find_next = 1
        elif c in (ARROW_LEFT, ARROW_UP):
            find_next = -1
        elif 32 <= c < 127:
            if len(query) < KILO_QUERY_LEN:
                query += chr(c)
                last_match = -1

        if last_match == -1:
            find_next = 1
        if find_next:
            match_row = None
            match_offset = 0
            current = last_match
            query_bytes = query.encode()

            for _ in range(E.numrows):
                current += find_next
                if current == -1:
                    current = E.numrows - 1
                elif current == E.numrows:
                    current = 0
                idx = bytes(E.row[current].render[:E.row[current].rsize]).find(query_bytes)
                if idx != -1 and query_bytes:
                    match_row = current
                    match_offset = idx
                    break
            find_next = 0

            restore_hl()

            if match_row is not None:
                row = E.row[match_row]
                last_match = match_row
                if row.hl:
                    saved_hl_line = match_row
                    saved_hl = bytearray(row.hl)
                    for k in range(match_offset, min(match_offset + len(query), len(row.hl))):
                        row.hl[k] = HL_MATCH
                E.cy = 0
                E.cx = match_offset
                E.rowoff = match_row
                E.coloff = 0
                if E.cx > E.screencols:
                    diff = E.cx - E.screencols
                    E.cx -= diff
                    E.coloff += diff


# ========================= Editor events handling ============================

def editorMoveCursor(key: int) -> None:
    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx
    row = E.row[filerow] if filerow < E.numrows else None

    if key == ARROW_LEFT:
        if E.cx == 0:
            if E.coloff:
                E.coloff -= 1
            else:
                if filerow > 0:
                    E.cy -= 1
                    E.cx = E.row[filerow - 1].size
                    if E.cx > E.screencols - 1:
                        E.coloff = E.cx - E.screencols + 1
                        E.cx = E.screencols - 1
        else:
            E.cx -= 1
    elif key == ARROW_RIGHT:
        if row and filecol < row.size:
            if E.cx == E.screencols - 1:
                E.coloff += 1
            else:
                E.cx += 1
        elif row and filecol == row.size:
            E.cx = 0
            E.coloff = 0
            if E.cy == E.screenrows - 1:
                E.rowoff += 1
            else:
                E.cy += 1
    elif key == ARROW_UP:
        if E.cy == 0:
            if E.rowoff:
                E.rowoff -= 1
        else:
            E.cy -= 1
    elif key == ARROW_DOWN:
        if filerow < E.numrows:
            if E.cy == E.screenrows - 1:
                E.rowoff += 1
            else:
                E.cy += 1

    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx
    row = E.row[filerow] if filerow < E.numrows else None
    rowlen = row.size if row else 0
    if filecol > rowlen:
        E.cx -= (filecol - rowlen)
        if E.cx < 0:
            E.coloff += E.cx
            E.cx = 0


KILO_QUIT_TIMES = 3
_quit_times = [KILO_QUIT_TIMES]


def editorProcessKeypress(fd: int) -> None:
    c = editorReadKey(fd)

    if c == ENTER:
        editorInsertNewline()
    elif c == CTRL_C:
        # Ignored: it can't be so simple to lose the changes to the file.
        pass
    elif c == CTRL_Q:
        if E.dirty and _quit_times[0]:
            editorSetStatusMessage(
                "WARNING!!! File has unsaved changes. "
                "Press Ctrl-Q %d more times to quit.", _quit_times[0])
            _quit_times[0] -= 1
            return
        sys.exit(0)
    elif c == CTRL_S:
        editorSave()
    elif c == CTRL_F:
        editorFind(fd)
    elif c in (BACKSPACE, CTRL_H, DEL_KEY):
        editorDelChar()
    elif c in (PAGE_UP, PAGE_DOWN):
        if c == PAGE_UP and E.cy != 0:
            E.cy = 0
        elif c == PAGE_DOWN and E.cy != E.screenrows - 1:
            E.cy = E.screenrows - 1
        times = E.screenrows
        while times:
            editorMoveCursor(ARROW_UP if c == PAGE_UP else ARROW_DOWN)
            times -= 1
    elif c in (ARROW_UP, ARROW_DOWN, ARROW_LEFT, ARROW_RIGHT):
        editorMoveCursor(c)
    elif c == CTRL_L:
        # Just refresh the line as side effect.
        pass
    elif c == ESC:
        pass
    else:
        editorInsertChar(c)

    _quit_times[0] = KILO_QUIT_TIMES


def editorFileWasModified() -> bool:
    return bool(E.dirty)


def updateWindowSize() -> None:
    size = getWindowSize(sys.stdin.fileno(), sys.stdout.fileno())
    if size is None:
        sys.stderr.write("Unable to query the screen for size (columns / rows)\n")
        sys.exit(1)
    rows, cols = size
    E.screenrows = rows
    E.screencols = cols
    E.screenrows -= 2  # Get room for status bar.


def handleSigWinCh(signum, frame) -> None:
    updateWindowSize()
    if E.cy > E.screenrows:
        E.cy = E.screenrows - 1
    if E.cx > E.screencols:
        E.cx = E.screencols - 1
    editorRefreshScreen()


def initEditor() -> None:
    E.cx = 0
    E.cy = 0
    E.rowoff = 0
    E.coloff = 0
    E.numrows = 0
    E.row = []
    E.dirty = 0
    E.filename = None
    E.syntax = None
    updateWindowSize()
    signal.signal(signal.SIGWINCH, handleSigWinCh)


def main() -> None:
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: kilo <filename>\n")
        sys.exit(1)

    initEditor()
    editorSelectSyntaxHighlight(sys.argv[1])
    editorOpen(sys.argv[1])
    enableRawMode(sys.stdin.fileno())
    editorSetStatusMessage("HELP: Ctrl-S = save | Ctrl-Q = quit | Ctrl-F = find")

    while True:
        editorRefreshScreen()
        editorProcessKeypress(sys.stdin.fileno())


if __name__ == "__main__":
    main()