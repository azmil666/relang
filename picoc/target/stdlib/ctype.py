"""
ctype.py — C ctype.h implementation for PicoC.
"""
from typing import List
from value import CValue
from stdlib.stdio import _get_int_val
from picoc_types import T_INT

class CtypeLib:
    def __init__(self, interp):
        self.interp = interp
        
    def get_functions(self) -> dict:
        return {
            'isalpha': self._isalpha,
            'isdigit': self._isdigit,
            'isspace': self._isspace,
            'toupper': self._toupper,
            'tolower': self._tolower,
        }
        
    def _isalpha(self, args: List[CValue]) -> CValue:
        v = chr(_get_int_val(args[0]) & 0xFF)
        return CValue(T_INT, 1 if v.isalpha() else 0)
        
    def _isdigit(self, args: List[CValue]) -> CValue:
        v = chr(_get_int_val(args[0]) & 0xFF)
        return CValue(T_INT, 1 if v.isdigit() else 0)
        
    def _isspace(self, args: List[CValue]) -> CValue:
        v = chr(_get_int_val(args[0]) & 0xFF)
        return CValue(T_INT, 1 if v.isspace() else 0)
        
    def _toupper(self, args: List[CValue]) -> CValue:
        v = _get_int_val(args[0])
        c = chr(v & 0xFF).upper()
        return CValue(T_INT, ord(c))
        
    def _tolower(self, args: List[CValue]) -> CValue:
        v = _get_int_val(args[0])
        c = chr(v & 0xFF).lower()
        return CValue(T_INT, ord(c))
