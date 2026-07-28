"""
stdbool.py — C stdbool.h definitions for PicoC.
"""
from value import CValue, make_cell
from picoc_types import T_BOOL

def inject_stdbool(interp):
    interp.call_stack.define_global('true', make_cell(CValue(T_BOOL, 1)))
    interp.call_stack.define_global('false', make_cell(CValue(T_BOOL, 0)))
