package main

type Direction int

const (
	DirUp Direction = iota
	DirRight
	DirDown
	DirLeft
)

var PipeSetsRunes = [][]rune{
	[]rune("┃┏ ┓┛━┓  ┗┃┛┗ ┏━"),
	[]rune("│╭ ╮╯─╮  ╰│╯╰ ╭─"),
	[]rune("│┌ ┐┘─┐  └│┘└ ┌─"),
	[]rune("║╔ ╗╝═╗  ╚║╝╚ ╔═"),
	[]rune("|+ ++-+  +|++ +-"),
	[]rune("|/ \\ /-\\  \\|/\\ /-"),
	[]rune(".o ....  .... .o"),
	[]rune(".o oo.o  o.oo o."),
	[]rune("-\\ /\\|/  /-\\/ \\|"),
	[]rune("╿┍ ┑┚╼┒  ┕╽┙┖ ┎╾"),
}

type Pipe struct {
	X        int
	Y        int
	Dir      Direction
	PipeType int
	Color    int
}

func GetPipeChar(pipeType int, oldDir, newDir Direction) rune {
	if pipeType < 0 || pipeType >= len(PipeSetsRunes) {
		pipeType = 0
	}
	runes := PipeSetsRunes[pipeType]
	idx := int(oldDir)*4 + int(newDir)
	if idx >= 0 && idx < len(runes) {
		return runes[idx]
	}
	return '?'
}

func StepPosition(x, y int, dir Direction) (int, int) {
	if dir%2 != 0 { // DirRight (1) or DirLeft (3)
		x += -int(dir) + 2
	} else { // DirUp (0) or DirDown (2)
		y += int(dir) - 1
	}
	return x, y
}
