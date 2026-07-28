package compiler

import (
	"fmt"
	"wren/ast"
	"wren/bytecode"
	"wren/runtime"
)

type LoopInfo struct {
	Start            int
	Body             int
	ExitJumps        []int
	ContinueJumps    []int
	EnclosingScope   int
	EnclosingLoop    *LoopInfo
}

type Compiler struct {
	scope       *CompilerScope
	module      *runtime.ObjModule
	errors      []string
	currentLoop *LoopInfo
}

func NewCompiler(module *runtime.ObjModule) *Compiler {
	mainFn := runtime.NewObjFn("<script>", 0, module)
	scope := NewCompilerScope(nil, TypeScript, mainFn)
	return &Compiler{
		scope:       scope,
		module:      module,
		errors:      make([]string, 0),
		currentLoop: nil,
	}
}

func (c *Compiler) Compile(statements []ast.Stmt) (*runtime.ObjFn, error) {
	for _, stmt := range statements {
		c.compileStmt(stmt)
	}

	// Implicit return null at end of script
	c.emitOp(bytecode.OpNull, 1)
	c.emitOp(bytecode.OpReturn, 1)

	if len(c.errors) > 0 {
		return nil, fmt.Errorf("%s", c.errors[0])
	}
	return c.scope.Fn, nil
}

func (c *Compiler) compileStmt(stmt ast.Stmt) {
	if stmt == nil {
		return
	}
	switch s := stmt.(type) {
	case *ast.VarDeclStmt:
		c.compileVarDecl(s)
	case *ast.ExprStmt:
		c.compileExpr(s.Expression)
		c.emitOp(bytecode.OpPop, s.Line())
	case *ast.BlockStmt:
		c.beginScope()
		for _, nested := range s.Statements {
			c.compileStmt(nested)
		}
		c.endScope(s.Line())
	case *ast.IfStmt:
		c.compileIf(s)
	case *ast.WhileStmt:
		c.compileWhile(s)
	case *ast.ForStmt:
		c.compileFor(s)
	case *ast.ReturnStmt:
		c.compileReturn(s)
	case *ast.BreakStmt:
		if c.currentLoop == nil {
			c.errors = append(c.errors, "Cannot use 'break' outside of a loop.")
			return
		}
		// Close upvalues up to the loop's scope depth
		for i := len(c.scope.Locals) - 1; i >= 0 && c.scope.Locals[i].Depth > c.currentLoop.EnclosingScope; i-- {
			if c.scope.Locals[i].IsUpvalue {
				c.emitOp(bytecode.OpCloseUpvalue, s.Line())
			} else {
				c.emitOp(bytecode.OpPop, s.Line())
			}
		}
		jump := c.emitJump(bytecode.OpJump, s.Line())
		c.currentLoop.ExitJumps = append(c.currentLoop.ExitJumps, jump)

	case *ast.ContinueStmt:
		if c.currentLoop == nil {
			c.errors = append(c.errors, "Cannot use 'continue' outside of a loop.")
			return
		}
		// Close upvalues up to the loop's scope depth
		for i := len(c.scope.Locals) - 1; i >= 0 && c.scope.Locals[i].Depth > c.currentLoop.EnclosingScope; i-- {
			if c.scope.Locals[i].IsUpvalue {
				c.emitOp(bytecode.OpCloseUpvalue, s.Line())
			} else {
				c.emitOp(bytecode.OpPop, s.Line())
			}
		}
		// We jump forward to the continue target (which is loop condition or increment)
		jump := c.emitJump(bytecode.OpJump, s.Line())
		c.currentLoop.ContinueJumps = append(c.currentLoop.ContinueJumps, jump)
	case *ast.ClassDeclStmt:
		c.compileClassDecl(s)
	case *ast.ImportStmt:
		c.compileImport(s)
	}
}

