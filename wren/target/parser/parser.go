package parser

import (
	"fmt"
	"strconv"
	"wren/ast"
	"wren/lexer"
)

type Precedence int

const (
	PREC_NONE Precedence = iota
	PREC_ASSIGNMENT
	PREC_CONDITIONAL
	PREC_LOGICAL_OR
	PREC_LOGICAL_AND
	PREC_EQUALITY
	PREC_IS
	PREC_COMPARISON
	PREC_BITWISE_OR
	PREC_BITWISE_XOR
	PREC_BITWISE_AND
	PREC_BITWISE_SHIFT
	PREC_RANGE
	PREC_TERM
	PREC_FACTOR
	PREC_UNARY
	PREC_CALL
	PREC_PRIMARY
)

type ParseError struct {
	Message string
	Line    int
}

func (e *ParseError) Error() string {
	return fmt.Sprintf("[%d] %s", e.Line, e.Message)
}

type Parser struct {
	lexer   *lexer.Lexer
	current lexer.Token
	previous lexer.Token
	hadError bool
	errors  []ParseError
}

func NewParser(l *lexer.Lexer) *Parser {
	p := &Parser{
		lexer:  l,
		errors: make([]ParseError, 0),
	}
	p.advance()
	return p
}

func (p *Parser) HadError() bool {
	return p.hadError
}

func (p *Parser) Errors() []ParseError {
	return p.errors
}

func (p *Parser) Parse() ([]ast.Stmt, error) {
	statements := make([]ast.Stmt, 0)
	for !p.isAtEnd() {
		if p.match(lexer.TokenNewline) {
			continue
		}
		stmt := p.statement()
		if stmt != nil {
			statements = append(statements, stmt)
		}
	}
	if p.hadError && len(p.errors) > 0 {
		return nil, &p.errors[0]
	}
	return statements, nil
}

func (p *Parser) statement() ast.Stmt {
	if p.match(lexer.TokenVar) {
		return p.varDeclaration()
	}
	if p.match(lexer.TokenClass) {
		return p.classDeclaration()
	}
	if p.match(lexer.TokenIf) {
		return p.ifStatement()
	}
	if p.match(lexer.TokenWhile) {
		return p.whileStatement()
	}
	if p.match(lexer.TokenFor) {
		return p.forStatement()
	}
	if p.match(lexer.TokenReturn) {
		return p.returnStatement()
	}
	if p.match(lexer.TokenBreak) {
		return &ast.BreakStmt{Token: p.previous}
	}
	if p.match(lexer.TokenContinue) {
		return &ast.ContinueStmt{Token: p.previous}
	}
	if p.match(lexer.TokenImport) {
		return p.importStatement()
	}
	if p.match(lexer.TokenLeftBrace) {
		return p.blockStatement()
	}

	return p.expressionStatement()
}

func (p *Parser) varDeclaration() ast.Stmt {
	name := p.consume(lexer.TokenIdentifier, "Expect variable name.")
	var initializer ast.Expr
	if p.match(lexer.TokenEqual) {
		initializer = p.expression()
	}
	p.match(lexer.TokenNewline)
	return &ast.VarDeclStmt{
		Name:        name,
		Initializer: initializer,
	}
}

func (p *Parser) classDeclaration() ast.Stmt {
	name := p.consume(lexer.TokenIdentifier, "Expect class name.")
	var superclass *ast.IdentifierExpr
	if p.match(lexer.TokenIs) {
		superName := p.consume(lexer.TokenIdentifier, "Expect superclass name.")
		superclass = &ast.IdentifierExpr{Token: superName, Name: superName.Text}
	}

	p.consume(lexer.TokenLeftBrace, "Expect '{' before class body.")
	p.match(lexer.TokenNewline)

	methods := make([]*ast.MethodDeclStmt, 0)
	for !p.check(lexer.TokenRightBrace) && !p.isAtEnd() {
		if p.match(lexer.TokenNewline) {
			continue
		}
		method := p.methodDeclaration()
		if method != nil {
			methods = append(methods, method)
		}
	}

	p.consume(lexer.TokenRightBrace, "Expect '}' after class body.")
	return &ast.ClassDeclStmt{
		Name:       name,
		Superclass: superclass,
		Methods:    methods,
	}
}

