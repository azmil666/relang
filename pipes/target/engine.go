package main

import (
	"math/rand"
	"strings"
	"time"
)

type Engine struct {
	Config Config
	Pipes  []Pipe
	Width  int
	Height int
	Count  int
}

func NewEngine(cfg Config) *Engine {
	rand.Seed(time.Now().UnixNano())
	w, h := GetTerminalSize()
	eng := &Engine{
		Config: cfg,
		Width:  w,
		Height: h,
		Count:  0,
	}
	eng.initPipes()
	return eng
}

func (e *Engine) initPipes() {
	e.Pipes = make([]Pipe, 0, e.Config.Pipes)
	for i := 0; i < e.Config.Pipes; i++ {
		var dir Direction
		var x, y int

		if e.Config.RandomStart {
			dir = Direction(rand.Intn(4))
			if e.Width > 0 {
				x = rand.Intn(e.Width)
			}
			if e.Height > 0 {
				y = rand.Intn(e.Height)
			}
		} else {
			dir = DirUp
			x = e.Width / 2
			y = e.Height / 2
		}

		pipeType := e.Config.PipeTypes[0]
		if len(e.Config.PipeTypes) > 0 {
			pipeType = e.Config.PipeTypes[rand.Intn(len(e.Config.PipeTypes))]
		}

		color := e.Config.Colors[0]
		if len(e.Config.Colors) > 0 {
			color = e.Config.Colors[rand.Intn(len(e.Config.Colors))]
		}

		e.Pipes = append(e.Pipes, Pipe{
			X:        x,
			Y:        y,
			Dir:      dir,
			PipeType: pipeType,
			Color:    color,
		})
	}
}

func (e *Engine) Update() bool {
	newW, newH := GetTerminalSize()
	if newW != e.Width || newH != e.Height {
		e.Width, e.Height = newW, newH
		ClearScreen()
	}

	for i := range e.Pipes {
		pipe := &e.Pipes[i]
		oldDir := pipe.Dir
		startX, startY := pipe.X, pipe.Y

		nextX, nextY := StepPosition(startX, startY, oldDir)

		if nextX < 0 || nextX >= e.Width || nextY < 0 || nextY >= e.Height {
			if !e.Config.KeepStyle {
				if len(e.Config.PipeTypes) > 0 {
					pipe.PipeType = e.Config.PipeTypes[rand.Intn(len(e.Config.PipeTypes))]
				}
				if len(e.Config.Colors) > 0 {
					pipe.Color = e.Config.Colors[rand.Intn(len(e.Config.Colors))]
				}
			}
			if e.Width > 0 {
				nextX = (nextX%e.Width + e.Width) % e.Width
			}
			if e.Height > 0 {
				nextY = (nextY%e.Height + e.Height) % e.Height
			}
		}

		newDir := oldDir
		steady := e.Config.Steady
		if steady < 1 {
			steady = 1
		}
		if rand.Intn(steady) <= 1 {
			turn := 2*rand.Intn(2) - 1 // -1 or 1
			newDir = Direction((int(oldDir) + turn + 4) % 4)
		}

		ch := GetPipeChar(pipe.PipeType, oldDir, newDir)
		DrawChar(startX, startY, ch, pipe.Color, e.Config.Bold, e.Config.Color)

		pipe.X = nextX
		pipe.Y = nextY
		pipe.Dir = newDir
	}

	e.Count += len(e.Pipes)
	if e.Config.Limit > 0 && e.Count >= e.Config.Limit {
		ClearScreen()
		e.Count = 0
	}

	return true
}

func (e *Engine) HandleKey(r rune) bool {
	upper := rune(strings.ToUpper(string(r))[0])
	switch upper {
	case 'P':
		if e.Config.Steady < 15 {
			e.Config.Steady++
		}
	case 'O':
		if e.Config.Steady > 3 {
			e.Config.Steady--
		}
	case 'F':
		if e.Config.FPS < 100 {
			e.Config.FPS++
		}
	case 'D':
		if e.Config.FPS > 20 {
			e.Config.FPS--
		}
	case 'B':
		e.Config.Bold = !e.Config.Bold
	case 'C':
		e.Config.Color = !e.Config.Color
	case 'K':
		e.Config.KeepStyle = !e.Config.KeepStyle
	case '?', 27: // ESC
		return false
	}
	return true
}
