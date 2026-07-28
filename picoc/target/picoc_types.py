"""
picoc_types.py — C type system for PicoC Python interpreter.

Handles type creation, sizeof computation with C alignment/padding rules,
and the type derivation chain (pointer, array, struct, union, typedef).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from enum import Enum, auto


class BaseType(Enum):
    VOID       = auto()
    CHAR       = auto()
    SHORT      = auto()
    INT        = auto()
    LONG       = auto()
    UCHAR      = auto()
    USHORT     = auto()
    UINT       = auto()
    ULONG      = auto()
    FLOAT      = auto()
    DOUBLE     = auto()
    POINTER    = auto()
    ARRAY      = auto()
    STRUCT     = auto()
    UNION      = auto()
    ENUM       = auto()
    FUNCTION   = auto()
    TYPEDEF    = auto()
    BOOL       = auto()


@dataclass
class CType:
    base: BaseType
    name: str = ''               # 'int', 'char', struct tag, etc.
    sizeof: int = 0              # pre-computed size in bytes
    align: int = 1               # alignment requirement in bytes
    # For pointer:
    ptr_to: Optional['CType'] = None
    # For array:
    array_of: Optional['CType'] = None
    array_size: int = 0          # 0 = unsized (decay)
    # For struct/union:
    members: Optional[Dict[str, Tuple['CType', int]]] = None  # name → (type, byte_offset)
    member_order: Optional[List[str]] = None
    # For function:
    return_type: Optional['CType'] = None
    param_types: Optional[List['CType']] = None
    is_variadic: bool = False
    # For typedef:
    typedef_of: Optional['CType'] = None
    # Qualifiers
    is_static: bool = False
    is_const: bool = False
    is_unsigned: bool = False

    def resolve(self) -> 'CType':
        """Unwrap typedef chain."""
        t = self
        while t.base == BaseType.TYPEDEF and t.typedef_of is not None:
            t = t.typedef_of
        return t

    def is_integer(self) -> bool:
        t = self.resolve()
        return t.base in (BaseType.CHAR, BaseType.SHORT, BaseType.INT,
                          BaseType.LONG, BaseType.UCHAR, BaseType.USHORT,
                          BaseType.UINT, BaseType.ULONG, BaseType.ENUM,
                          BaseType.BOOL)

    def is_numeric(self) -> bool:
        t = self.resolve()
        return self.is_integer() or t.base in (BaseType.FLOAT, BaseType.DOUBLE)

    def is_pointer(self) -> bool:
        t = self.resolve()
        return t.base in (BaseType.POINTER, BaseType.ARRAY)

    def is_signed(self) -> bool:
        t = self.resolve()
        return t.base in (BaseType.CHAR, BaseType.SHORT, BaseType.INT, BaseType.LONG)

    def is_fp(self) -> bool:
        t = self.resolve()
        return t.base in (BaseType.FLOAT, BaseType.DOUBLE)

    def deref(self) -> Optional['CType']:
        """Type when dereferencing a pointer/array."""
        t = self.resolve()
        if t.base == BaseType.POINTER:
            return t.ptr_to
        if t.base == BaseType.ARRAY:
            return t.array_of
        return None

    def decay(self) -> 'CType':
        """Array decays to pointer to element."""
        t = self.resolve()
        if t.base == BaseType.ARRAY:
            return make_pointer(t.array_of)
        return self

    def __repr__(self):
        return f"CType({self.base.name}, {self.name!r})"

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other


# ─── Primitive type singletons ──────────────────────────────────────────────

T_VOID   = CType(BaseType.VOID,   'void',           sizeof=0,  align=1)
T_CHAR   = CType(BaseType.CHAR,   'char',           sizeof=1,  align=1)
T_UCHAR  = CType(BaseType.UCHAR,  'unsigned char',  sizeof=1,  align=1)
T_SHORT  = CType(BaseType.SHORT,  'short',          sizeof=2,  align=2)
T_USHORT = CType(BaseType.USHORT, 'unsigned short', sizeof=2,  align=2)
T_INT    = CType(BaseType.INT,    'int',            sizeof=4,  align=4)
T_UINT   = CType(BaseType.UINT,   'unsigned int',   sizeof=4,  align=4)
T_LONG   = CType(BaseType.LONG,   'long',           sizeof=8,  align=8)
T_ULONG  = CType(BaseType.ULONG,  'unsigned long',  sizeof=8,  align=8)
T_FLOAT  = CType(BaseType.FLOAT,  'float',          sizeof=4,  align=4)
T_DOUBLE = CType(BaseType.DOUBLE, 'double',         sizeof=8,  align=8)
T_BOOL   = CType(BaseType.BOOL,   '_Bool',          sizeof=1,  align=1)

# Commonly needed derived types (initialized below)
T_CHAR_PTR = None
T_VOID_PTR = None
T_INT_PTR  = None


def _init_derived():
    global T_CHAR_PTR, T_VOID_PTR, T_INT_PTR
    T_CHAR_PTR = make_pointer(T_CHAR)
    T_VOID_PTR = make_pointer(T_VOID)
    T_INT_PTR  = make_pointer(T_INT)


PRIMITIVE_TYPES = {
    'void':           T_VOID,
    'char':           T_CHAR,
    'unsigned char':  T_UCHAR,
    'short':          T_SHORT,
    'short int':      T_SHORT,
    'unsigned short': T_USHORT,
    'int':            T_INT,
    'unsigned int':   T_UINT,
    'unsigned':       T_UINT,
    'long':           T_LONG,
    'long int':       T_LONG,
    'unsigned long':  T_ULONG,
    'unsigned long int': T_ULONG,
    'float':          T_FLOAT,
    'double':         T_DOUBLE,
    'long double':    T_DOUBLE,  # treat as double
    '_Bool':          T_BOOL,
    'bool':           T_BOOL,
}

TYPE_NAME_MAP = {
    BaseType.VOID:   'void',
    BaseType.CHAR:   'char',
    BaseType.UCHAR:  'unsigned char',
    BaseType.SHORT:  'short',
    BaseType.USHORT: 'unsigned short',
    BaseType.INT:    'int',
    BaseType.UINT:   'unsigned int',
    BaseType.LONG:   'long',
    BaseType.ULONG:  'unsigned long',
    BaseType.FLOAT:  'float',
    BaseType.DOUBLE: 'double',
    BaseType.BOOL:   '_Bool',
}


# ─── Type factories ─────────────────────────────────────────────────────────

def make_pointer(base: CType) -> CType:
    return CType(BaseType.POINTER, f'{base.name}*',
                 sizeof=8, align=8, ptr_to=base)


def make_array(elem: CType, size: int) -> CType:
    sz = elem.sizeof * size if size > 0 else 0
    return CType(BaseType.ARRAY, f'{elem.name}[{size}]',
                 sizeof=sz, align=elem.align,
                 array_of=elem, array_size=size)


def make_struct(tag: str, members_list: List[Tuple[str, CType]]) -> CType:
    """Build a struct type computing C alignment and padding."""
    members = {}
    member_order = []
    offset = 0
    max_align = 1
    for mname, mtype in members_list:
        mtype = mtype.resolve()
        a = mtype.align
        if a > 1:
            offset = (offset + a - 1) & ~(a - 1)  # align up
        members[mname] = (mtype, offset)
        member_order.append(mname)
        offset += mtype.sizeof
        if a > max_align:
            max_align = a
    # Final struct size is padded to its own alignment
    total = (offset + max_align - 1) & ~(max_align - 1) if max_align > 1 else offset
    return CType(BaseType.STRUCT, tag,
                 sizeof=total, align=max_align,
                 members=members, member_order=member_order)


def make_union(tag: str, members_list: List[Tuple[str, CType]]) -> CType:
    """Build a union type (all members start at offset 0, size = max member)."""
    members = {}
    member_order = []
    max_size = 0
    max_align = 1
    for mname, mtype in members_list:
        mtype = mtype.resolve()
        members[mname] = (mtype, 0)  # all at offset 0
        member_order.append(mname)
        if mtype.sizeof > max_size:
            max_size = mtype.sizeof
        if mtype.align > max_align:
            max_align = mtype.align
    total = (max_size + max_align - 1) & ~(max_align - 1) if max_align > 1 else max_size
    return CType(BaseType.UNION, tag,
                 sizeof=total, align=max_align,
                 members=members, member_order=member_order)


def make_enum(tag: str) -> CType:
    return CType(BaseType.ENUM, tag, sizeof=4, align=4)


def make_function(ret: CType, params: List[CType], variadic=False) -> CType:
    return CType(BaseType.FUNCTION, f'fn→{ret.name}',
                 sizeof=0, align=1,
                 return_type=ret, param_types=params, is_variadic=variadic)


def make_typedef(name: str, target: CType) -> CType:
    return CType(BaseType.TYPEDEF, name, sizeof=target.sizeof, align=target.align,
                 typedef_of=target)


def sizeof_type(t: CType) -> int:
    """Get sizeof for a CType."""
    return t.resolve().sizeof


_init_derived()
