"""
string.py — C string.h implementation for PicoC.
"""
from typing import List
from value import CValue, cell_get, cell_set
from stdlib.stdio import _get_str_val, _get_int_val
from picoc_types import T_INT, T_CHAR_PTR, T_VOID_PTR, T_CHAR

class StringLib:
    def __init__(self, interp):
        self.interp = interp
        
    def get_functions(self) -> dict:
        return {
            'strlen': self._strlen,
            'strcpy': self._strcpy,
            'strncpy': self._strncpy,
            'strcmp': self._strcmp,
            'strncmp': self._strncmp,
            'strcat': self._strcat,
            'memcpy': self._memcpy,
            'memset': self._memset,
        }
        
    def _strlen(self, args: List[CValue]) -> CValue:
        s = _get_str_val(args[0])
        return CValue(T_INT, len(s))
        
    def _strcpy(self, args: List[CValue]) -> CValue:
        dest = args[0]
        src_str = _get_str_val(args[1])
        if dest.val and isinstance(dest.val, list):
            target = dest.val
            for i, c in enumerate(src_str + '\0'):
                if i < len(target):
                    cell_set(target[i], CValue(T_CHAR, ord(c)))
        return dest
        
    def _strncpy(self, args: List[CValue]) -> CValue:
        dest = args[0]
        src_str = _get_str_val(args[1])
        n = _get_int_val(args[2])
        if dest.val and isinstance(dest.val, list):
            target = dest.val
            for i in range(n):
                c = src_str[i] if i < len(src_str) else '\0'
                if i < len(target):
                    cell_set(target[i], CValue(T_CHAR, ord(c)))
        return dest
        
    def _strcmp(self, args: List[CValue]) -> CValue:
        s1 = _get_str_val(args[0])
        s2 = _get_str_val(args[1])
        if s1 == s2: return CValue(T_INT, 0)
        return CValue(T_INT, -1 if s1 < s2 else 1)
        
    def _strncmp(self, args: List[CValue]) -> CValue:
        s1 = _get_str_val(args[0])
        s2 = _get_str_val(args[1])
        n = _get_int_val(args[2])
        if s1[:n] == s2[:n]: return CValue(T_INT, 0)
        return CValue(T_INT, -1 if s1[:n] < s2[:n] else 1)
        
    def _strcat(self, args: List[CValue]) -> CValue:
        dest = args[0]
        src_str = _get_str_val(args[1])
        # Find null terminator in dest
        if dest.val and isinstance(dest.val, list):
            target = dest.val
            start = 0
            while start < len(target):
                v = cell_get(target[start]).val
                if v == 0 or v == '\0': break
                start += 1
            for i, c in enumerate(src_str + '\0'):
                if start + i < len(target):
                    cell_set(target[start+i], CValue(T_CHAR, ord(c)))
        return dest
        
    def _memcpy(self, args: List[CValue]) -> CValue:
        dest = args[0]
        src = args[1]
        n = _get_int_val(args[2])
        if dest.val and isinstance(dest.val, list) and src.val and isinstance(src.val, list):
            for i in range(n):
                if i < len(dest.val) and i < len(src.val):
                    v = cell_get(src.val[i])
                    cell_set(dest.val[i], v.copy())
        return dest
        
    def _memset(self, args: List[CValue]) -> CValue:
        dest = args[0]
        c = _get_int_val(args[1])
        n = _get_int_val(args[2])
        if dest.val and isinstance(dest.val, list):
            for i in range(n):
                if i < len(dest.val):
                    cell_set(dest.val[i], CValue(T_CHAR, c))
        return dest