func (p *Parser) methodDeclaration() *ast.MethodDeclStmt {
	isStatic := p.match(lexer.TokenStatic)
	isConstruct := p.match(lexer.TokenConstruct)

	methodNameToken := p.advance()
	methodName := methodNameToken.Text

	// Operator method names
	if methodNameToken.Type == lexer.TokenPlus || methodNameToken.Type == lexer.TokenMinus || methodNameToken.Type == lexer.TokenStar || methodNameToken.Type == lexer.TokenSlash || methodNameToken.Type == lexer.TokenPercent {
		methodName = methodNameToken.Text
	} else if methodNameToken.Type == lexer.TokenLeftBracket {
		p.consume(lexer.TokenRightBracket, "Expect ']' after '['.")
		if p.match(lexer.TokenEqual) {
			methodName = "[_]=(_)"
		} else {
			methodName = "[_]"
		}
	}

	params := make([]string, 0)
	if p.match(lexer.TokenLeftParen) {
		if !p.check(lexer.TokenRightParen) {
			for {
				paramToken := p.consume(lexer.TokenIdentifier, "Expect parameter name.")
				params = append(params, paramToken.Text)
				if !p.match(lexer.TokenComma) {
					break
				}
			}
		}
		p.consume(lexer.TokenRightParen, "Expect ')' after parameters.")
	}

	p.consume(lexer.TokenLeftBrace, "Expect '{' before method body.")
	body := p.blockStatements()

	return &ast.MethodDeclStmt{
		Name:        methodName,
		IsStatic:    isStatic,
		IsConstruct: isConstruct,
		Params:      params,
		Body:        body,
		LineNum:     methodNameToken.Line,
	}
}

func (p *Parser) ifStatement() ast.Stmt {
	line := p.previous.Line
	p.consume(lexer.TokenLeftParen, "Expect '(' after 'if'.")
	condition := p.expression()
	p.consume(lexer.TokenRightParen, "Expect ')' after condition.")

	thenBranch := p.statement()
	var elseBranch ast.Stmt
	if p.match(lexer.TokenElse) {
		elseBranch = p.statement()
	}

	return &ast.IfStmt{
		Condition:  condition,
		ThenBranch: thenBranch,
		ElseBranch: elseBranch,
		LineNum:    line,
	}
}

func (p *Parser) whileStatement() ast.Stmt {
	line := p.previous.Line
	p.consume(lexer.TokenLeftParen, "Expect '(' after 'while'.")
	condition := p.expression()
	p.consume(lexer.TokenRightParen, "Expect ')' after condition.")

	body := p.statement()
	return &ast.WhileStmt{
		Condition: condition,
		Body:      body,
		LineNum:   line,
	}
}

func (p *Parser) forStatement() ast.Stmt {
	line := p.previous.Line
	p.consume(lexer.TokenLeftParen, "Expect '(' after 'for'.")
	variable := p.consume(lexer.TokenIdentifier, "Expect variable name in 'for'.")
	p.consume(lexer.TokenIn, "Expect 'in' after for variable.")
	iterator := p.expression()
	p.consume(lexer.TokenRightParen, "Expect ')' after for iterator.")

	body := p.statement()
	return &ast.ForStmt{
		Variable: variable,
		Iterator: iterator,
		Body:     body,
		LineNum:  line,
	}
}

func (p *Parser) returnStatement() ast.Stmt {
	token := p.previous
	var value ast.Expr
	if !p.check(lexer.TokenNewline) && !p.check(lexer.TokenRightBrace) && !p.check(lexer.TokenEOF) {
		value = p.expression()
	}
	p.match(lexer.TokenNewline)
	return &ast.ReturnStmt{
		Token: token,
		Value: value,
	}
}

func (p *Parser) importStatement() ast.Stmt {
	pathToken := p.consume(lexer.TokenString, "Expect module import path.")
	symbols := make([]ast.ImportSymbol, 0)

	if p.match(lexer.TokenFor) {
		for {
			nameToken := p.consume(lexer.TokenIdentifier, "Expect symbol name in import.")
			alias := nameToken.Text
			symbols = append(symbols, ast.ImportSymbol{Name: nameToken.Text, Alias: alias})
			if !p.match(lexer.TokenComma) {
				break
			}
		}
	}
	p.match(lexer.TokenNewline)
	return &ast.ImportStmt{
		Path:    pathToken,
		Symbols: symbols,
	}
}

