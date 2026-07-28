"""
scope.py — Symbol tables and call stack for PicoC Python interpreter.

A Scope is a dict mapping name → cell ([CValue]).
The CallStack tracks function scopes.
Static variables persist in a global registry keyed on (func_name, var_name).
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any


class Scope:
    """A single variable scope (function body, block, or global)."""

    def __init__(self, name: str = '<scope>', parent: Optional['Scope'] = None):
        self.name = name
        self.parent = parent
        # name → cell ([CValue])
        self._vars: Dict[str, list] = {}

    def define(self, name: str, cell: list):
        """Define a new variable in this scope."""
        self._vars[name] = cell

    def lookup(self, name: str) -> Optional[list]:
        """Look up a variable, searching parent scopes."""
        scope = self
        while scope is not None:
            if name in scope._vars:
                return scope._vars[name]
            scope = scope.parent
        return None

    def lookup_local(self, name: str) -> Optional[list]:
        """Look up only in this scope (not parents)."""
        return self._vars.get(name)

    def assign(self, name: str, cell: list):
        """Find and update an existing binding."""
        scope = self
        while scope is not None:
            if name in scope._vars:
                scope._vars[name] = cell
                return True
            scope = scope.parent
        return False

    def all_names(self):
        return list(self._vars.keys())

    def __repr__(self):
        return f"Scope({self.name}, vars={list(self._vars.keys())})"


class CallStack:
    """
    Manages the function call stack.

    Stack frames: list of (func_name, scope, return_value_cell)
    """

    def __init__(self, global_scope: Scope):
        self.global_scope = global_scope
        self.frames: List[Dict] = []  # stack of frame dicts
        self._static_vars: Dict[Tuple[str, str], list] = {}  # (func, name) → cell

    def push_frame(self, func_name: str, parent_scope: Optional[Scope] = None):
        """Push a new stack frame for a function call."""
        frame_scope = Scope(func_name, parent=self.global_scope)
        frame = {
            'func_name': func_name,
            'scope': frame_scope,
            'return_value': None,
            'returning': False,
            'breaking': False,
            'continuing': False,
            'goto_label': None,
        }
        self.frames.append(frame)

    def pop_frame(self) -> Optional[Any]:
        """Pop the current frame and return the return value."""
        if self.frames:
            frame = self.frames.pop()
            return frame.get('return_value')
        return None

    @property
    def current_frame(self) -> Optional[Dict]:
        return self.frames[-1] if self.frames else None

    @property
    def current_scope(self) -> Scope:
        if self.frames:
            return self.frames[-1]['scope']
        return self.global_scope

    @property
    def current_func_name(self) -> str:
        if self.frames:
            return self.frames[-1]['func_name']
        return '<global>'

    def push_block_scope(self) -> Scope:
        """Push a nested block scope inside current frame."""
        parent = self.current_scope
        new_scope = Scope(f'{self.current_func_name}:block', parent=parent)
        if self.frames:
            self.frames[-1]['scope'] = new_scope
        return new_scope

    def pop_block_scope(self, outer_scope: Scope):
        """Restore the outer scope after a block."""
        if self.frames:
            self.frames[-1]['scope'] = outer_scope

    def define_var(self, name: str, cell: list):
        """Define a variable in the current scope."""
        self.current_scope.define(name, cell)

    def define_global(self, name: str, cell: list):
        """Define in global scope."""
        self.global_scope.define(name, cell)

    def lookup(self, name: str) -> Optional[list]:
        """Look up a variable starting from current scope."""
        return self.current_scope.lookup(name)

    def lookup_global(self, name: str) -> Optional[list]:
        return self.global_scope.lookup(name)

    # ── Static variables ──────────────────────────────────────────────────

    def get_static(self, func_name: str, var_name: str) -> Optional[list]:
        """Get a static variable's cell if it exists."""
        return self._static_vars.get((func_name, var_name))

    def set_static(self, func_name: str, var_name: str, cell: list):
        """Register a static variable's cell."""
        self._static_vars[(func_name, var_name)] = cell

    # ── Control flow signals ──────────────────────────────────────────────

    def signal_return(self, value=None):
        if self.frames:
            self.frames[-1]['return_value'] = value
            self.frames[-1]['returning'] = True

    def signal_break(self):
        if self.frames:
            self.frames[-1]['breaking'] = True

    def signal_continue(self):
        if self.frames:
            self.frames[-1]['continuing'] = True

    def signal_goto(self, label: str):
        if self.frames:
            self.frames[-1]['goto_label'] = label

    def is_returning(self) -> bool:
        return bool(self.frames and self.frames[-1]['returning'])

    def is_breaking(self) -> bool:
        return bool(self.frames and self.frames[-1]['breaking'])

    def is_continuing(self) -> bool:
        return bool(self.frames and self.frames[-1]['continuing'])

    def get_goto_label(self) -> Optional[str]:
        return self.frames[-1]['goto_label'] if self.frames else None

    def clear_break(self):
        if self.frames:
            self.frames[-1]['breaking'] = False

    def clear_continue(self):
        if self.frames:
            self.frames[-1]['continuing'] = False

    def clear_goto(self):
        if self.frames:
            self.frames[-1]['goto_label'] = None

    def is_interrupted(self) -> bool:
        """Any control flow signal active."""
        if not self.frames:
            return False
        f = self.frames[-1]
        return f['returning'] or f['breaking'] or f['continuing'] or f['goto_label'] is not None

    def interrupt_reason(self) -> str:
        if not self.frames:
            return 'none'
        f = self.frames[-1]
        if f['returning']: return 'return'
        if f['breaking']: return 'break'
        if f['continuing']: return 'continue'
        if f['goto_label']: return 'goto'
        return 'none'
