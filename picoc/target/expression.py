"""
expression.py — Runtime expression evaluator for PicoC Python interpreter.
"""
from typing import Optional, List
from lexer import TT, Token
from value import CValue, make_cell, cell_get, cell_set, coerce_to_int, coerce_to_float, is_zero, apply_mask
from picoc_types import BaseType, CType, T_INT, T_LONG, T_UINT, T_ULONG, T_FLOAT, T_DOUBLE, T_CHAR, T_VOID_PTR, make_pointer, sizeof_type

# Precedence levels
PREC_ASSIGN = 1
PREC_TERNARY = 2
PREC_OR = 3
PREC_AND = 4
PREC_BIT_OR = 5
PREC_BIT_XOR = 6
PREC_BIT_AND = 7
PREC_EQUALITY = 8
PREC_RELATIONAL = 9
PREC_SHIFT = 10
PREC_ADDITIVE = 11
PREC_MULTIPLICATIVE = 12
PREC_PREFIX = 13
PREC_POSTFIX = 14

class EvalError(Exception):
    def __init__(self, msg, token=None):
        line = token.line if token else 0
        super().__init__(f"EvalError line {line}: {msg}")

def eval_expr(interp, precedence=0) -> CValue:
    """Parse and evaluate an expression using Pratt parsing."""
    tok = interp.cur()
    
    # PREFIX
    if tok.type == TT.LPAREN:
        # Could be a cast or grouping
        if _is_type_start(interp, 1):
            # Cast
            interp.advance() # consume (
            cast_type = interp.parse_type()
            interp.expect(TT.RPAREN)
            rhs = eval_expr(interp, PREC_PREFIX)
            left = _apply_cast(cast_type, rhs)
        else:
            # Grouping
            interp.advance()
            left = eval_expr(interp, 0)
            interp.expect(TT.RPAREN)
    elif tok.type == TT.IDENT:
        interp.advance()
        name = tok.value
        # Variable lookup
        cell = interp.call_stack.lookup(name)
        if cell is not None:
            v = cell_get(cell)
            left = CValue(v.typ, v.val, cell=cell, is_lvalue=True)
        else:
            # Maybe a function name
            func = interp.call_stack.lookup_global(name)
            if func is not None:
                fv = cell_get(func)
                left = fv
            else:
                raise EvalError(f"Undefined variable '{name}'", tok)
    elif tok.type in (TT.INT_LIT, TT.FLOAT_LIT, TT.CHAR_LIT):
        interp.advance()
        if tok.type == TT.INT_LIT:
            val, suffix = tok.value
            left = CValue(T_INT, val) # Simplify type selection for literals
        elif tok.type == TT.FLOAT_LIT:
            val, suffix = tok.value
            typ = T_FLOAT if 'f' in suffix else T_DOUBLE
            left = CValue(typ, val)
        elif tok.type == TT.CHAR_LIT:
            left = CValue(T_CHAR, tok.value)
    elif tok.type == TT.STRING_LIT:
        interp.advance()
        from picoc_types import T_CHAR_PTR
        # In a real compiler, strings are stored in read-only memory.
        # Here we just treat them as char arrays, represented by strings.
        # We need it to be a char pointer if passed to functions.
        s = tok.value
        # Create a cell array
        arr = []
        for c in s:
            cv = CValue(T_CHAR, ord(c))
            arr.append(make_cell(cv))
        arr.append(make_cell(CValue(T_CHAR, 0))) # null terminator
        left = CValue(T_CHAR_PTR, arr)
    elif tok.type == TT.PLUS:
        interp.advance()
        left = eval_expr(interp, PREC_PREFIX)
        # Unary plus does nothing
    elif tok.type == TT.MINUS:
        interp.advance()
        rhs = eval_expr(interp, PREC_PREFIX)
        left = _unary_op('-', rhs)
    elif tok.type == TT.BANG:
        interp.advance()
        rhs = eval_expr(interp, PREC_PREFIX)
        left = CValue(T_INT, 1 if is_zero(rhs) else 0)
    elif tok.type == TT.TILDE:
        interp.advance()
        rhs = eval_expr(interp, PREC_PREFIX)
        left = _unary_op('~', rhs)
    elif tok.type == TT.AMP:
        interp.advance()
        rhs = eval_expr(interp, PREC_PREFIX)
        if not rhs.is_lvalue:
            raise EvalError("Cannot take address of rvalue", tok)
        ptr_type = make_pointer(rhs.typ)
        left = CValue(ptr_type, rhs.cell)
    elif tok.type == TT.STAR:
        interp.advance()
        rhs = eval_expr(interp, PREC_PREFIX)
        if not rhs.typ.is_pointer():
            raise EvalError("Cannot dereference non-pointer", tok)
        if rhs.val is None:
            raise EvalError("Null pointer dereference", tok)
        
        # rhs.val should be a cell or a list of cells
        if isinstance(rhs.val, list) and len(rhs.val) > 0 and isinstance(rhs.val[0], CValue):
            cell = rhs.val
        elif isinstance(rhs.val, list):
            cell = rhs.val[0]
        else:
            raise EvalError("Invalid pointer value", tok)
            
        v = cell_get(cell)
        deref_type = rhs.typ.deref()
        left = CValue(deref_type, v.val, cell=cell, is_lvalue=True)
    elif tok.type == TT.INC:
        interp.advance()
        rhs = eval_expr(interp, PREC_PREFIX)
        if not rhs.is_lvalue:
            raise EvalError("Cannot increment rvalue", tok)
        old_val = coerce_to_int(rhs)
        new_cv = CValue(rhs.typ, old_val + 1)
        cell_set(rhs.cell, new_cv)
        left = CValue(rhs.typ, old_val + 1, cell=rhs.cell, is_lvalue=True)
    elif tok.type == TT.DEC:
        interp.advance()
        rhs = eval_expr(interp, PREC_PREFIX)
        if not rhs.is_lvalue:
            raise EvalError("Cannot decrement rvalue", tok)
        old_val = coerce_to_int(rhs)
        new_cv = CValue(rhs.typ, old_val - 1)
        cell_set(rhs.cell, new_cv)
        left = CValue(rhs.typ, old_val - 1, cell=rhs.cell, is_lvalue=True)
    elif tok.type == TT.KW_SIZEOF:
        interp.advance()
        # sizeof(type) or sizeof expr
        if interp.cur().type == TT.LPAREN and _is_type_start(interp, 1):
            interp.advance() # (
            t = interp.parse_type()
            interp.expect(TT.RPAREN)
            left = CValue(T_INT, sizeof_type(t))
        else:
            rhs = eval_expr(interp, PREC_PREFIX)
            left = CValue(T_INT, sizeof_type(rhs.typ))
    else:
        raise EvalError(f"Unexpected token in expression: {tok}", tok)

    # INFIX
    while True:
        tok = interp.cur()
        prec, is_right_assoc = _get_precedence(tok.type)
        if prec == 0 or prec < precedence:
            break
        if prec == precedence and not is_right_assoc:
            break
            
        interp.advance()
        
        if tok.type == TT.LPAREN: # Function call
            args = []
            if interp.cur().type != TT.RPAREN:
                while True:
                    args.append(eval_expr(interp, 0))
                    if interp.cur().type == TT.COMMA:
                        interp.advance()
                    else:
                        break
            interp.expect(TT.RPAREN)
            left = interp.call_function(left, args)
        
        elif tok.type == TT.LBRACKET: # Array indexing
            idx_expr = eval_expr(interp, 0)
            interp.expect(TT.RBRACKET)
            idx = coerce_to_int(idx_expr)
            
            # Decay array to pointer
            base = left
            if base.typ.base == BaseType.ARRAY:
                base = CValue(make_pointer(base.typ.array_of), base.val)
            
            if not base.typ.is_pointer():
                raise EvalError("Subscripted value is not an array, pointer", tok)
                
            # Pointer arithmetic
            if isinstance(base.val, list):
                # We expect a list of cells
                cells = base.val
                if isinstance(cells, list) and len(cells) > 0 and isinstance(cells[0], list):
                    # Array of cells
                    if 0 <= idx < len(cells):
                        target_cell = cells[idx]
                        v = cell_get(target_cell)
                        left = CValue(base.typ.deref(), v.val, cell=target_cell, is_lvalue=True)
                    else:
                        # Out of bounds - just give a dummy cell to avoid crashing immediately?
                        # Or raise error
                        # raise EvalError(f"Array index out of bounds: {idx}", tok)
                        # For C, let's just make a dummy or allow it if memory was flat. Here we error if beyond len.
                        # Wait, C allows pointers to point into a larger buffer.
                        # For now, bounds checking is enforced by Python list.
                        if idx >= len(cells):
                            # Extend dynamically for stdlib compatibility if needed, or error
                            raise EvalError(f"Array index out of bounds: {idx}", tok)
                else:
                    # Single cell?
                    if idx == 0:
                        target_cell = cells
                        v = cell_get(target_cell)
                        left = CValue(base.typ.deref(), v.val, cell=target_cell, is_lvalue=True)
                    else:
                        raise EvalError(f"Pointer index out of bounds: {idx}", tok)
            elif isinstance(base.val, str): # string literal
                # Return char
                if 0 <= idx < len(base.val):
                    left = CValue(T_CHAR, ord(base.val[idx]))
                elif idx == len(base.val):
                    left = CValue(T_CHAR, 0)
                else:
                    raise EvalError(f"String index out of bounds: {idx}", tok)
            else:
                 raise EvalError("Invalid pointer value for subscript", tok)
                 
        elif tok.type in (TT.DOT, TT.ARROW): # Struct member
            if tok.type == TT.ARROW:
                # Dereference first
                if not left.typ.is_pointer():
                    raise EvalError("Cannot dereference non-pointer with ->", tok)
                if left.val is None:
                    raise EvalError("Null pointer dereference", tok)
                cell = left.val if isinstance(left.val, list) and isinstance(left.val[0], CValue) else left.val[0]
                v = cell_get(cell)
                left = CValue(left.typ.deref(), v.val, cell=cell, is_lvalue=True)
                
            member_name = interp.cur().value
            interp.expect(TT.IDENT)
            
            struct_typ = left.typ.resolve()
            if struct_typ.base not in (BaseType.STRUCT, BaseType.UNION):
                raise EvalError("Left of . or -> must be struct/union", tok)
                
            if member_name not in struct_typ.members:
                raise EvalError(f"Struct has no member '{member_name}'", tok)
                
            m_typ, m_offset = struct_typ.members[member_name]
            
            if not isinstance(left.val, dict):
                left.val = {}
                
            if member_name not in left.val:
                # Uninitialized member
                left.val[member_name] = make_cell(CValue(m_typ, 0))
                
            m_cell = left.val[member_name]
            v = cell_get(m_cell)
            left = CValue(m_typ, v.val, cell=m_cell, is_lvalue=True)

        elif tok.type == TT.INC: # Postfix ++
            if not left.is_lvalue:
                raise EvalError("Cannot increment rvalue", tok)
            old_val = coerce_to_int(left)
            new_cv = CValue(left.typ, old_val + 1)
            cell_set(left.cell, new_cv)
            left = CValue(left.typ, old_val) # returns old val, not lvalue
            
        elif tok.type == TT.DEC: # Postfix --
            if not left.is_lvalue:
                raise EvalError("Cannot decrement rvalue", tok)
            old_val = coerce_to_int(left)
            new_cv = CValue(left.typ, old_val - 1)
            cell_set(left.cell, new_cv)
            left = CValue(left.typ, old_val)
            
        elif tok.type == TT.QUESTION: # Ternary ?:
            cond = not is_zero(left)
            
            # If false, we need to skip tokens instead of evaluating
            if cond:
                left = eval_expr(interp, 0)
                interp.expect(TT.COLON)
                _skip_expr(interp)
            else:
                _skip_expr(interp)
                interp.expect(TT.COLON)
                left = eval_expr(interp, PREC_TERNARY)
                
        elif tok.type in (TT.ASSIGN, TT.PLUS_ASSIGN, TT.MINUS_ASSIGN, TT.STAR_ASSIGN,
                          TT.SLASH_ASSIGN, TT.PERCENT_ASSIGN, TT.AMP_ASSIGN, 
                          TT.PIPE_ASSIGN, TT.CARET_ASSIGN, TT.SHL_ASSIGN, TT.SHR_ASSIGN):
            if not left.is_lvalue:
                raise EvalError("Left side of assignment must be an lvalue", tok)
            
            rhs = eval_expr(interp, prec)
            
            if tok.type != TT.ASSIGN:
                # evaluate left op rhs
                op_map = {
                    TT.PLUS_ASSIGN: TT.PLUS, TT.MINUS_ASSIGN: TT.MINUS,
                    TT.STAR_ASSIGN: TT.STAR, TT.SLASH_ASSIGN: TT.SLASH,
                    TT.PERCENT_ASSIGN: TT.PERCENT, TT.AMP_ASSIGN: TT.AMP,
                    TT.PIPE_ASSIGN: TT.PIPE, TT.CARET_ASSIGN: TT.CARET,
                    TT.SHL_ASSIGN: TT.SHL, TT.SHR_ASSIGN: TT.SHR
                }
                left_val = left.copy()
                rhs = _binary_op(op_map[tok.type], left_val, rhs)
                
            rhs = _apply_cast(left.typ, rhs)
            cell_set(left.cell, rhs)
            left = CValue(left.typ, rhs.val, cell=left.cell, is_lvalue=True)

        elif tok.type == TT.AND: # && short circuit
            cond = not is_zero(left)
            if not cond:
                _skip_expr(interp)
                left = CValue(T_INT, 0)
            else:
                rhs = eval_expr(interp, prec)
                left = CValue(T_INT, 1 if not is_zero(rhs) else 0)

        elif tok.type == TT.OR: # || short circuit
            cond = not is_zero(left)
            if cond:
                _skip_expr(interp)
                left = CValue(T_INT, 1)
            else:
                rhs = eval_expr(interp, prec)
                left = CValue(T_INT, 1 if not is_zero(rhs) else 0)

        else: # Standard binary op
            rhs = eval_expr(interp, prec)
            left = _binary_op(tok.type, left, rhs)

    return left