func (c *Compiler) compileVarDecl(s *ast.VarDeclStmt) {
	if s.Initializer != nil {
		c.compileExpr(s.Initializer)
	} else {
		c.emitOp(bytecode.OpNull, s.Line())
	}

	if c.scope.ScopeDepth > 0 {
		c.scope.AddLocal(s.Name.Text)
	} else {
		idx := c.scope.Fn.Chunk.AddConstant(s.Name.Text)
		c.emitOp(bytecode.OpDefineGlobal, s.Line())
		c.emitByte(byte(idx), s.Line())
		if c.module != nil {
			c.module.Variables[s.Name.Text] = runtime.NullValue()
			c.module.VarNames = append(c.module.VarNames, s.Name.Text)
		}
	}
}

func (c *Compiler) compileIf(s *ast.IfStmt) {
	c.compileExpr(s.Condition)

	thenJump := c.emitJump(bytecode.OpJumpIfFalse, s.Line())
	c.emitOp(bytecode.OpPop, s.Line())

	c.compileStmt(s.ThenBranch)

	elseJump := c.emitJump(bytecode.OpJump, s.Line())
	c.patchJump(thenJump)
	c.emitOp(bytecode.OpPop, s.Line())

	if s.ElseBranch != nil {
		c.compileStmt(s.ElseBranch)
	}
	c.patchJump(elseJump)
}

func (c *Compiler) compileWhile(s *ast.WhileStmt) {
	loop := &LoopInfo{
		Start:          len(c.scope.Fn.Chunk.Code),
		EnclosingScope: c.scope.ScopeDepth,
		EnclosingLoop:  c.currentLoop,
		ContinueJumps:  make([]int, 0),
		ExitJumps:      make([]int, 0),
	}
	c.currentLoop = loop

	c.compileExpr(s.Condition)

	exitJump := c.emitJump(bytecode.OpJumpIfFalse, s.Line())
	c.emitOp(bytecode.OpPop, s.Line())

	c.compileStmt(s.Body)

	for _, jump := range loop.ContinueJumps {
		c.patchJump(jump)
	}

	c.emitLoop(loop.Start, s.Line())

	c.patchJump(exitJump)
	c.emitOp(bytecode.OpPop, s.Line())

	for _, jump := range loop.ExitJumps {
		c.patchJump(jump)
	}

	c.currentLoop = loop.EnclosingLoop
}

func (c *Compiler) compileFor(s *ast.ForStmt) {
	c.beginScope()
	c.compileExpr(s.Iterator)

	iterSlot := c.scope.AddLocal("<seq>")

	// Call iterate(null)
	c.emitOp(bytecode.OpGetLocal, s.Line())
	c.emitByte(byte(iterSlot), s.Line())
	c.emitOp(bytecode.OpNull, s.Line())
	c.emitCall("iterate(_)", 1, s.Line())

	seqIterSlot := c.scope.AddLocal("<iter>")

	loop := &LoopInfo{
		Start:          len(c.scope.Fn.Chunk.Code),
		EnclosingScope: c.scope.ScopeDepth,
		EnclosingLoop:  c.currentLoop,
		ContinueJumps:  make([]int, 0),
		ExitJumps:      make([]int, 0),
	}
	c.currentLoop = loop

	c.emitOp(bytecode.OpGetLocal, s.Line())
	c.emitByte(byte(seqIterSlot), s.Line())

	exitJump := c.emitJump(bytecode.OpJumpIfFalse, s.Line())
	c.emitOp(bytecode.OpPop, s.Line())

	// Var element = seq.iteratorValue(iter)
	c.emitOp(bytecode.OpGetLocal, s.Line())
	c.emitByte(byte(iterSlot), s.Line())
	c.emitOp(bytecode.OpGetLocal, s.Line())
	c.emitByte(byte(seqIterSlot), s.Line())
	c.emitCall("iteratorValue(_)", 1, s.Line())

	elemSlot := c.scope.AddLocal(s.Variable.Text)
	_ = elemSlot

	c.compileStmt(s.Body)

	// Patch continue jumps to jump to the increment phase
	for _, jump := range loop.ContinueJumps {
		c.patchJump(jump)
	}

	// Advance iter = seq.iterate(iter)
	c.emitOp(bytecode.OpGetLocal, s.Line())
	c.emitByte(byte(iterSlot), s.Line())
	c.emitOp(bytecode.OpGetLocal, s.Line())
	c.emitByte(byte(seqIterSlot), s.Line())
	c.emitCall("iterate(_)", 1, s.Line())
	c.emitOp(bytecode.OpSetLocal, s.Line())
	c.emitByte(byte(seqIterSlot), s.Line())
	c.emitOp(bytecode.OpPop, s.Line())

	c.emitLoop(loop.Start, s.Line())

	c.patchJump(exitJump)
	c.emitOp(bytecode.OpPop, s.Line())

	for _, jump := range loop.ExitJumps {
		c.patchJump(jump)
	}

	c.currentLoop = loop.EnclosingLoop
	c.endScope(s.Line())
}

