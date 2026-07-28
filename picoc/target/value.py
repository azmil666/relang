"""
value.py — Runtime value model for PicoC Python interpreter.

Core model: every "memory location" is a mutable list [CValue] called a "cell".
This lets us model C pointers, address-of (&), and dereference (*) cleanly.
"""
from __future__ import annotations
from typing import Optional, Any, List


# ─── Integer masking helpers ────────────────────────────────────────────────

def mask_char(v: int) -> int:
    """Signed 8-bit clamp."""
    v = int(v) & 0xFF
    return v - 256 if v >= 128 else v

def mask_uchar(v: int) -> int:
    return int(v) & 0xFF

def mask_short(v: int) -> int:
    v = int(v) & 0xFFFF
    return v - 65536 if v >= 32768 else v

def mask_ushort(v: int) -> int:
    return int(v) & 0xFFFF

def mask_int(v: int) -> int:
    v = int(v) & 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v

def mask_uint(v: int) -> int:
    return int(v) & 0xFFFFFFFF

def mask_long(v: int) -> int:
    v = int(v) & 0xFFFFFFFFFFFFFFFF
    return v - (1 << 64) if v >= (1 << 63) else v

def mask_ulong(v: int) -> int:
    return int(v) & 0xFFFFFFFFFFFFFFFF


TYPE_MASKS = {
    'char':           mask_char,
    'unsigned char':  mask_uchar,
    'short':          mask_short,
    'unsigned short': mask_ushort,
    'int':            mask_int,
    'unsigned int':   mask_uint,
    'long':           mask_long,
    'unsigned long':  mask_ulong,
}


# ─── CValue ──────────────────────────────────────────────────────────────────

class CValue:
    """
    A runtime C value.
    
    val: the Python representation of the value:
      - int, float for numeric types
      - list[CValue] cell reference for pointer types (the cell being pointed to)
      - list[list[CValue]] for array types (list of cells)
      - str for function names
      - dict for struct/union instances {'member': cell}
      - None for void/NULL
      
    cell: if this CValue is an LValue (addressable), this is the [CValue] list 
          that holds this value — so &x returns a pointer to x.cell.
    """
    __slots__ = ('typ', 'val', 'cell', 'is_lvalue')

    def __init__(self, typ, val, cell=None, is_lvalue=False):
        self.typ = typ           # CType instance
        self.val = val           # Python value
        self.cell = cell         # [CValue] mutable container (if LValue)
        self.is_lvalue = is_lvalue

    def copy(self) -> 'CValue':
        """Return a non-LValue copy (rvalue)."""
        return CValue(self.typ, self.val)

    def __repr__(self):
        return f"CValue({self.typ}, {self.val!r})"


def make_cell(cval: CValue) -> List[CValue]:
    """Wrap a CValue in a mutable cell and mark it as an LValue."""
    cell = [cval]
    cval.cell = cell
    cval.is_lvalue = True
    return cell


def cell_get(cell: List[CValue]) -> CValue:
    """Read value from a cell."""
    return cell[0]


def cell_set(cell: List[CValue], new_val: CValue):
    """Write a new value into a cell, preserving the cell reference."""
    cell[0] = new_val
    new_val.cell = cell
    new_val.is_lvalue = True


def make_int_cell(typ, v: int) -> List[CValue]:
    """Convenience: create a cell containing an integer CValue."""
    from picoc_types import CType  # avoid circular at module level
    cv = CValue(typ, v, is_lvalue=True)
    cell = [cv]
    cv.cell = cell
    return cell


def coerce_to_int(v: CValue) -> int:
    """Convert a CValue to Python int (for use in arithmetic/conditions)."""
    from picoc_types import BaseType
    if v is None or v.val is None:
        return 0
    if isinstance(v.val, float):
        return int(v.val)
    if isinstance(v.val, int):
        return v.val
    if isinstance(v.val, list):
        # pointer — non-null is truthy
        return 1 if v.val is not None else 0
    return 0


def coerce_to_float(v: CValue) -> float:
    if v is None or v.val is None:
        return 0.0
    if isinstance(v.val, float):
        return v.val
    if isinstance(v.val, int):
        return float(v.val)
    return 0.0


def is_zero(v: CValue) -> bool:
    """C truthiness: 0/NULL/0.0 are false."""
    if v is None or v.val is None:
        return True
    if isinstance(v.val, (int, float)):
        return v.val == 0
    if isinstance(v.val, list):
        return False  # non-null pointer
    return False


def apply_mask(typ_name: str, val: int) -> int:
    """Apply correct integer masking for named type."""
    fn = TYPE_MASKS.get(typ_name)
    if fn:
        return fn(val)
    return val
