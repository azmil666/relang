"""
preprocessor.py — C preprocessor for PicoC Python interpreter.

Handles:
- #define (object macros and function macros)
- #include (stdio.h, stdlib.h, etc. → stub injection, no file I/O)
- #if / #ifdef / #ifndef / #else / #elif / #endif
- #undef
- Macro expansion in source before tokenization

Strategy: run as a string-level pass BEFORE tokenization, producing
a clean C string with all preprocessor directives resolved.
"""
from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple


class Preprocessor:
    """
    Processes C source text through the preprocessor pass.
    Returns clean source text with directives resolved.
    """

    # Headers we "know about" — their #includes are silently accepted
    KNOWN_HEADERS = {
        'stdio.h', 'stdlib.h', 'string.h', 'math.h',
        'ctype.h', 'stdbool.h', 'time.h', 'unistd.h',
        'errno.h', 'assert.h', 'stdarg.h', 'stddef.h',
        'limits.h', 'float.h',
    }

    def __init__(self):
        # defines: name → (params_or_None, body_str)
        self.defines: Dict[str, Tuple[Optional[List[str]], str]] = {}
        self._init_predefined()

    def _init_predefined(self):
        """Built-in defines."""
        self.defines['NULL'] = (None, '((void*)0)')
        self.defines['true'] = (None, '1')
        self.defines['false'] = (None, '0')
        self.defines['bool'] = (None, '_Bool')
        self.defines['__LINE__'] = (None, '0')  # placeholder
        self.defines['__FILE__'] = (None, '"<input>"')
        self.defines['INT_MAX'] = (None, '2147483647')
        self.defines['INT_MIN'] = (None, '(-2147483648)')
        self.defines['UINT_MAX'] = (None, '4294967295U')
        self.defines['LONG_MAX'] = (None, '9223372036854775807L')
        self.defines['CHAR_MAX'] = (None, '127')
        self.defines['CHAR_MIN'] = (None, '(-128)')
        self.defines['UCHAR_MAX'] = (None, '255')
        self.defines['SHRT_MAX'] = (None, '32767')
        self.defines['SHRT_MIN'] = (None, '(-32768)')
        self.defines['EOF'] = (None, '(-1)')
        self.defines['EXIT_SUCCESS'] = (None, '0')
        self.defines['EXIT_FAILURE'] = (None, '1')
        self.defines['RAND_MAX'] = (None, '2147483647')
        self.defines['SIZE_MAX'] = (None, '18446744073709551615UL')

    def process(self, source: str, filename: str = '<input>') -> str:
        """Main preprocessing pass."""
        lines = source.split('\n')
        output_lines = []
        i = 0
        # Stack: list of (condition_met, any_met) for nested #if blocks
        cond_stack: List[Tuple[bool, bool]] = []

        def is_active() -> bool:
            return all(met for met, _ in cond_stack)

        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()

            if stripped.startswith('#'):
                directive_line, i = self._collect_continuation(lines, i)
                self._handle_directive(directive_line.strip(), cond_stack,
                                       output_lines, is_active, filename, i)
            else:
                if is_active():
                    expanded = self._expand_line(line)
                    output_lines.append(expanded)
                else:
                    output_lines.append('')  # preserve line numbers
                i += 1

        return '\n'.join(output_lines)

    def _collect_continuation(self, lines: List[str], i: int) -> Tuple[str, int]:
        """Collect a directive line including backslash continuations."""
        result = lines[i]
        while result.endswith('\\') and i + 1 < len(lines):
            result = result[:-1] + ' '
            i += 1
            result += lines[i]
        return result, i + 1

    def _handle_directive(self, line: str, cond_stack, output_lines,
                           is_active_fn, filename: str, lineno: int):
        """Process a single preprocessor directive."""
        # Strip leading #
        line = line.lstrip()
        if not line.startswith('#'):
            return
        line = line[1:].lstrip()
        # Split directive name from rest
        parts = line.split(None, 1)
        if not parts:
            return
        directive = parts[0]
        rest = parts[1] if len(parts) > 1 else ''

        if directive == 'define':
            if is_active_fn():
                self._handle_define(rest)
            return

        if directive == 'undef':
            if is_active_fn():
                name = rest.split()[0] if rest.split() else ''
                self.defines.pop(name, None)
            return

        if directive == 'include':
            if is_active_fn():
                # Just accept known headers silently
                output_lines.append('')  # blank line to preserve line count
            return

        if directive == 'ifdef':
            name = rest.strip().split()[0] if rest.strip() else ''
            cond = name in self.defines
            cond_stack.append((cond, cond))
            return

        if directive == 'ifndef':
            name = rest.strip().split()[0] if rest.strip() else ''
            cond = name not in self.defines
            cond_stack.append((cond, cond))
            return

        if directive == 'if':
            if is_active_fn():
                cond = bool(self._eval_const_expr(rest.strip()))
            else:
                cond = False
            cond_stack.append((cond, cond))
            return

        if directive == 'elif':
            if cond_stack:
                _, any_met = cond_stack[-1]
                if not any_met and is_active_fn():
                    cond = bool(self._eval_const_expr(rest.strip()))
                else:
                    cond = False
                cond_stack[-1] = (cond, any_met or cond)
            return

        if directive == 'else':
            if cond_stack:
                _, any_met = cond_stack[-1]
                cond = not any_met
                cond_stack[-1] = (cond, True)
            return

        if directive == 'endif':
            if cond_stack:
                cond_stack.pop()
            return

        if directive in ('pragma', 'line', 'error'):
            return  # ignore

        # Unknown directive — ignore
        return

    def _handle_define(self, rest: str):
        """Parse and store a #define."""
        rest = rest.strip()
        if not rest:
            return

        # Check for function macro: name( with no space before (
        m = re.match(r'^([A-Za-z_]\w*)\(([^)]*)\)\s*(.*)', rest, re.DOTALL)
        if m:
            name = m.group(1)
            params_str = m.group(2)
            body = m.group(3).strip()
            params = [p.strip() for p in params_str.split(',')] if params_str.strip() else []
            self.defines[name] = (params, body)
        else:
            # Object macro
            parts = rest.split(None, 1)
            name = parts[0]
            body = parts[1].strip() if len(parts) > 1 else ''
            # Remove trailing comment
            body = re.sub(r'\s*//.*$', '', body)
            self.defines[name] = (None, body)

    def _expand_line(self, line: str) -> str:
        """Expand macros in a source line."""
        return self._expand_text(line, set())

    def _expand_text(self, text: str, expanding: set, depth: int = 0) -> str:
        """Recursively expand macros in text."""
        if depth > 32:
            return text  # prevent infinite recursion

        result = ''
        i = 0
        n = len(text)

        while i < n:
            c = text[i]

            # Skip string literals
            if c == '"':
                result += c; i += 1
                while i < n and text[i] != '"':
                    if text[i] == '\\' and i + 1 < n:
                        result += text[i] + text[i+1]; i += 2
                    else:
                        result += text[i]; i += 1
                if i < n:
                    result += text[i]; i += 1
                continue

            # Skip char literals
            if c == "'":
                result += c; i += 1
                while i < n and text[i] != "'":
                    if text[i] == '\\' and i + 1 < n:
                        result += text[i] + text[i+1]; i += 2
                    else:
                        result += text[i]; i += 1
                if i < n:
                    result += text[i]; i += 1
                continue

            # Identifier
            if c.isalpha() or c == '_':
                j = i
                while j < n and (text[j].isalnum() or text[j] == '_'):
                    j += 1
                word = text[i:j]

                if word in self.defines and word not in expanding:
                    params, body = self.defines[word]

                    if params is None:
                        # Object macro
                        expanded = self._expand_text(body, expanding | {word}, depth + 1)
                        result += expanded
                        i = j
                        continue
                    else:
                        # Function macro — find arguments
                        k = j
                        while k < n and text[k] in ' \t':
                            k += 1
                        if k < n and text[k] == '(':
                            args, end = self._collect_macro_args(text, k)
                            expanded_body = self._substitute_macro(params, body, args)
                            expanded = self._expand_text(expanded_body, expanding | {word}, depth + 1)
                            result += expanded
                            i = end
                            continue

                result += word
                i = j
                continue

            result += c
            i += 1

        return result

    def _collect_macro_args(self, text: str, start: int):
        """Collect comma-separated macro arguments from '(' to matching ')'."""
        assert text[start] == '('
        args = []
        current = ''
        depth = 0
        i = start + 1  # skip '('
        n = len(text)

        while i < n:
            c = text[i]
            if c == '(' :
                depth += 1; current += c; i += 1
            elif c == ')':
                if depth == 0:
                    args.append(current.strip())
                    i += 1
                    break
                depth -= 1; current += c; i += 1
            elif c == ',' and depth == 0:
                args.append(current.strip())
                current = ''
                i += 1
            else:
                current += c; i += 1

        return args, i

    def _substitute_macro(self, params: List[str], body: str, args: List[str]) -> str:
        """Substitute macro parameters with arguments."""
        # Handle # (stringify) and ## (concat) operators
        result = body

        # First handle ## (token paste)
        result = re.sub(r'\s*##\s*', '', result)

        # Then handle # (stringify)
        def stringify(m):
            param = m.group(1)
            idx = params.index(param) if param in params else -1
            if idx >= 0 and idx < len(args):
                return f'"{args[idx]}"'
            return f'"{param}"'

        result = re.sub(r'#\s*([A-Za-z_]\w*)', stringify, result)

        # Replace parameters with arguments
        for param, arg in zip(params, args):
            result = re.sub(r'\b' + re.escape(param) + r'\b', arg, result)

        return result

    def _eval_const_expr(self, expr: str) -> int:
        """Evaluate a constant preprocessor expression."""
        # Expand macros first
        expr = self._expand_text(expr, set())

        # Handle 'defined(NAME)' and 'defined NAME'
        def replace_defined(m):
            name = m.group(1) or m.group(2)
            return '1' if name.strip() in self.defines else '0'

        expr = re.sub(r'defined\s*\(\s*([A-Za-z_]\w*)\s*\)', replace_defined, expr)
        expr = re.sub(r'defined\s+([A-Za-z_]\w*)', replace_defined, expr)

        # Replace any remaining identifiers with 0
        expr = re.sub(r'\b([A-Za-z_]\w*)\b', '0', expr)

        # Remove suffixes from numbers
        expr = re.sub(r'(\d+)[uUlLfF]+', r'\1', expr)

        # Handle sizeof — stub as 4
        expr = re.sub(r'sizeof\s*\([^)]*\)', '4', expr)
        expr = re.sub(r'sizeof\s+\w+', '4', expr)

        try:
            return int(eval(expr, {"__builtins__": {}}))
        except Exception:
            return 0