func (c *Compiler) compileReturn(s *ast.ReturnStmt) {
	if s.Value != nil {
		c.compileExpr(s.Value)
	} else {
		c.emitOp(bytecode.OpNull, s.Line())
	}
	c.emitOp(bytecode.OpReturn, s.Line())
}

func (c *Compiler) compileClassDecl(s *ast.ClassDeclStmt) {
	idx := c.scope.Fn.Chunk.AddConstant(s.Name.Text)
	c.emitOp(bytecode.OpClass, s.Line())
	c.emitByte(byte(idx), s.Line())

	if s.Superclass != nil {
		c.compileExpr(s.Superclass)
		c.emitOp(bytecode.OpInherit, s.Line())
	}

	for _, method := range s.Methods {
		c.compileMethod(method, s.Name.Text)
	}

	if c.scope.ScopeDepth > 0 {
		c.scope.AddLocal(s.Name.Text)
	} else {
		c.emitOp(bytecode.OpDefineGlobal, s.Line())
		c.emitByte(byte(idx), s.Line())
	}
}

func (c *Compiler) compileMethod(m *ast.MethodDeclStmt, className string) {
	fn := runtime.NewObjFn(m.Name, len(m.Params), c.module)
	childScope := NewCompilerScope(c.scope, TypeMethod, fn)

	// Parameter stack slots
	for _, p := range m.Params {
		childScope.AddLocal(p)
	}

	oldScope := c.scope
	c.scope = childScope

	if m.IsConstruct {
		c.emitOp(bytecode.OpConstruct, m.LineNum)
	}

	for _, stmt := range m.Body {
		c.compileStmt(stmt)
	}
	if m.IsConstruct {
		c.emitOp(bytecode.OpGetLocal, m.LineNum)
		c.emitByte(0, m.LineNum) // Get 'this'
	} else {
		c.emitOp(bytecode.OpNull, m.LineNum)
	}
	c.emitOp(bytecode.OpReturn, m.LineNum)

	c.scope = oldScope

	idx := c.scope.Fn.Chunk.AddConstant(fn)
	c.emitOp(bytecode.OpConstant, m.LineNum)
	c.emitByte(byte(idx), m.LineNum)

	sig := m.Name
	if len(m.Params) > 0 {
		sig = fmt.Sprintf("%s(%s)", m.Name, buildArgSignature(len(m.Params)))
	}

	sigIdx := c.scope.Fn.Chunk.AddConstant(sig)
	c.emitOp(bytecode.OpMethod, m.LineNum)
	c.emitByte(byte(sigIdx), m.LineNum)
	if m.IsStatic || m.IsConstruct {
		c.emitByte(1, m.LineNum)
	} else {
		c.emitByte(0, m.LineNum)
	}
}

func (c *Compiler) compileImport(s *ast.ImportStmt) {
	pathIdx := c.scope.Fn.Chunk.AddConstant(s.Path.Text)
	c.emitOp(bytecode.OpImport, s.Line())
	c.emitByte(byte(pathIdx), s.Line())

	for _, symbol := range s.Symbols {
		c.emitOp(bytecode.OpDup, s.Line())
		symIdx := c.scope.Fn.Chunk.AddConstant(symbol.Name)
		c.emitOp(bytecode.OpGetGlobal, s.Line())
		c.emitByte(byte(symIdx), s.Line())

		if c.scope.ScopeDepth > 0 {
			c.scope.AddLocal(symbol.Alias)
		} else {
			aliasIdx := c.scope.Fn.Chunk.AddConstant(symbol.Alias)
			c.emitOp(bytecode.OpDefineGlobal, s.Line())
			c.emitByte(byte(aliasIdx), s.Line())
		}
	}
	c.emitOp(bytecode.OpPop, s.Line())
}

