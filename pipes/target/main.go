package main

import (
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	cfg := LoadConfig()
	shouldSave := ParseFlags(&cfg)
	if shouldSave {
		_ = SaveConfig(cfg)
	}

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	EnableRawMode()
	defer RestoreTerminal()
	HideCursor()
	ClearScreen()

	eng := NewEngine(cfg)
	keyChan := StartInputListener()

	currentFPS := eng.Config.FPS
	ticker := time.NewTicker(time.Second / time.Duration(currentFPS))
	defer ticker.Stop()

running:
	for {
		select {
		case <-sigChan:
			break running
		case r := <-keyChan:
			if !eng.HandleKey(r) {
				break running
			}
			if eng.Config.FPS != currentFPS {
				currentFPS = eng.Config.FPS
				if currentFPS < 20 {
					currentFPS = 20
				}
				ticker.Reset(time.Second / time.Duration(currentFPS))
			}
		case <-ticker.C:
			if !eng.Update() {
				break running
			}
		}
	}
}