func (p *Parser) blockStatement() ast.Stmt {
	line := p.previous.Line
	statements := p.blockStatements()
	return &ast.BlockStmt{
		Statements: statements,
		LineNum:    line,
	}
}

func (p *Parser) blockStatements() []ast.Stmt {
	statements := make([]ast.Stmt, 0)
	for !p.check(lexer.TokenRightBrace) && !p.isAtEnd() {
		if p.match(lexer.TokenNewline) {
			continue
		}
		stmt := p.statement()
		if stmt != nil {
			statements = append(statements, stmt)
		}
	}
	p.consume(lexer.TokenRightBrace, "Expect '}' after block.")
	return statements
}

func (p *Parser) expressionStatement() ast.Stmt {
	expr := p.expression()
	p.match(lexer.TokenNewline)
	return &ast.ExprStmt{Expression: expr}
}

func (p *Parser) expression() ast.Expr {
	return p.parsePrecedence(PREC_ASSIGNMENT)
}

func (p *Parser) parsePrecedence(prec Precedence) ast.Expr {
	token := p.advance()

	prefix := p.getPrefix(token)
	if prefix == nil {
		p.error(token, fmt.Sprintf("Expect expression, got '%s'", token.Text))
		return nil
	}

	left := prefix()

	for prec <= p.getPrecedence(p.current.Type) {
		token = p.advance()
		infix := p.getInfix(token)
		if infix == nil {
			break
		}
		left = infix(left, token)
	}

	return left
}

func (p *Parser) getPrefix(token lexer.Token) func() ast.Expr {
	switch token.Type {
	case lexer.TokenNumber:
		return func() ast.Expr {
			val, _ := strconv.ParseFloat(token.Text, 64)
			return &ast.LiteralExpr{Token: token, Value: val}
		}
	case lexer.TokenString:
		return func() ast.Expr {
			return &ast.LiteralExpr{Token: token, Value: token.Text}
		}
	case lexer.TokenInterpolation:
		return func() ast.Expr {
			parts := []ast.Expr{&ast.LiteralExpr{Token: token, Value: token.Text}}
			parts = append(parts, p.expression())
			for p.match(lexer.TokenInterpolation) {
				parts = append(parts, &ast.LiteralExpr{Token: p.previous, Value: p.previous.Text})
				parts = append(parts, p.expression())
			}
			return &ast.StringInterpolationExpr{Parts: parts, LineNum: token.Line}
		}
	case lexer.TokenTrue:
		return func() ast.Expr { return &ast.LiteralExpr{Token: token, Value: true} }
	case lexer.TokenFalse:
		return func() ast.Expr { return &ast.LiteralExpr{Token: token, Value: false} }
	case lexer.TokenNull:
		return func() ast.Expr { return &ast.LiteralExpr{Token: token, Value: nil} }
	case lexer.TokenIdentifier:
		return func() ast.Expr { return &ast.IdentifierExpr{Token: token, Name: token.Text} }
	case lexer.TokenThis:
		return func() ast.Expr { return &ast.ThisExpr{Token: token} }
	case lexer.TokenSuper:
		return func() ast.Expr {
			p.consume(lexer.TokenDot, "Expect '.' after 'super'.")
			methodToken := p.consume(lexer.TokenIdentifier, "Expect superclass method name.")
			args := make([]ast.Expr, 0)
			if p.match(lexer.TokenLeftParen) {
				if !p.check(lexer.TokenRightParen) {
					for {
						args = append(args, p.expression())
						if !p.match(lexer.TokenComma) {
							break
						}
					}
				}
				p.consume(lexer.TokenRightParen, "Expect ')' after super arguments.")
			}
			return &ast.SuperExpr{Method: methodToken.Text, Args: args, LineNum: token.Line}
		}
	case lexer.TokenLeftParen:
		return func() ast.Expr {
			expr := p.expression()
			p.consume(lexer.TokenRightParen, "Expect ')' after expression.")
			return expr
		}
	case lexer.TokenLeftBracket:
		return func() ast.Expr {
			elements := make([]ast.Expr, 0)
			if !p.check(lexer.TokenRightBracket) {
				for {
					elements = append(elements, p.expression())
					if !p.match(lexer.TokenComma) {
						break
					}
				}
			}
			p.consume(lexer.TokenRightBracket, "Expect ']' after list elements.")
			return &ast.ListExpr{Token: token, Elements: elements}
		}
	case lexer.TokenLeftBrace:
		return func() ast.Expr {
			// Map literal or Fn closure literal
			if p.check(lexer.TokenRightBrace) || p.peekNextIsColon() {
				entries := make([]ast.MapEntry, 0)
				if !p.check(lexer.TokenRightBrace) {
					for {
						key := p.expression()
						p.consume(lexer.TokenColon, "Expect ':' after map key.")
						val := p.expression()
						entries = append(entries, ast.MapEntry{Key: key, Value: val})
						if !p.match(lexer.TokenComma) {
							break
						}
					}
				}
				p.consume(lexer.TokenRightBrace, "Expect '}' after map entries.")
				return &ast.MapExpr{Token: token, Entries: entries}
			}

			// Closure Fn block
			params := make([]string, 0)
			if p.match(lexer.TokenPipe) {
				if !p.check(lexer.TokenPipe) {
					for {
						paramToken := p.consume(lexer.TokenIdentifier, "Expect parameter name.")
						params = append(params, paramToken.Text)
						if !p.match(lexer.TokenComma) {
							break
						}
					}
				}
				p.consume(lexer.TokenPipe, "Expect '|' after closure parameters.")
			}
			body := p.blockStatements()
			return &ast.FnExpr{Params: params, Body: body, LineNum: token.Line}
		}
	case lexer.TokenMinus, lexer.TokenBang, lexer.TokenTilde:
		return func() ast.Expr {
			right := p.parsePrecedence(PREC_UNARY)
			return &ast.UnaryExpr{Op: token, Right: right}
		}
	}
	return nil
}

