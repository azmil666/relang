package lexer

import (
	"fmt"
	"strconv"
	"strings"
)

type Lexer struct {
	source      string
	start       int
	current     int
	line        int
	column      int
	startCol    int
	interpStack []int // Stack of parenthesis counts for string interpolation
}

func NewLexer(source string) *Lexer {
	return &Lexer{
		source:      source,
		start:       0,
		current:     0,
		line:        1,
		column:      1,
		startCol:    1,
		interpStack: make([]int, 0),
	}
}

func (l *Lexer) NextToken() Token {
	l.skipWhitespaceAndComments()
	l.start = l.current
	l.startCol = l.column

	if l.isAtEnd() {
		return l.makeToken(TokenEOF, "")
	}

	c := l.advance()

	// If we are inside a string interpolation expression and encounter ')', pop interpolation stack
	if len(l.interpStack) > 0 && c == ')' {
		l.interpStack[len(l.interpStack)-1]--
		if l.interpStack[len(l.interpStack)-1] == 0 {
			l.interpStack = l.interpStack[:len(l.interpStack)-1]
			return l.scanString(false)
		}
	}

	if len(l.interpStack) > 0 && c == '(' {
		l.interpStack[len(l.interpStack)-1]++
	}

	if isAlpha(c) {
		return l.scanIdentifier()
	}

	if isDigit(c) {
		return l.scanNumber()
	}

	switch c {
	case '\n':
		l.line++
		l.column = 1
		return l.makeToken(TokenNewline, "\n")
	case '(':
		return l.makeToken(TokenLeftParen, "(")
	case ')':
		return l.makeToken(TokenRightParen, ")")
	case '{':
		return l.makeToken(TokenLeftBrace, "{")
	case '}':
		return l.makeToken(TokenRightBrace, "}")
	case '[':
		return l.makeToken(TokenLeftBracket, "[")
	case ']':
		return l.makeToken(TokenRightBracket, "]")
	case ',':
		return l.makeToken(TokenComma, ",")
	case ':':
		return l.makeToken(TokenColon, ":")
	case ';':
		return l.makeToken(TokenSemicolon, ";")
	case '+':
		return l.makeToken(TokenPlus, "+")
	case '-':
		return l.makeToken(TokenMinus, "-")
	case '*':
		return l.makeToken(TokenStar, "*")
	case '/':
		return l.makeToken(TokenSlash, "/")
	case '%':
		return l.makeToken(TokenPercent, "%")
	case '~':
		return l.makeToken(TokenTilde, "~")
	case '&':
		if l.match('&') {
			return l.makeToken(TokenAmpAmp, "&&")
		}
		return l.makeToken(TokenAmp, "&")
	case '|':
		if l.match('|') {
			return l.makeToken(TokenPipePipe, "||")
		}
		return l.makeToken(TokenPipe, "|")
	case '^':
		return l.makeToken(TokenCaret, "^")
	case '?':
		return l.makeToken(TokenQuestion, "?")
	case '=':
		if l.match('=') {
			return l.makeToken(TokenEqualEqual, "==")
		}
		return l.makeToken(TokenEqual, "=")
	case '!':
		if l.match('=') {
			return l.makeToken(TokenBangEqual, "!=")
		}
		return l.makeToken(TokenBang, "!")
	case '<':
		if l.match('=') {
			return l.makeToken(TokenLessEqual, "<=")
		}
		return l.makeToken(TokenLess, "<")
	case '>':
		if l.match('=') {
			return l.makeToken(TokenGreaterEqual, ">=")
		}
		return l.makeToken(TokenGreater, ">")
	case '.':
		if l.match('.') {
			if l.match('.') {
				return l.makeToken(TokenDotDotDot, "...")
			}
			return l.makeToken(TokenDotDot, "..")
		}
		return l.makeToken(TokenDot, ".")
	case '"':
		if l.peek() == '"' && l.peekNext() == '"' {
			l.advance()
			l.advance()
			return l.scanRawString()
		}
		return l.scanString(false)
	}

	return l.errorToken(fmt.Sprintf("Unexpected character '%c'", c))
}

func (l *Lexer) scanString(isInterpolated bool) Token {
	var builder strings.Builder
	for !l.isAtEnd() {
		c := l.advance()
		if c == '"' {
			return l.makeToken(TokenString, builder.String())
		}
		if c == '%' && l.peek() == '(' {
			l.advance() // Consume '('
			l.interpStack = append(l.interpStack, 1)
			return l.makeToken(TokenInterpolation, builder.String())
		}
		if c == '\\' {
			if l.isAtEnd() {
				return l.errorToken("Unterminated string escape")
			}
			esc := l.advance()
			switch esc {
			case '"', '\\', '/', '%':
				builder.WriteByte(esc)
			case 'b':
				builder.WriteByte('\b')
			case 'f':
				builder.WriteByte('\f')
			case 'n':
				builder.WriteByte('\n')
			case 'r':
				builder.WriteByte('\r')
			case 't':
				builder.WriteByte('\t')
			case '0':
				builder.WriteByte(0)
			case 'x':
				if l.remaining() < 2 {
					return l.errorToken("Invalid byte escape sequence")
				}
				hexStr := l.source[l.current : l.current+2]
				val, err := strconv.ParseUint(hexStr, 16, 8)
				if err != nil {
					return l.errorToken("Invalid byte escape sequence")
				}
				builder.WriteByte(byte(val))
				l.current += 2
				l.column += 2
			case 'u':
				if l.remaining() < 4 {
					return l.errorToken("Invalid unicode escape sequence")
				}
				hexStr := l.source[l.current : l.current+4]
				val, err := strconv.ParseUint(hexStr, 16, 32)
				if err != nil {
					return l.errorToken("Invalid unicode escape sequence")
				}
				builder.WriteRune(rune(val))
				l.current += 4
				l.column += 4
			case 'U':
				if l.remaining() < 8 {
					return l.errorToken("Invalid unicode escape sequence")
				}
				hexStr := l.source[l.current : l.current+8]
				val, err := strconv.ParseUint(hexStr, 16, 32)
				if err != nil {
					return l.errorToken("Invalid unicode escape sequence")
				}
				builder.WriteRune(rune(val))
				l.current += 8
				l.column += 8
			default:
				return l.errorToken(fmt.Sprintf("Invalid escape character '\\%c'", esc))
			}
		} else {
			if c == '\n' {
				l.line++
				l.column = 1
			}
			builder.WriteByte(c)
		}
	}
	return l.errorToken("Unterminated string")
}

