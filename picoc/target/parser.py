"""
parser.py — Direct-execution parser and control-flow runner for PicoC.
"""
from typing import List, Dict, Optional
from lexer import TT, Token
from picoc_types import (BaseType, CType, PRIMITIVE_TYPES, T_INT, T_VOID, 
                         make_pointer, make_array, make_struct, make_union, make_enum, make_function, sizeof_type)
from value import CValue, make_cell, cell_get, cell_set, coerce_to_int, is_zero
from scope import CallStack
from expression import eval_expr, EvalError

class Interpreter:
    def __init__(self, tokens: List[Token], call_stack: CallStack):
        self.tokens = tokens
        self.call_stack = call_stack
        self.idx = 0
        self.typedefs: Dict[str, CType] = {}
        self.structs: Dict[str, CType] = {}
        self.unions: Dict[str, CType] = {}
        self.enums: Dict[str, CType] = {}
        self.skip_mode = False

    def cur(self) -> Token:
        if self.idx < len(self.tokens):
            return self.tokens[self.idx]
        return self.tokens[-1] # EOF

    def peek(self, offset=1) -> Token:
        pos = self.idx + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return self.tokens[-1]

    def advance(self) -> Token:
        tok = self.cur()
        if self.idx < len(self.tokens) - 1:
            self.idx += 1
        return tok

    def expect(self, tt: TT) -> Token:
        tok = self.cur()
        if tok.type != tt:
            raise EvalError(f"Expected {tt.name}, got {tok.type.name}", tok)
        return self.advance()
        
    def is_typedef(self, name: str) -> bool:
        return name in self.typedefs

    def parse_type(self) -> CType:
        """Parse a C type declaration (e.g. `int *`, `struct foo`)."""
        tok = self.cur()
        base_typ = None
        
        # Modifiers
        is_unsigned = False
        is_const = False
        
        while self.cur().type in (TT.KW_UNSIGNED, TT.KW_SIGNED, TT.KW_CONST):
            if self.cur().type == TT.KW_UNSIGNED: is_unsigned = True
            if self.cur().type == TT.KW_CONST: is_const = True
            self.advance()
            
        tok = self.cur()
        if tok.type in (TT.KW_INT, TT.KW_CHAR, TT.KW_SHORT, TT.KW_LONG, TT.KW_FLOAT, TT.KW_DOUBLE, TT.KW_VOID, TT.KW_BOOL):
            name = tok.value
            if is_unsigned and name == 'int': name = 'unsigned int'
            elif is_unsigned and name == 'char': name = 'unsigned char'
            elif is_unsigned and name == 'short': name = 'unsigned short'
            elif is_unsigned and name == 'long': name = 'unsigned long'
            base_typ = PRIMITIVE_TYPES.get(name, T_INT)
            self.advance()
        elif tok.type == TT.KW_STRUCT:
            self.advance()
            tag = self.cur().value if self.cur().type == TT.IDENT else ""
            if tag: self.advance()
            # We don't support defining structs inside type parsing easily here, just lookup
            if tag in self.structs:
                base_typ = self.structs[tag]
            else:
                base_typ = CType(BaseType.STRUCT, f"struct {tag}") # incomplete
        elif tok.type == TT.KW_UNION:
            self.advance()
            tag = self.cur().value
            self.advance()
            base_typ = self.unions.get(tag, CType(BaseType.UNION, f"union {tag}"))
        elif tok.type == TT.KW_ENUM:
            self.advance()
            tag = self.cur().value
            self.advance()
            base_typ = self.enums.get(tag, CType(BaseType.ENUM, f"enum {tag}"))
        elif tok.type == TT.IDENT and self.is_typedef(tok.value):
            base_typ = self.typedefs[tok.value]
            self.advance()
        elif is_unsigned:
            base_typ = PRIMITIVE_TYPES['unsigned int']
        else:
            base_typ = T_INT # Default to int
            
        # Pointers
        while self.cur().type == TT.STAR:
            self.advance()
            base_typ = make_pointer(base_typ)
            
        return base_typ

    def parse_declaration(self, is_global=False):
        """Parse variables, functions, typedefs, struct definitions."""
        tok = self.cur()
        if tok.type == TT.KW_TYPEDEF:
            self.advance()
            typ = self.parse_type()
            name = self.expect(TT.IDENT).value
            self.typedefs[name] = typ
            self.expect(TT.SEMICOLON)
            return
            
        if tok.type in (TT.KW_STRUCT, TT.KW_UNION, TT.KW_ENUM) and self.peek(1).type == TT.IDENT and self.peek(2).type == TT.LBRACE:
            # Struct/Union/Enum definition
            is_struct = tok.type == TT.KW_STRUCT
            is_union = tok.type == TT.KW_UNION
            self.advance()
            tag = self.expect(TT.IDENT).value
            self.expect(TT.LBRACE)
            
            if is_struct or is_union:
                members = []
                while self.cur().type != TT.RBRACE:
                    m_typ = self.parse_type()
                    m_name = self.expect(TT.IDENT).value
                    # Arrays in structs
                    if self.cur().type == TT.LBRACKET:
                        self.advance()
                        size = self.expect(TT.INT_LIT).value[0]
                        self.expect(TT.RBRACKET)
                        m_typ = make_array(m_typ, size)
                    members.append((m_name, m_typ))
                    self.expect(TT.SEMICOLON)
                self.expect(TT.RBRACE)
                self.expect(TT.SEMICOLON)
                if is_struct:
                    self.structs[tag] = make_struct(tag, members)
                else:
                    self.unions[tag] = make_union(tag, members)
            else:
                # Enum
                val = 0
                while self.cur().type != TT.RBRACE:
                    e_name = self.expect(TT.IDENT).value
                    if self.cur().type == TT.ASSIGN:
                        self.advance()
                        v_expr = eval_expr(self, 0)
                        val = coerce_to_int(v_expr)
                    
                    e_cv = CValue(T_INT, val)
                    self.call_stack.define_global(e_name, make_cell(e_cv))
                    val += 1
                    
                    if self.cur().type == TT.COMMA:
                        self.advance()
                self.expect(TT.RBRACE)
                self.expect(TT.SEMICOLON)
                self.enums[tag] = make_enum(tag)
            return

        typ = self.parse_type()
        
        while True:
            # Could be just a struct def without variables `struct S { int x; };`
            if self.cur().type == TT.SEMICOLON:
                self.advance()
                return
                
            name = self.expect(TT.IDENT).value
            
            # Array?
            if self.cur().type == TT.LBRACKET:
                self.advance()
                size = 0
                if self.cur().type != TT.RBRACKET:
                    size_expr = eval_expr(self, 0)
                    size = coerce_to_int(size_expr)
                self.expect(TT.RBRACKET)
                typ = make_array(typ, size)
            
            # Function?
            if self.cur().type == TT.LPAREN:
                self.advance()
                params = []
                param_names = []
                while self.cur().type != TT.RPAREN:
                    if self.cur().type == TT.ELLIPSIS:
                        self.advance()
                        break
                    p_typ = self.parse_type()
                    p_name = self.expect(TT.IDENT).value if self.cur().type == TT.IDENT else ""
                    # Array param decays to pointer
                    if self.cur().type == TT.LBRACKET:
                        self.advance()
                        # size optional
                        if self.cur().type != TT.RBRACKET:
                            eval_expr(self, 0) # ignore
                        self.expect(TT.RBRACKET)
                        p_typ = make_pointer(p_typ)
                    params.append(p_typ)
                    param_names.append(p_name)
                    if self.cur().type == TT.COMMA:
                        self.advance()
                self.expect(TT.RPAREN)
                
                func_typ = make_function(typ, params)
                
                if self.cur().type == TT.LBRACE:
                    # Function definition
                    func_val = CValue(func_typ, {'idx': self.idx, 'params': param_names, 'types': params})
                    self.call_stack.define_global(name, make_cell(func_val))
                    self._skip_block()
                    return # Only one function def at a time
                else:
                    # Function prototype
                    func_val = CValue(func_typ, None)
                    self.call_stack.define_global(name, make_cell(func_val))
            else:
                # Variable
                val = CValue(typ, 0)
                if self.cur().type == TT.ASSIGN:
                    self.advance()
                    init_val = eval_expr(self, 0)
                    val = CValue(typ, init_val.val) # Apply coercion in a real compiler
                    
                if is_global:
                    self.call_stack.define_global(name, make_cell(val))
                else:
                    self.call_stack.define_var(name, make_cell(val))
                    
            if self.cur().type == TT.COMMA:
                self.advance()
            else:
                self.expect(TT.SEMICOLON)
                break

    def _skip_block(self):
        depth = 0
        while self.idx < len(self.tokens):
            if self.cur().type == TT.LBRACE: depth += 1
            elif self.cur().type == TT.RBRACE:
                depth -= 1
                if depth == 0:
                    self.advance()
                    return
            self.advance()

    def parse_statement(self):
        if self.skip_mode:
            return self._skip_statement()
            
        tok = self.cur()
        
        if tok.type == TT.LBRACE:
            self.advance()
            outer = self.call_stack.current_scope
            self.call_stack.push_block_scope()
            while self.cur().type != TT.RBRACE and not self.call_stack.is_interrupted():
                self.parse_statement()
            
            if self.call_stack.is_interrupted():
                # Fast forward to end of block
                self._skip_block_from_inside()
            else:
                self.expect(TT.RBRACE)
                
            self.call_stack.pop_block_scope(outer)
            return
            
        if tok.type in (TT.KW_INT, TT.KW_CHAR, TT.KW_SHORT, TT.KW_LONG, TT.KW_FLOAT, 
                        TT.KW_DOUBLE, TT.KW_VOID, TT.KW_UNSIGNED, TT.KW_SIGNED,
                        TT.KW_STRUCT, TT.KW_UNION, TT.KW_ENUM, TT.KW_BOOL, TT.KW_TYPEDEF) or self.is_typedef(tok.value):
            self.parse_declaration(is_global=False)
            return

        if tok.type == TT.KW_IF:
            self.advance()
            self.expect(TT.LPAREN)
            cond = eval_expr(self, 0)
            self.expect(TT.RPAREN)
            
            if not is_zero(cond):
                self.parse_statement()
                if self.cur().type == TT.KW_ELSE:
                    self.advance()
                    self.skip_mode = True
                    self.parse_statement()
                    self.skip_mode = False
            else:
                self.skip_mode = True
                self.parse_statement()
                self.skip_mode = False
                if self.cur().type == TT.KW_ELSE:
                    self.advance()
                    self.parse_statement()
            return
            
        if tok.type == TT.KW_WHILE:
            self.advance()
            self.expect(TT.LPAREN)
            cond_idx = self.idx
            
            while True:
                self.idx = cond_idx
                cond = eval_expr(self, 0)
                self.expect(TT.RPAREN)
                
                if is_zero(cond):
                    self.skip_mode = True
                    self.parse_statement()
                    self.skip_mode = False
                    break
                    
                body_idx = self.idx
                self.parse_statement()
                
                if self.call_stack.is_breaking():
                    self.call_stack.clear_break()
                    break
                if self.call_stack.is_continuing():
                    self.call_stack.clear_continue()
                if self.call_stack.is_returning():
                    break
            return

        if tok.type == TT.KW_FOR:
            self.advance()
            self.expect(TT.LPAREN)
            
            outer = self.call_stack.current_scope
            self.call_stack.push_block_scope()
            
            # Init
            if self.cur().type != TT.SEMICOLON:
                if self.cur().type in (TT.KW_INT, TT.KW_CHAR) or self.is_typedef(self.cur().value):
                    self.parse_declaration(is_global=False)
                else:
                    eval_expr(self, 0)
                    self.expect(TT.SEMICOLON)
            else:
                self.advance()
                
            cond_idx = self.idx
            
            while True:
                self.idx = cond_idx
                cond = CValue(T_INT, 1)
                if self.cur().type != TT.SEMICOLON:
                    cond = eval_expr(self, 0)
                self.expect(TT.SEMICOLON)
                
                inc_idx = self.idx
                # Skip inc to reach body
                self.skip_mode = True
                if self.cur().type != TT.RPAREN:
                    eval_expr(self, 0)
                self.skip_mode = False
                self.expect(TT.RPAREN)
                
                if is_zero(cond):
                    self.skip_mode = True
                    self.parse_statement()
                    self.skip_mode = False
                    break
                    
                self.parse_statement()
                
                if self.call_stack.is_breaking():
                    self.call_stack.clear_break()
                    break
                if self.call_stack.is_returning():
                    break
                    
                self.call_stack.clear_continue()
                
                # Do increment
                if self.tokens[inc_idx].type != TT.RPAREN:
                    old_idx = self.idx
                    self.idx = inc_idx
                    eval_expr(self, 0)
                    self.idx = old_idx
                    
            self.call_stack.pop_block_scope(outer)
            return

        if tok.type == TT.KW_RETURN:
            self.advance()
            val = None
            if self.cur().type != TT.SEMICOLON:
                val = eval_expr(self, 0)
            self.expect(TT.SEMICOLON)
            self.call_stack.signal_return(val)
            return
            
        if tok.type == TT.KW_BREAK:
            self.advance()
            self.expect(TT.SEMICOLON)
            self.call_stack.signal_break()
            return
            
        if tok.type == TT.KW_CONTINUE:
            self.advance()
            self.expect(TT.SEMICOLON)
            self.call_stack.signal_continue()
            return
            
        # Expression statement
        if tok.type != TT.SEMICOLON:
            eval_expr(self, 0)
        self.expect(TT.SEMICOLON)

    def _skip_statement(self):
        """Skip a single statement (could be a block) quickly."""
        if self.cur().type == TT.LBRACE:
            self._skip_block()
            return
            
        # Try to skip everything up to a semicolon that isn't nested in parens
        depth = 0
        while self.idx < len(self.tokens):
            t = self.cur().type
            if t in (TT.LPAREN, TT.LBRACKET): depth += 1
            elif t in (TT.RPAREN, TT.RBRACKET): depth -= 1
            elif t == TT.SEMICOLON and depth == 0:
                self.advance()
                return
            elif t == TT.LBRACE: # A block start inside if without braces? Just let _skip_block handle if we started with brace
                pass
            self.advance()

    def _skip_block_from_inside(self):
        depth = 1 # We are inside
        while self.idx < len(self.tokens):
            if self.cur().type == TT.LBRACE: depth += 1
            elif self.cur().type == TT.RBRACE:
                depth -= 1
                if depth == 0:
                    self.advance()
                    return
            self.advance()

    def call_function(self, func_cv: CValue, args: List[CValue]) -> CValue:
        val = func_cv.val
        if isinstance(val, str):
            # Native function
            # Look up in standard library wrappers mapping
            # (Handled globally or registered native funcs)
            return self._call_native(val, args)
            
        if not isinstance(val, dict) or 'idx' not in val:
            raise EvalError(f"Cannot call non-function")
            
        # User defined function
        old_idx = self.idx
        self.idx = val['idx']
        
        self.expect(TT.LBRACE)
        
        func_name = func_cv.typ.name
        self.call_stack.push_frame(func_name)
        
        # Bind args
        params = val['params']
        for i, p_name in enumerate(params):
            if p_name and i < len(args):
                self.call_stack.define_var(p_name, make_cell(args[i].copy()))
                
        # Run block
        outer = self.call_stack.current_scope
        self.call_stack.push_block_scope()
        while self.cur().type != TT.RBRACE and not self.call_stack.is_interrupted():
            self.parse_statement()
            
        ret_val = self.call_stack.pop_frame()
        self.idx = old_idx
        
        if ret_val is None:
            return CValue(T_VOID, None)
        return ret_val

    def _call_native(self, name: str, args: List[CValue]) -> CValue:
        """Call a standard library Python function."""
        # This will be populated by picoc.py
        if hasattr(self, 'native_functions') and name in self.native_functions:
            return self.native_functions[name](args)
        raise EvalError(f"Undefined native function '{name}'")