func (p *Parser) getInfix(token lexer.Token) func(ast.Expr, lexer.Token) ast.Expr {
	switch token.Type {
	case lexer.TokenEqual:
		return func(left ast.Expr, op lexer.Token) ast.Expr {
			right := p.parsePrecedence(PREC_ASSIGNMENT)
			if id, ok := left.(*ast.IdentifierExpr); ok {
				return &ast.AssignExpr{Name: id.Token, Value: right}
			}
			if call, ok := left.(*ast.CallExpr); ok {
				if call.Method == "[_]" {
					args := append(call.Args, right)
					return &ast.CallExpr{Receiver: call.Receiver, Method: "[_]=(_)", Args: args, LineNum: op.Line}
				}
				return &ast.SetterExpr{Receiver: call.Receiver, Name: call.Method, Value: right, LineNum: op.Line}
			}
			p.error(op, "Invalid assignment target.")
			return nil
		}
	case lexer.TokenPlus, lexer.TokenMinus, lexer.TokenStar, lexer.TokenSlash, lexer.TokenPercent,
		lexer.TokenEqualEqual, lexer.TokenBangEqual, lexer.TokenLess, lexer.TokenLessEqual,
		lexer.TokenGreater, lexer.TokenGreaterEqual, lexer.TokenAmp, lexer.TokenPipe, lexer.TokenCaret,
		lexer.TokenLessLess, lexer.TokenGreaterGreater:
		return func(left ast.Expr, op lexer.Token) ast.Expr {
			prec := p.getPrecedence(op.Type)
			right := p.parsePrecedence(prec + 1)
			return &ast.BinaryExpr{Left: left, Op: op, Right: right}
		}
	case lexer.TokenAmpAmp:
		return func(left ast.Expr, op lexer.Token) ast.Expr {
			right := p.parsePrecedence(PREC_LOGICAL_AND + 1)
			return &ast.LogicalExpr{Left: left, Op: op, Right: right, IsAnd: true}
		}
	case lexer.TokenPipePipe:
		return func(left ast.Expr, op lexer.Token) ast.Expr {
			right := p.parsePrecedence(PREC_LOGICAL_OR + 1)
			return &ast.LogicalExpr{Left: left, Op: op, Right: right, IsAnd: false}
		}
	case lexer.TokenIs:
		return func(left ast.Expr, op lexer.Token) ast.Expr {
			right := p.parsePrecedence(PREC_IS + 1)
			return &ast.IsExpr{Left: left, Right: right, LineNum: op.Line}
		}
	case lexer.TokenDotDot, lexer.TokenDotDotDot:
		return func(left ast.Expr, op lexer.Token) ast.Expr {
			right := p.parsePrecedence(PREC_RANGE + 1)
			return &ast.RangeExpr{From: left, To: right, IsInclusive: op.Type == lexer.TokenDotDot, LineNum: op.Line}
		}
	case lexer.TokenDot:
		return func(left ast.Expr, op lexer.Token) ast.Expr {
			nameToken := p.consume(lexer.TokenIdentifier, "Expect property or method name after '.'.")
			args := make([]ast.Expr, 0)
			if p.match(lexer.TokenLeftParen) {
				if !p.check(lexer.TokenRightParen) {
					for {
						args = append(args, p.expression())
						if !p.match(lexer.TokenComma) {
							break
						}
					}
				}
				p.consume(lexer.TokenRightParen, "Expect ')' after arguments.")
			}
			return &ast.CallExpr{Receiver: left, Method: nameToken.Text, Args: args, LineNum: op.Line}
		}
	case lexer.TokenLeftBracket:
		return func(left ast.Expr, op lexer.Token) ast.Expr {
			args := make([]ast.Expr, 0)
			if !p.check(lexer.TokenRightBracket) {
				for {
					args = append(args, p.expression())
					if !p.match(lexer.TokenComma) {
						break
					}
				}
			}
			p.consume(lexer.TokenRightBracket, "Expect ']' after subscript index.")
			return &ast.CallExpr{Receiver: left, Method: "[_]", Args: args, LineNum: op.Line}
		}
	case lexer.TokenLeftParen:
		return func(left ast.Expr, op lexer.Token) ast.Expr {
			args := make([]ast.Expr, 0)
			if !p.check(lexer.TokenRightParen) {
				for {
					args = append(args, p.expression())
					if !p.match(lexer.TokenComma) {
						break
					}
				}
			}
			p.consume(lexer.TokenRightParen, "Expect ')' after call arguments.")
			return &ast.CallExpr{Receiver: left, Method: "call", Args: args, LineNum: op.Line}
		}
	}
	return nil
}

