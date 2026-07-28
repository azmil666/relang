# Wren (Go)

A Go (Golang) reimplementation of the Wren programming language interpreter, migrated from the original C implementation as part of the Relang language migration project.

## Overview

This project aims to recreate the core functionality of the Wren language in pure Go while preserving the original language semantics as closely as possible.

The implementation follows a compiler and virtual machine architecture:

```
Source Code (.wren)
        ↓
Lexer
        ↓
Parser
        ↓
Compiler
        ↓
Bytecode
        ↓
Virtual Machine
        ↓
Runtime
```

## Features

- Lexer for Wren source code
- Pratt parser
- Bytecode compiler
- Stack-based virtual machine
- Runtime object system
- Classes and instances
- Functions and closures
- Variables and scopes
- Arithmetic and logical expressions
- Control flow
  - if / else
  - while
  - for
  - break
  - continue
- Module loading support
- Basic standard library
- Command-line execution

## Project Structure

```
target/
├── ast/
├── bytecode/
├── compiler/
├── core/
├── lexer/
├── parser/
├── runtime/
├── vm/
├── main.go
└── go.mod
```

## Building

From the `target` directory:

```bash
go build -o wren .
```

On Windows:

```powershell
go build -o wren.exe .
```

## Running

Execute a Wren program:

```bash
./wren example.wren
```

or on Windows:

```powershell
.\wren.exe example.wren
```

Display help:

```bash
./wren --help
```

Display version:

```bash
./wren --version
```

## Validation

The implementation can be validated using the Relang test suite.

From the `relang` directory:

```bash
python validate.py "../target/wren.exe"
```

## Current Status

This is a partial but functional Go implementation of the Wren interpreter.

Implemented components include:

- Lexical analysis
- Parsing
- Bytecode generation
- Virtual machine execution
- Core runtime
- Object-oriented features
- Basic collections
- Module loading
- Error handling
- Command-line interface

Some advanced runtime features and portions of the standard library are still incomplete.

## Technology

- Go (Golang)
- Bytecode Virtual Machine
- Pratt Parser
- Stack-based Execution Model

## Acknowledgements

This project is based on the original Wren programming language and was developed as part of the Relang language migration project, reimplementing the interpreter from C to Go.