func (c *Compiler) compileExpr(expr ast.Expr) {
	if expr == nil {
		return
	}
	switch e := expr.(type) {
	case *ast.LiteralExpr:
		c.compileLiteral(e)
	case *ast.IdentifierExpr:
		c.compileIdentifier(e)
	case *ast.UnaryExpr:
		c.compileUnary(e)
	case *ast.BinaryExpr:
		c.compileBinary(e)
	case *ast.AssignExpr:
		c.compileAssign(e)
	case *ast.SetterExpr:
		c.compileSetter(e)
	case *ast.CallExpr:
		c.compileCall(e)
	case *ast.ListExpr:
		c.compileList(e)
	case *ast.MapExpr:
		c.compileMap(e)
	case *ast.RangeExpr:
		c.compileRange(e)
	case *ast.StringInterpolationExpr:
		c.compileStringInterpolation(e)
	case *ast.FnExpr:
		c.compileFnExpr(e)
	case *ast.LogicalExpr:
		c.compileLogical(e)
	case *ast.IsExpr:
		c.compileIs(e)
	case *ast.ThisExpr:
		c.emitOp(bytecode.OpGetLocal, e.Line())
		c.emitByte(0, e.Line())
	case *ast.SuperExpr:
		c.compileSuper(e)
	}
}

func (c *Compiler) compileLiteral(e *ast.LiteralExpr) {
	if e.Value == nil {
		c.emitOp(bytecode.OpNull, e.Line())
	} else if b, ok := e.Value.(bool); ok {
		if b {
			c.emitOp(bytecode.OpTrue, e.Line())
		} else {
			c.emitOp(bytecode.OpFalse, e.Line())
		}
	} else if n, ok := e.Value.(float64); ok {
		c.scope.Fn.Chunk.WriteConstant(n, e.Line())
	} else if s, ok := e.Value.(string); ok {
		c.scope.Fn.Chunk.WriteConstant(runtime.NewObjString(s), e.Line())
	}
}

func (c *Compiler) compileIdentifier(e *ast.IdentifierExpr) {
	local := c.scope.ResolveLocal(e.Name)
	if local != -1 {
		c.emitOp(bytecode.OpGetLocal, e.Line())
		c.emitByte(byte(local), e.Line())
		return
	}

	upvalue := c.scope.ResolveUpvalue(e.Name)
	if upvalue != -1 {
		c.emitOp(bytecode.OpGetUpvalue, e.Line())
		c.emitByte(byte(upvalue), e.Line())
		return
	}

	idx := c.scope.Fn.Chunk.AddConstant(e.Name)
	c.emitOp(bytecode.OpGetGlobal, e.Line())
	c.emitByte(byte(idx), e.Line())
}

func (c *Compiler) compileUnary(e *ast.UnaryExpr) {
	c.compileExpr(e.Right)
	sig := e.Op.Text
	c.emitCall(sig, 0, e.Line())
}

func (c *Compiler) compileBinary(e *ast.BinaryExpr) {
	c.compileExpr(e.Left)
	c.compileExpr(e.Right)
	sig := fmt.Sprintf("%s(_)", e.Op.Text)
	c.emitCall(sig, 1, e.Line())
}

func (c *Compiler) compileAssign(e *ast.AssignExpr) {
	c.compileExpr(e.Value)
	local := c.scope.ResolveLocal(e.Name.Text)
	if local != -1 {
		c.emitOp(bytecode.OpSetLocal, e.Name.Line)
		c.emitByte(byte(local), e.Name.Line)
		return
	}

	upvalue := c.scope.ResolveUpvalue(e.Name.Text)
	if upvalue != -1 {
		c.emitOp(bytecode.OpSetUpvalue, e.Name.Line)
		c.emitByte(byte(upvalue), e.Name.Line)
		return
	}

	idx := c.scope.Fn.Chunk.AddConstant(e.Name.Text)
	c.emitOp(bytecode.OpSetGlobal, e.Name.Line)
	c.emitByte(byte(idx), e.Name.Line)
}