func (p *Parser) getPrecedence(tokenType lexer.TokenType) Precedence {
	switch tokenType {
	case lexer.TokenEqual:
		return PREC_ASSIGNMENT
	case lexer.TokenPipePipe:
		return PREC_LOGICAL_OR
	case lexer.TokenAmpAmp:
		return PREC_LOGICAL_AND
	case lexer.TokenEqualEqual, lexer.TokenBangEqual:
		return PREC_EQUALITY
	case lexer.TokenIs:
		return PREC_IS
	case lexer.TokenLess, lexer.TokenLessEqual, lexer.TokenGreater, lexer.TokenGreaterEqual:
		return PREC_COMPARISON
	case lexer.TokenAmp:
		return PREC_BITWISE_AND
	case lexer.TokenPipe:
		return PREC_BITWISE_OR
	case lexer.TokenCaret:
		return PREC_BITWISE_XOR
	case lexer.TokenLessLess, lexer.TokenGreaterGreater:
		return PREC_BITWISE_SHIFT
	case lexer.TokenDotDot, lexer.TokenDotDotDot:
		return PREC_RANGE
	case lexer.TokenPlus, lexer.TokenMinus:
		return PREC_TERM
	case lexer.TokenStar, lexer.TokenSlash, lexer.TokenPercent:
		return PREC_FACTOR
	case lexer.TokenDot, lexer.TokenLeftBracket, lexer.TokenLeftParen:
		return PREC_CALL
	}
	return PREC_NONE
}

func (p *Parser) peekNextIsColon() bool {
	return p.current.Type == lexer.TokenColon
}

func (p *Parser) advance() lexer.Token {
	p.previous = p.current
	for {
		p.current = p.lexer.NextToken()
		if p.current.Type != lexer.TokenError {
			break
		}
		p.error(p.current, p.current.Text)
	}
	return p.previous
}

func (p *Parser) check(tokenType lexer.TokenType) bool {
	if p.isAtEnd() {
		return false
	}
	return p.current.Type == tokenType
}

func (p *Parser) match(tokenType lexer.TokenType) bool {
	if !p.check(tokenType) {
		return false
	}
	p.advance()
	return true
}

func (p *Parser) consume(tokenType lexer.TokenType, message string) lexer.Token {
	if p.check(tokenType) {
		return p.advance()
	}
	p.error(p.current, message)
	return p.current
}

func (p *Parser) isAtEnd() bool {
	return p.current.Type == lexer.TokenEOF
}

func (p *Parser) error(token lexer.Token, message string) {
	p.hadError = true
	p.errors = append(p.errors, ParseError{Message: message, Line: token.Line})
}