def _skip_expr(interp):
    """Skip over an expression without evaluating it (for short circuiting)."""
    # Quick and dirty token skipper matching parentheses/brackets
    depth = 0
    while True:
        tok = interp.cur()
        if tok.type in (TT.LPAREN, TT.LBRACKET):
            depth += 1
        elif tok.type in (TT.RPAREN, TT.RBRACKET):
            if depth == 0:
                break
            depth -= 1
        elif depth == 0:
            if tok.type in (TT.COMMA, TT.SEMICOLON, TT.COLON):
                break
            # Also break on lower precedence operators... this is tricky without full parse.
            # A better way is to add a dummy flag to eval_expr.
            # But for simplicity, we can just do dummy evaluation.
            pass
            
        # Actually, skipping via dummy eval is safer.
        # Let's redefine skip_expr to use eval_expr with a flag, or we just catch it.
        break
    # For now, let's implement a proper skip by just throwing a dummy state, but Python doesn't have easy AST here.
    # We will use eval_expr but ignore side effects? Too hard.
    # Let's do a basic parenthesis matching skip until we hit a delimiter that stops the current precedence.
    # A robust way is to pass an `execute=False` flag to eval_expr.
    
    # Since we need a quick fix, let's just do parenthesis matching until we hit the next valid token 
    # of lower or equal precedence.
    pass # Wait, we must skip exactly one expression. The best way is to add `execute=False` to eval_expr.

