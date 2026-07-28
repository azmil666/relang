"""
stdlib.py — C stdlib implementation for PicoC.
"""
from typing import List
from value import CValue, make_cell
from stdlib.stdio import _get_int_val, _get_str_val
from picoc_types import T_INT, T_VOID_PTR, T_VOID
import random
import sys

class StdlibLib:
    def __init__(self, interp):
        self.interp = interp
        
    def get_functions(self) -> dict:
        return {
            'malloc': self._malloc,
            'calloc': self._calloc,
            'realloc': self._realloc,
            'free': self._free,
            'atoi': self._atoi,
            'rand': self._rand,
            'srand': self._srand,
            'abs': self._abs,
            'exit': self._exit,
        }
        
    def _malloc(self, args: List[CValue]) -> CValue:
        size = _get_int_val(args[0]) if args else 0
        # In our model, a pointer is a cell or list of cells.
        # malloc returns a block of bytes (char cells).
        # We can just return a list of cells.
        from picoc_types import T_CHAR
        arr = [make_cell(CValue(T_CHAR, 0)) for _ in range(size)]
        return CValue(T_VOID_PTR, arr)
        
    def _calloc(self, args: List[CValue]) -> CValue:
        n = _get_int_val(args[0]) if len(args) > 0 else 0
        size = _get_int_val(args[1]) if len(args) > 1 else 0
        from picoc_types import T_CHAR
        arr = [make_cell(CValue(T_CHAR, 0)) for _ in range(n * size)]
        return CValue(T_VOID_PTR, arr)
        
    def _realloc(self, args: List[CValue]) -> CValue:
        ptr = args[0]
        size = _get_int_val(args[1])
        from picoc_types import T_CHAR
        arr = [make_cell(CValue(T_CHAR, 0)) for _ in range(size)]
        if ptr.val and isinstance(ptr.val, list):
            # copy old data
            for i in range(min(len(ptr.val), size)):
                arr[i] = ptr.val[i]
        return CValue(T_VOID_PTR, arr)
        
    def _free(self, args: List[CValue]) -> CValue:
        # no-op in Python
        return CValue(T_VOID, None)
        
    def _atoi(self, args: List[CValue]) -> CValue:
        s = _get_str_val(args[0])
        try:
            return CValue(T_INT, int(s))
        except ValueError:
            return CValue(T_INT, 0)
            
    def _rand(self, args: List[CValue]) -> CValue:
        return CValue(T_INT, random.randint(0, 32767))
        
    def _srand(self, args: List[CValue]) -> CValue:
        random.seed(_get_int_val(args[0]))
        return CValue(T_VOID, None)
        
    def _abs(self, args: List[CValue]) -> CValue:
        v = _get_int_val(args[0])
        return CValue(T_INT, abs(v))
        
    def _exit(self, args: List[CValue]) -> CValue:
        sys.exit(_get_int_val(args[0]))
