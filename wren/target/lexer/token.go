package lexer

import "fmt"

type TokenType int

const (
	// Single-character tokens
	TokenLeftParen TokenType = iota
	TokenRightParen
	TokenLeftBrace
	TokenRightBrace
	TokenLeftBracket
	TokenRightBracket
	TokenComma
	TokenDot
	TokenColon
	TokenSemicolon
	TokenPlus
	TokenMinus
	TokenStar
	TokenSlash
	TokenPercent
	TokenTilde
	TokenAmp
	TokenAmpAmp
	TokenPipe
	TokenPipePipe
	TokenCaret
	TokenQuestion

	// One or two character tokens
	TokenEqual
	TokenEqualEqual
	TokenBang
	TokenBangEqual
	TokenLess
	TokenLessEqual
	TokenGreater
	TokenGreaterEqual
	TokenDotDot
	TokenDotDotDot
	TokenArrow
	TokenLessLess
	TokenGreaterGreater

	// Literals
	TokenIdentifier
	TokenString
	TokenInterpolation
	TokenNumber

	// Keywords
	TokenClass
	TokenVar
	TokenIs
	TokenStatic
	TokenImport
	TokenFor
	TokenIn
	TokenReturn
	TokenBreak
	TokenContinue
	TokenIf
	TokenElse
	TokenWhile
	TokenSuper
	TokenThis
	TokenTrue
	TokenFalse
	TokenNull
	TokenForeign
	TokenConstruct

	// Formatting & Control
	TokenNewline
	TokenEOF
	TokenError
)

type Token struct {
	Type   TokenType
	Text   string
	Line   int
	Column int
}

func (t Token) String() string {
	return fmt.Sprintf("Token(%d, '%s', Line:%d)", t.Type, t.Text, t.Line)
}

var Keywords = map[string]TokenType{
	"class":     TokenClass,
	"var":       TokenVar,
	"is":        TokenIs,
	"static":    TokenStatic,
	"import":    TokenImport,
	"for":       TokenFor,
	"in":        TokenIn,
	"return":    TokenReturn,
	"break":     TokenBreak,
	"continue":  TokenContinue,
	"if":        TokenIf,
	"else":      TokenElse,
	"while":     TokenWhile,
	"super":     TokenSuper,
	"this":      TokenThis,
	"true":      TokenTrue,
	"false":     TokenFalse,
	"null":      TokenNull,
	"foreign":   TokenForeign,
	"construct": TokenConstruct,
}