func (c *Compiler) compileSetter(e *ast.SetterExpr) {
	c.compileExpr(e.Receiver)
	c.compileExpr(e.Value)
	sig := fmt.Sprintf("%s=(_)", e.Name)
	c.emitCall(sig, 1, e.LineNum)
}

func (c *Compiler) compileCall(e *ast.CallExpr) {
	c.compileExpr(e.Receiver)
	for _, arg := range e.Args {
		c.compileExpr(arg)
	}

	argCount := len(e.Args)
	if e.BlockArg != nil {
		c.compileFnExpr(e.BlockArg)
		argCount++
	}

	sig := e.Method
	if argCount > 0 {
		if e.Method == "[_]" {
			sig = fmt.Sprintf("[%s]", buildArgSignature(argCount))
		} else if e.Method == "[_]=(_)" {
			sig = fmt.Sprintf("[%s]=(_)", buildArgSignature(argCount-1))
		} else {
			sig = fmt.Sprintf("%s(%s)", e.Method, buildArgSignature(argCount))
		}
	}
	c.emitCall(sig, argCount, e.LineNum)
}

func (c *Compiler) compileList(e *ast.ListExpr) {
	c.emitOp(bytecode.OpGetGlobal, e.Line())
	idx := c.scope.Fn.Chunk.AddConstant("List")
	c.emitByte(byte(idx), e.Line())
	c.emitCall("new()", 0, e.Line())

	for _, elem := range e.Elements {
		c.emitOp(bytecode.OpDup, e.Line())
		c.compileExpr(elem)
		c.emitCall("add(_)", 1, e.Line())
		c.emitOp(bytecode.OpPop, e.Line())
	}
}

func (c *Compiler) compileMap(e *ast.MapExpr) {
	c.emitOp(bytecode.OpGetGlobal, e.Line())
	idx := c.scope.Fn.Chunk.AddConstant("Map")
	c.emitByte(byte(idx), e.Line())
	c.emitCall("new()", 0, e.Line())

	for _, entry := range e.Entries {
		c.emitOp(bytecode.OpDup, e.Line())
		c.compileExpr(entry.Key)
		c.compileExpr(entry.Value)
		c.emitCall("[_]=(_)", 2, e.Line())
		c.emitOp(bytecode.OpPop, e.Line())
	}
}

func (c *Compiler) compileRange(e *ast.RangeExpr) {
	c.compileExpr(e.From)
	c.compileExpr(e.To)
	op := "..(_)"
	if !e.IsInclusive {
		op = "...(_)"
	}
	c.emitCall(op, 1, e.LineNum)
}

func (c *Compiler) compileStringInterpolation(e *ast.StringInterpolationExpr) {
	// Build a string by concatenating all parts, calling toString on non-string exprs
	for i, part := range e.Parts {
		c.compileExpr(part)
		// Call toString on every part to ensure it's a string
		c.emitCall("toString", 0, e.LineNum)
		if i > 0 {
			c.emitCall("+(_)", 1, e.LineNum)
		}
	}
}

func (c *Compiler) compileLogical(e *ast.LogicalExpr) {
	c.compileExpr(e.Left)
	var shortCircuitOp bytecode.Opcode
	if e.IsAnd {
		// if left is false, short circuit (keep false on stack)
		shortCircuitOp = bytecode.OpJumpIfFalse
	} else {
		// if left is true, short circuit (keep true on stack)
		shortCircuitOp = bytecode.OpJumpIfTrue
	}
	jump := c.emitJump(shortCircuitOp, e.Line())
	c.emitOp(bytecode.OpPop, e.Line())
	c.compileExpr(e.Right)
	c.patchJump(jump)
}

func (c *Compiler) compileIs(e *ast.IsExpr) {
	c.compileExpr(e.Left)
	c.compileExpr(e.Right)
	c.emitOp(bytecode.OpIs, e.LineNum)
}