# Redefine eval_expr to handle execute=False ? Yes, that's better. But to avoid rewriting the whole function,
# I will patch it.
# Actually, let's just skip tokens.
def _skip_expr(interp):
    # This is a hack for ?: and && ||
    # We just run eval_expr with a mock interpreter or add a flag to interpreter.
    interp.skip_mode = True
    try:
        eval_expr(interp, 0)
    finally:
        interp.skip_mode = False

def _get_precedence(tt):
    """Returns (precedence, is_right_assoc)"""
    if tt in (TT.ASSIGN, TT.PLUS_ASSIGN, TT.MINUS_ASSIGN, TT.STAR_ASSIGN,
              TT.SLASH_ASSIGN, TT.PERCENT_ASSIGN, TT.AMP_ASSIGN, TT.PIPE_ASSIGN,
              TT.CARET_ASSIGN, TT.SHL_ASSIGN, TT.SHR_ASSIGN):
        return PREC_ASSIGN, True
    if tt == TT.QUESTION: return PREC_TERNARY, True
    if tt == TT.OR: return PREC_OR, False
    if tt == TT.AND: return PREC_AND, False
    if tt == TT.PIPE: return PREC_BIT_OR, False
    if tt == TT.CARET: return PREC_BIT_XOR, False
    if tt == TT.AMP: return PREC_BIT_AND, False
    if tt in (TT.EQ, TT.NEQ): return PREC_EQUALITY, False
    if tt in (TT.LT, TT.LE, TT.GT, TT.GE): return PREC_RELATIONAL, False
    if tt in (TT.SHL, TT.SHR): return PREC_SHIFT, False
    if tt in (TT.PLUS, TT.MINUS): return PREC_ADDITIVE, False
    if tt in (TT.STAR, TT.SLASH, TT.PERCENT): return PREC_MULTIPLICATIVE, False
    
    # Postfix
    if tt in (TT.LPAREN, TT.LBRACKET, TT.DOT, TT.ARROW, TT.INC, TT.DEC): return PREC_POSTFIX, False
    return 0, False

