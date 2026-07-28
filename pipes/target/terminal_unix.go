//go:build unix

package main

import (
	"fmt"
	"os"
	"syscall"
	"unsafe"
)

var origTermios syscall.Termios
var isRaw bool

func EnableRawMode() {
	fd := uintptr(syscall.Stdin)
	_, _, err := syscall.Syscall(syscall.SYS_IOCTL, fd, uintptr(syscall.TCGETS), uintptr(unsafe.Pointer(&origTermios)))
	if err != 0 {
		return
	}

	raw := origTermios
	raw.Lflag &^= (syscall.ECHO | syscall.ICANON | syscall.IEXTEN | syscall.ISIG)
	raw.Iflag &^= (syscall.IXON | syscall.ICRNL | syscall.BRKINT | syscall.INPCK | syscall.ISTRIP)
	raw.Oflag &^= syscall.OPOST

	syscall.Syscall(syscall.SYS_IOCTL, fd, uintptr(syscall.TCSETS), uintptr(unsafe.Pointer(&raw)))
	isRaw = true
}

func RestoreTerminal() {
	if isRaw {
		fd := uintptr(syscall.Stdin)
		syscall.Syscall(syscall.SYS_IOCTL, fd, uintptr(syscall.TCSETS), uintptr(unsafe.Pointer(&origTermios)))
		isRaw = false
	}
	fmt.Print("\033[?25h\033[0m")
}

type winsize struct {
	Row    uint16
	Col    uint16
	Xpixel uint16
	Ypixel uint16
}

func GetTerminalSize() (int, int) {
	ws := winsize{}
	fd := uintptr(syscall.Stdout)
	_, _, err := syscall.Syscall(syscall.SYS_IOCTL, fd, uintptr(syscall.TIOCGWINSZ), uintptr(unsafe.Pointer(&ws)))
	if err == 0 && ws.Col > 0 && ws.Row > 0 {
		return int(ws.Col), int(ws.Row)
	}
	return 80, 24
}