func (l *Lexer) scanRawString() Token {
	var builder strings.Builder
	for !l.isAtEnd() {
		if l.peek() == '"' && l.peekNext() == '"' && l.peekOffset(2) == '"' {
			l.advance()
			l.advance()
			l.advance()
			return l.makeToken(TokenString, builder.String())
		}
		c := l.advance()
		if c == '\n' {
			l.line++
			l.column = 1
		}
		builder.WriteByte(c)
	}
	return l.errorToken("Unterminated raw string")
}

func (l *Lexer) scanIdentifier() Token {
	for isAlphaNumeric(l.peek()) {
		l.advance()
	}
	text := l.source[l.start:l.current]
	tokenType, isKeyword := Keywords[text]
	if isKeyword {
		return l.makeToken(tokenType, text)
	}
	return l.makeToken(TokenIdentifier, text)
}

func (l *Lexer) scanNumber() Token {
	if l.source[l.start] == '0' {
		if l.peek() == 'x' || l.peek() == 'X' {
			l.advance() // consume x
			for isHexDigit(l.peek()) {
				l.advance()
			}
			return l.makeToken(TokenNumber, l.source[l.start:l.current])
		} else if l.peek() == 'b' || l.peek() == 'B' {
			l.advance() // consume b
			for l.peek() == '0' || l.peek() == '1' {
				l.advance()
			}
			return l.makeToken(TokenNumber, l.source[l.start:l.current])
		}
	}

	for isDigit(l.peek()) {
		l.advance()
	}

	if l.peek() == '.' && isDigit(l.peekNext()) {
		l.advance() // consume '.'
		for isDigit(l.peek()) {
			l.advance()
		}
	}

	if l.peek() == 'e' || l.peek() == 'E' {
		l.advance()
		if l.peek() == '+' || l.peek() == '-' {
			l.advance()
		}
		for isDigit(l.peek()) {
			l.advance()
		}
	}

	return l.makeToken(TokenNumber, l.source[l.start:l.current])
}

func (l *Lexer) skipWhitespaceAndComments() {
	for !l.isAtEnd() {
		c := l.peek()
		switch c {
		case ' ', '\r', '\t':
			l.advance()
		case '#':
			if l.line == 1 && l.peekNext() == '!' {
				for !l.isAtEnd() && l.peek() != '\n' {
					l.advance()
				}
			} else {
				return
			}
		case '/':
			if l.peekNext() == '/' {
				for !l.isAtEnd() && l.peek() != '\n' {
					l.advance()
				}
			} else if l.peekNext() == '*' {
				l.advance() // consume /
				l.advance() // consume *
				l.skipBlockComment()
			} else {
				return
			}
		default:
			return
		}
	}
}

func (l *Lexer) skipBlockComment() {
	nesting := 1
	for !l.isAtEnd() && nesting > 0 {
		if l.peek() == '/' && l.peekNext() == '*' {
			l.advance()
			l.advance()
			nesting++
		} else if l.peek() == '*' && l.peekNext() == '/' {
			l.advance()
			l.advance()
			nesting--
		} else {
			if l.advance() == '\n' {
				l.line++
				l.column = 1
			}
		}
	}
}

func (l *Lexer) isAtEnd() bool {
	return l.current >= len(l.source)
}

func (l *Lexer) remaining() int {
	return len(l.source) - l.current
}

func (l *Lexer) advance() byte {
	c := l.source[l.current]
	l.current++
	l.column++
	return c
}

func (l *Lexer) match(expected byte) bool {
	if l.isAtEnd() || l.source[l.current] != expected {
		return false
	}
	l.current++
	l.column++
	return true
}

func (l *Lexer) peek() byte {
	if l.isAtEnd() {
		return 0
	}
	return l.source[l.current]
}

func (l *Lexer) peekNext() byte {
	if l.current+1 >= len(l.source) {
		return 0
	}
	return l.source[l.current+1]
}

func (l *Lexer) peekOffset(offset int) byte {
	if l.current+offset >= len(l.source) {
		return 0
	}
	return l.source[l.current+offset]
}

func (l *Lexer) makeToken(tokenType TokenType, text string) Token {
	return Token{
		Type:   tokenType,
		Text:   text,
		Line:   l.line,
		Column: l.startCol,
	}
}

func (l *Lexer) errorToken(message string) Token {
	return Token{
		Type:   TokenError,
		Text:   message,
		Line:   l.line,
		Column: l.startCol,
	}
}

func isDigit(c byte) bool {
	return c >= '0' && c <= '9'
}

func isHexDigit(c byte) bool {
	return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')
}

func isAlpha(c byte) bool {
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_'
}

func isAlphaNumeric(c byte) bool {
	return isAlpha(c) || isDigit(c)
}