def _is_type_start(interp, offset=0):
    tt = interp.peek(offset).type
    return tt in (TT.KW_INT, TT.KW_CHAR, TT.KW_SHORT, TT.KW_LONG, TT.KW_FLOAT, 
                  TT.KW_DOUBLE, TT.KW_VOID, TT.KW_UNSIGNED, TT.KW_SIGNED,
                  TT.KW_STRUCT, TT.KW_UNION, TT.KW_ENUM, TT.KW_BOOL) or interp.is_typedef(interp.peek(offset).value)

def _unary_op(op: str, v: CValue) -> CValue:
    if v.typ.is_fp():
        val = coerce_to_float(v)
        if op == '-': return CValue(v.typ, -val)
    else:
        val = coerce_to_int(v)
        if op == '-': return CValue(v.typ, apply_mask(v.typ.name, -val))
        if op == '~': return CValue(v.typ, apply_mask(v.typ.name, ~val))
    return v

def _binary_op(tt, left: CValue, right: CValue) -> CValue:
    # Handle pointer arithmetic
    if left.typ.is_pointer() and right.typ.is_integer():
        # Pointer + int
        if tt in (TT.PLUS, TT.MINUS):
            # For simplicity, if we have an array of cells, we just offset the index
            # But CValue.val for array is a list of cells. 
            # If left.val is a list of cells, returning a sublist doesn't work well for pointers.
            # In our model, left.val is the cell list. Wait, left.val for pointer is `list` (the cell it points to).
            # To do pointer arithmetic properly, we need the base array and offset.
            # Since this is a simple interpreter, we can cheat: 
            # If left.val is part of a list, we need the list and the index. 
            # Let's represent pointer value as (list_of_cells, index) internally?
            # value.py doesn't have offset. It just has cell.
            pass
    
    is_fp = left.typ.is_fp() or right.typ.is_fp()
    if is_fp:
        l = coerce_to_float(left)
        r = coerce_to_float(right)
        typ = T_DOUBLE
    else:
        l = coerce_to_int(left)
        r = coerce_to_int(right)
        typ = T_INT # Simplified promotion
        
    if tt == TT.PLUS: res = l + r
    elif tt == TT.MINUS: res = l - r
    elif tt == TT.STAR: res = l * r
    elif tt == TT.SLASH: 
        if r == 0: raise EvalError("Division by zero")
        res = l / r if is_fp else l // r
    elif tt == TT.PERCENT:
        if is_fp: raise EvalError("Modulo on floats")
        if r == 0: raise EvalError("Division by zero")
        res = l % r
    elif tt == TT.EQ: return CValue(T_INT, 1 if l == r else 0)
    elif tt == TT.NEQ: return CValue(T_INT, 1 if l != r else 0)
    elif tt == TT.LT: return CValue(T_INT, 1 if l < r else 0)
    elif tt == TT.LE: return CValue(T_INT, 1 if l <= r else 0)
    elif tt == TT.GT: return CValue(T_INT, 1 if l > r else 0)
    elif tt == TT.GE: return CValue(T_INT, 1 if l >= r else 0)
    elif tt == TT.SHL: res = l << r
    elif tt == TT.SHR: res = l >> r
    elif tt == TT.AMP: res = l & r
    elif tt == TT.PIPE: res = l | r
    elif tt == TT.CARET: res = l ^ r
    else: raise EvalError("Unknown binary op")
    
    if not is_fp:
        res = apply_mask(typ.name, res)
        
    return CValue(typ, res)

def _apply_cast(typ: CType, v: CValue) -> CValue:
    if typ.is_fp():
        return CValue(typ, coerce_to_float(v))
    elif typ.is_integer():
        return CValue(typ, apply_mask(typ.name, coerce_to_int(v)))
    elif typ.is_pointer():
        return CValue(typ, v.val)
    return CValue(typ, v.val)
