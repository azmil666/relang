package main

import (
	"fmt"
	"os"
)

func HideCursor() {
	fmt.Print("\033[?25l")
}

func ShowCursor() {
	fmt.Print("\033[?25h\033[0m")
}

func ClearScreen() {
	fmt.Print("\033[2J\033[H")
}

func FormatAttr(color int, bold, enableColor bool) string {
	if !enableColor {
		if bold {
			return "\033[1m"
		}
		return "\033[0m"
	}
	ansiColor := 30 + (color % 8)
	if bold {
		return fmt.Sprintf("\033[1;%dm", ansiColor)
	}
	return fmt.Sprintf("\033[0;%dm", ansiColor)
}

func DrawChar(x, y int, r rune, color int, bold, enableColor bool) {
	attr := FormatAttr(color, bold, enableColor)
	// ANSI 1-based indexing for row (y+1) and column (x+1)
	fmt.Printf("\033[%d;%dH%s%c\033[0m", y+1, x+1, attr, r)
}

func StartInputListener() chan rune {
	ch := make(chan rune, 16)
	go func() {
		buf := make([]byte, 1)
		for {
			n, err := os.Stdin.Read(buf)
			if err != nil || n == 0 {
				break
			}
			ch <- rune(buf[0])
		}
	}()
	return ch
}
