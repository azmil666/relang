"""
math.py — C math.h implementation for PicoC.
"""
import math
from typing import List
from value import CValue
from stdlib.stdio import _get_float_val
from picoc_types import T_DOUBLE

class MathLib:
    def __init__(self, interp):
        self.interp = interp
        
    def get_functions(self) -> dict:
        return {
            'sin': self._sin,
            'cos': self._cos,
            'sqrt': self._sqrt,
            'pow': self._pow,
            'fabs': self._fabs,
            'floor': self._floor,
            'ceil': self._ceil,
        }
        
    def _sin(self, args: List[CValue]) -> CValue:
        v = _get_float_val(args[0])
        return CValue(T_DOUBLE, math.sin(v))
        
    def _cos(self, args: List[CValue]) -> CValue:
        v = _get_float_val(args[0])
        return CValue(T_DOUBLE, math.cos(v))
        
    def _sqrt(self, args: List[CValue]) -> CValue:
        v = _get_float_val(args[0])
        return CValue(T_DOUBLE, math.sqrt(v))
        
    def _pow(self, args: List[CValue]) -> CValue:
        b = _get_float_val(args[0])
        e = _get_float_val(args[1])
        return CValue(T_DOUBLE, math.pow(b, e))
        
    def _fabs(self, args: List[CValue]) -> CValue:
        v = _get_float_val(args[0])
        return CValue(T_DOUBLE, math.fabs(v))
        
    def _floor(self, args: List[CValue]) -> CValue:
        v = _get_float_val(args[0])
        return CValue(T_DOUBLE, float(math.floor(v)))
        
    def _ceil(self, args: List[CValue]) -> CValue:
        v = _get_float_val(args[0])
        return CValue(T_DOUBLE, float(math.ceil(v)))
