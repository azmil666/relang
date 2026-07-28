# PicoC Python Interpreter

This is a clean, dependency-free Python implementation of the PicoC C interpreter.

## Building / Setup
No build step is required, as the implementation is purely in Python using the standard library.
Requires Python 3.7 or newer.

## Running
Execute a C source file using the Python interpreter:

```bash
python picoc.py <source_file.c>
```

You can also pass arguments to the script, though full `argv` mapping is simplified.

## Implementation Status
- **Lexer**: Complete (all C tokens, strings, chars, numbers).
- **Preprocessor**: Implemented (`#define`, `#if`, `#include` stubbed).
- **Type System**: Fully modeled (`CType`), handling alignment, structs, arrays, and pointers.
- **Memory Model**: Cell-based memory (`[CValue]`) to simulate C LValues and pointers natively in Python.
- **Parser & Evaluator**: Direct AST-less execution with Pratt expression parsing.
- **Standard Library**:
  - `<stdio.h>`: Byte-identical `printf` via custom formatter.
  - `<stdlib.h>`, `<string.h>`, `<math.h>`, `<ctype.h>`, `<stdbool.h>` partial support sufficient for standard PicoC programs.
