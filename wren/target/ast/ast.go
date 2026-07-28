package ast

import "wren/lexer"

type Node interface {
	Line() int
}

type Expr interface {
	Node
	exprNode()
}

type Stmt interface {
	Node
	stmtNode()
}

// Expressions

type LiteralExpr struct {
	Token lexer.Token
	Value interface{} // float64, bool, string, nil
}

func (e *LiteralExpr) Line() int  { return e.Token.Line }
func (e *LiteralExpr) exprNode() {}

type IdentifierExpr struct {
	Token lexer.Token
	Name  string
}

func (e *IdentifierExpr) Line() int  { return e.Token.Line }
func (e *IdentifierExpr) exprNode() {}

type UnaryExpr struct {
	Op    lexer.Token
	Right Expr
}

func (e *UnaryExpr) Line() int  { return e.Op.Line }
func (e *UnaryExpr) exprNode() {}

type BinaryExpr struct {
	Left  Expr
	Op    lexer.Token
	Right Expr
}

func (e *BinaryExpr) Line() int  { return e.Op.Line }
func (e *BinaryExpr) exprNode() {}

// LogicalExpr is used for && and || (short-circuit evaluation)
type LogicalExpr struct {
	Left    Expr
	Op      lexer.Token
	Right   Expr
	IsAnd   bool // true for &&, false for ||
}

func (e *LogicalExpr) Line() int  { return e.Op.Line }
func (e *LogicalExpr) exprNode() {}

// IsExpr represents the `is` operator
type IsExpr struct {
	Left    Expr
	Right   Expr
	LineNum int
}

func (e *IsExpr) Line() int  { return e.LineNum }
func (e *IsExpr) exprNode() {}

type AssignExpr struct {
	Name  lexer.Token
	Value Expr
}

func (e *AssignExpr) Line() int  { return e.Name.Line }
func (e *AssignExpr) exprNode() {}

type SetterExpr struct {
	Receiver Expr
	Name     string
	Value    Expr
	LineNum  int
}

func (e *SetterExpr) Line() int  { return e.LineNum }
func (e *SetterExpr) exprNode() {}

type CallExpr struct {
	Receiver Expr
	Method   string
	Args     []Expr
	BlockArg *FnExpr // Trailing block closure if present
	LineNum  int
}

func (e *CallExpr) Line() int  { return e.LineNum }
func (e *CallExpr) exprNode() {}

type ListExpr struct {
	Token    lexer.Token
	Elements []Expr
}

func (e *ListExpr) Line() int  { return e.Token.Line }
func (e *ListExpr) exprNode() {}

type MapEntry struct {
	Key   Expr
	Value Expr
}

type MapExpr struct {
	Token   lexer.Token
	Entries []MapEntry
}

func (e *MapExpr) Line() int  { return e.Token.Line }
func (e *MapExpr) exprNode() {}

type RangeExpr struct {
	From        Expr
	To          Expr
	IsInclusive bool
	LineNum     int
}

func (e *RangeExpr) Line() int  { return e.LineNum }
func (e *RangeExpr) exprNode() {}

type StringInterpolationExpr struct {
	Parts   []Expr
	LineNum int
}

func (e *StringInterpolationExpr) Line() int  { return e.LineNum }
func (e *StringInterpolationExpr) exprNode() {}

type FnExpr struct {
	Params  []string
	Body    []Stmt
	LineNum int
}

func (e *FnExpr) Line() int  { return e.LineNum }
func (e *FnExpr) exprNode() {}

type SuperExpr struct {
	Method  string
	Args    []Expr
	LineNum int
}

func (e *SuperExpr) Line() int  { return e.LineNum }
func (e *SuperExpr) exprNode() {}

type ThisExpr struct {
	Token lexer.Token
}

func (e *ThisExpr) Line() int  { return e.Token.Line }
func (e *ThisExpr) exprNode() {}

// Statements

type VarDeclStmt struct {
	Name        lexer.Token
	Initializer Expr
}

func (s *VarDeclStmt) Line() int  { return s.Name.Line }
func (s *VarDeclStmt) stmtNode() {}

type ExprStmt struct {
	Expression Expr
}

func (s *ExprStmt) Line() int  { return s.Expression.Line() }
func (s *ExprStmt) stmtNode() {}

type BlockStmt struct {
	Statements []Stmt
	LineNum    int
}

func (s *BlockStmt) Line() int  { return s.LineNum }
func (s *BlockStmt) stmtNode() {}

type IfStmt struct {
	Condition  Expr
	ThenBranch Stmt
	ElseBranch Stmt
	LineNum    int
}

func (s *IfStmt) Line() int  { return s.LineNum }
func (s *IfStmt) stmtNode() {}

type WhileStmt struct {
	Condition Expr
	Body      Stmt
	LineNum   int
}

func (s *WhileStmt) Line() int  { return s.LineNum }
func (s *WhileStmt) stmtNode() {}

type ForStmt struct {
	Variable lexer.Token
	Iterator Expr
	Body     Stmt
	LineNum  int
}

func (s *ForStmt) Line() int  { return s.LineNum }
func (s *ForStmt) stmtNode() {}

type ReturnStmt struct {
	Token lexer.Token
	Value Expr
}

func (s *ReturnStmt) Line() int  { return s.Token.Line }
func (s *ReturnStmt) stmtNode() {}

type BreakStmt struct {
	Token lexer.Token
}

func (s *BreakStmt) Line() int  { return s.Token.Line }
func (s *BreakStmt) stmtNode() {}

type ContinueStmt struct {
	Token lexer.Token
}

func (s *ContinueStmt) Line() int  { return s.Token.Line }
func (s *ContinueStmt) stmtNode() {}

type MethodDeclStmt struct {
	Name        string
	IsStatic    bool
	IsConstruct bool
	Params      []string
	Body        []Stmt
	LineNum     int
}

func (s *MethodDeclStmt) Line() int  { return s.LineNum }
func (s *MethodDeclStmt) stmtNode() {}

type ClassDeclStmt struct {
	Name       lexer.Token
	Superclass *IdentifierExpr
	Methods    []*MethodDeclStmt
}

func (s *ClassDeclStmt) Line() int  { return s.Name.Line }
func (s *ClassDeclStmt) stmtNode() {}

type ImportSymbol struct {
	Name  string
	Alias string
}

type ImportStmt struct {
	Path    lexer.Token
	Symbols []ImportSymbol
}

func (s *ImportStmt) Line() int  { return s.Path.Line }
func (s *ImportStmt) stmtNode() {}
