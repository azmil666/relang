//go:build windows

package main

import (
	"fmt"
	"os"
	"syscall"
	"unsafe"
)

var (
	kernel32                       = syscall.NewLazyDLL("kernel32.dll")
	procGetConsoleMode             = kernel32.NewProc("GetConsoleMode")
	procSetConsoleMode             = kernel32.NewProc("SetConsoleMode")
	procGetConsoleScreenBufferInfo = kernel32.NewProc("GetConsoleScreenBufferInfo")

	origMode uint32
	isRaw    bool
)

type coord struct {
	X int16
	Y int16
}

type smallRect struct {
	Left   int16
	Top    int16
	Right  int16
	Bottom int16
}

type consoleScreenBufferInfo struct {
	Size              coord
	CursorPosition    coord
	Attributes        uint16
	Window            smallRect
	MaximumWindowSize coord
}

func EnableRawMode() {
	handle := syscall.Handle(os.Stdin.Fd())
	var mode uint32
	ret, _, _ := procGetConsoleMode.Call(uintptr(handle), uintptr(unsafe.Pointer(&mode)))
	if ret != 0 {
		origMode = mode
		rawMode := (mode &^ (0x0002 | 0x0004)) | 0x0200
		procSetConsoleMode.Call(uintptr(handle), uintptr(rawMode))
		isRaw = true
	}
	outHandle := syscall.Handle(os.Stdout.Fd())
	var outMode uint32
	if ret, _, _ := procGetConsoleMode.Call(uintptr(outHandle), uintptr(unsafe.Pointer(&outMode))); ret != 0 {
		procSetConsoleMode.Call(uintptr(outHandle), uintptr(outMode|0x0004))
	}
}

func RestoreTerminal() {
	if isRaw {
		handle := syscall.Handle(os.Stdin.Fd())
		procSetConsoleMode.Call(uintptr(handle), uintptr(origMode))
		isRaw = false
	}
	fmt.Print("\033[?25h\033[0m")
}

func GetTerminalSize() (int, int) {
	outHandle := syscall.Handle(os.Stdout.Fd())
	var info consoleScreenBufferInfo
	ret, _, _ := procGetConsoleScreenBufferInfo.Call(uintptr(outHandle), uintptr(unsafe.Pointer(&info)))
	if ret != 0 {
		w := int(info.Window.Right - info.Window.Left + 1)
		h := int(info.Window.Bottom - info.Window.Top + 1)
		if w > 0 && h > 0 {
			return w, h
		}
	}
	return 80, 24
}
