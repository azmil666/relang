"""
picoc.py — Entrypoint for PicoC Python interpreter.
"""
import sys
import os
import argparse

sys.setrecursionlimit(50000)

from lexer import tokenize, TT, LexError
from preprocessor import Preprocessor
from parser import Interpreter
from scope import Scope, CallStack
from value import CValue, make_cell

# Stdlib
from stdlib.stdio import StdioLib
from stdlib.stdlib import StdlibLib
from stdlib.string import StringLib
from stdlib.math import MathLib
from stdlib.ctype import CtypeLib
from stdlib.stdbool import inject_stdbool
from picoc_types import T_INT, T_CHAR_PTR

def main():
    parser = argparse.ArgumentParser(description="PicoC Python Interpreter")
    parser.add_argument("file", help="C source file to execute")
    parser.add_argument("-s", action="store_true", help="Unused (legacy arg)")
    parser.add_argument("-i", action="store_true", help="Unused (legacy arg)")
    parser.add_argument("-c", action="store_true", help="Unused (legacy arg)")
    # accept extra args for the interpreted program
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments to pass to the C program")
    
    args = parser.parse_args()
    
    try:
        with open(args.file, 'r') as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Error: file '{args.file}' not found.")
        sys.exit(1)
        
    # 1. Preprocess
    pp = Preprocessor()
    try:
        processed_source = pp.process(source, args.file)
    except Exception as e:
        print(f"Preprocessor error: {e}")
        sys.exit(1)
        
    # 2. Tokenize
    try:
        tokens = tokenize(processed_source, args.file)
    except LexError as e:
        print(e)
        sys.exit(1)
        
    # 3. Setup Scope & CallStack
    global_scope = Scope('<global>')
    call_stack = CallStack(global_scope)
    
    # 4. Initialize Interpreter
    interp = Interpreter(tokens, call_stack)
    
    # 5. Inject Standard Libraries
    native_funcs = {}
    
    def register_lib(lib_class):
        lib_inst = lib_class(interp)
        funcs = lib_inst.get_functions()
        for name, func in funcs.items():
            native_funcs[name] = func
            # Define as function prototype in global scope
            # We just need it to be identifiable as a native func (val=name)
            # from picoc_types import make_function, T_VOID
            # For simplicity, we just use string as value
            from picoc_types import CType, BaseType
            f_typ = CType(BaseType.FUNCTION, f"fn_{name}")
            cv = CValue(f_typ, name)
            call_stack.define_global(name, make_cell(cv))
            
    register_lib(StdioLib)
    register_lib(StdlibLib)
    register_lib(StringLib)
    register_lib(MathLib)
    register_lib(CtypeLib)
    inject_stdbool(interp)
    
    interp.native_functions = native_funcs
    
    # 6. Global Parse
    try:
        while interp.cur().type != TT.EOF:
            interp.parse_declaration(is_global=True)
    except Exception as e:
        print(f"Runtime error during global parse: {e}")
        sys.exit(1)
        
    # 7. Execute main()
    main_func = call_stack.lookup_global('main')
    if not main_func:
        print("Error: main() not defined")
        sys.exit(1)
        
    # Set up argc, argv
    # argc = 1 + len(args.args)
    # argv = [args.file] + args.args
    # Simplification: just pass 0, NULL
    
    try:
        ret_val = interp.call_function(main_func[0], [CValue(T_INT, 0), CValue(T_CHAR_PTR, None)])
        ret_code = ret_val.val if ret_val.val is not None else 0
        sys.exit(int(ret_code))
    except Exception as e:
        print(f"Runtime error during execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