func (c *Compiler) compileFnExpr(e *ast.FnExpr) {
	fn := runtime.NewObjFn("", len(e.Params), c.module)
	childScope := NewCompilerScope(c.scope, TypeFn, fn)

	for _, p := range e.Params {
		childScope.AddLocal(p)
	}

	oldScope := c.scope
	c.scope = childScope

	for _, stmt := range e.Body {
		c.compileStmt(stmt)
	}
	c.emitOp(bytecode.OpNull, e.LineNum)
	c.emitOp(bytecode.OpReturn, e.LineNum)

	c.scope = oldScope

	fnIdx := c.scope.Fn.Chunk.AddConstant(fn)
	c.emitOp(bytecode.OpClosure, e.LineNum)
	c.emitByte(byte(fnIdx), e.LineNum)

	for _, upvalue := range childScope.Upvalues {
		if upvalue.IsLocal {
			c.emitByte(1, e.LineNum)
		} else {
			c.emitByte(0, e.LineNum)
		}
		c.emitByte(byte(upvalue.Index), e.LineNum)
	}
}

func (c *Compiler) compileSuper(e *ast.SuperExpr) {
	c.emitOp(bytecode.OpGetLocal, e.LineNum)
	c.emitByte(0, e.LineNum)

	for _, arg := range e.Args {
		c.compileExpr(arg)
	}

	sig := e.Method
	if len(e.Args) > 0 {
		sig = fmt.Sprintf("%s(%s)", e.Method, buildArgSignature(len(e.Args)))
	}
	sigIdx := c.scope.Fn.Chunk.AddConstant(sig)
	c.emitOp(bytecode.OpSuperCall, e.LineNum)
	c.emitByte(byte(sigIdx), e.LineNum)
	c.emitByte(byte(len(e.Args)), e.LineNum)
}

func (c *Compiler) emitByte(b byte, line int) {
	c.scope.Fn.Chunk.WriteByte(b, line)
}

func (c *Compiler) emitOp(op bytecode.Opcode, line int) {
	c.scope.Fn.Chunk.WriteOp(op, line)
}

func (c *Compiler) emitCall(signature string, argCount int, line int) {
	idx := c.scope.Fn.Chunk.AddConstant(signature)
	c.emitOp(bytecode.OpCall, line)
	c.emitByte(byte(idx), line)
	c.emitByte(byte(argCount), line)
}

func (c *Compiler) emitJump(op bytecode.Opcode, line int) int {
	c.emitOp(op, line)
	c.emitByte(0xFF, line)
	c.emitByte(0xFF, line)
	return len(c.scope.Fn.Chunk.Code) - 2
}

func (c *Compiler) patchJump(offset int) {
	jump := len(c.scope.Fn.Chunk.Code) - offset - 2
	c.scope.Fn.Chunk.Code[offset] = byte((jump >> 8) & 0xFF)
	c.scope.Fn.Chunk.Code[offset+1] = byte(jump & 0xFF)
}

func (c *Compiler) emitLoop(start int, line int) {
	c.emitOp(bytecode.OpLoop, line)
	offset := len(c.scope.Fn.Chunk.Code) - start + 2
	c.emitByte(byte((offset>>8)&0xFF), line)
	c.emitByte(byte(offset&0xFF), line)
}

func (c *Compiler) beginScope() {
	c.scope.ScopeDepth++
}

func (c *Compiler) endScope(line int) {
	c.scope.ScopeDepth--
	for len(c.scope.Locals) > 0 && c.scope.Locals[len(c.scope.Locals)-1].Depth > c.scope.ScopeDepth {
		if c.scope.Locals[len(c.scope.Locals)-1].IsUpvalue {
			c.emitOp(bytecode.OpCloseUpvalue, line)
		} else {
			c.emitOp(bytecode.OpPop, line)
		}
		c.scope.Locals = c.scope.Locals[:len(c.scope.Locals)-1]
	}
}

func buildArgSignature(count int) string {
	if count == 0 {
		return ""
	}
	parts := make([]string, count)
	for i := 0; i < count; i++ {
		parts[i] = "_"
	}
	return joinStrings(parts, ",")
}

func joinStrings(slice []string, sep string) string {
	if len(slice) == 0 {
		return ""
	}
	res := slice[0]
	for i := 1; i < len(slice); i++ {
		res += sep + slice[i]
	}
	return res
}
