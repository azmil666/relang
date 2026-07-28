package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"encoding/json"
)

type Config struct {
	Pipes       int   `json:"pipes"`
	FPS         int   `json:"fps"`
	Steady      int   `json:"steady"`
	Limit       int   `json:"limit"`
	RandomStart bool  `json:"random_start"`
	Bold        bool  `json:"bold"`
	Color       bool  `json:"color"`
	KeepStyle   bool  `json:"keep_style"`
	Colors      []int `json:"colors"`
	PipeTypes   []int `json:"pipe_types"`
}

func DefaultConfig() Config {
	return Config{
		Pipes:       1,
		FPS:         75,
		Steady:      13,
		Limit:       2000,
		RandomStart: false,
		Bold:        true,
		Color:       true,
		KeepStyle:   false,
		Colors:      []int{1, 2, 3, 4, 5, 6, 7, 0},
		PipeTypes:   []int{0},
	}
}

func getConfigFilePath() string {
	homeDir, err := os.UserHomeDir()
	if err != nil {
		homeDir = "."
	}
	if runtime.GOOS == "windows" {
		return filepath.Join(homeDir, "AppData", "Local", "pipes-py", "config.json")
	}
	return filepath.Join(homeDir, ".config", "pipes-py", "config.json")
}

func LoadConfig() Config {
	cfg := DefaultConfig()
	path := getConfigFilePath()
	data, err := os.ReadFile(path)
	if err != nil {
		return cfg
	}

	var loaded Config
	if err := json.Unmarshal(data, &loaded); err == nil {
		if loaded.Pipes > 0 {
			cfg.Pipes = loaded.Pipes
		}
		if loaded.FPS >= 20 && loaded.FPS <= 100 {
			cfg.FPS = loaded.FPS
		}
		if loaded.Steady >= 3 && loaded.Steady <= 15 {
			cfg.Steady = loaded.Steady
		}
		if loaded.Limit >= 0 {
			cfg.Limit = loaded.Limit
		}
		cfg.RandomStart = loaded.RandomStart
		cfg.Bold = loaded.Bold
		cfg.Color = loaded.Color
		cfg.KeepStyle = loaded.KeepStyle
		if len(loaded.Colors) > 0 {
			cfg.Colors = loaded.Colors
		}
		if len(loaded.PipeTypes) > 0 {
			cfg.PipeTypes = loaded.PipeTypes
		}
	}
	return cfg
}

func SaveConfig(cfg Config) error {
	path := getConfigFilePath()
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0644)
}

func ParseFlags(cfg *Config) bool {
	pPipes := flag.Int("p", 0, "number of pipes")
	flag.IntVar(pPipes, "pipes", 0, "number of pipes")

	pFps := flag.Int("f", 0, "frames per second (20-100)")
	flag.IntVar(pFps, "fps", 0, "frames per second (20-100)")

	pSteady := flag.Int("s", 0, "steadiness (5-15)")
	flag.IntVar(pSteady, "steady", 0, "steadiness (5-15)")

	pLimit := flag.Int("r", -1, "character limit before reset")
	flag.IntVar(pLimit, "limit", -1, "character limit before reset")

	pRandom := flag.Bool("R", false, "random start")
	flag.BoolVar(pRandom, "random", false, "random start")

	pNoBold := flag.Bool("B", false, "disable bold")
	flag.BoolVar(pNoBold, "no-bold", false, "disable bold")

	pNoColor := flag.Bool("C", false, "disable color")
	flag.BoolVar(pNoColor, "no-color", false, "disable color")

	pPipeStyle := flag.Int("P", -1, "change pipe style (0-9)")
	flag.IntVar(pPipeStyle, "pipe-style", -1, "change pipe style (0-9)")

	pKeepStyle := flag.Bool("K", false, "keep style on wrap")
	flag.BoolVar(pKeepStyle, "keep-style", false, "keep style on wrap")

	pSaveConfig := flag.Bool("S", false, "save current settings as default")
	flag.BoolVar(pSaveConfig, "save-config", false, "save current settings as default")

	pVersion := flag.Bool("v", false, "print version")
	flag.BoolVar(pVersion, "version", false, "print version")

	flag.Parse()

	if *pVersion {
		fmt.Println("pipes-go v0.1.0")
		os.Exit(0)
	}

	if *pPipes > 0 {
		cfg.Pipes = *pPipes
	}
	if *pFps > 0 {
		if *pFps < 20 {
			cfg.FPS = 20
		} else if *pFps > 100 {
			cfg.FPS = 100
		} else {
			cfg.FPS = *pFps
		}
	}
	if *pSteady > 0 {
		if *pSteady < 5 {
			cfg.Steady = 5
		} else if *pSteady > 15 {
			cfg.Steady = 15
		} else {
			cfg.Steady = *pSteady
		}
	}
	if *pLimit >= 0 {
		cfg.Limit = *pLimit
	}
	if *pRandom {
		cfg.RandomStart = true
	}
	if *pNoBold {
		cfg.Bold = false
	}
	if *pNoColor {
		cfg.Color = false
	}
	if *pKeepStyle {
		cfg.KeepStyle = true
	}
	if *pPipeStyle >= 0 && *pPipeStyle <= 9 {
		cfg.PipeTypes = []int{*pPipeStyle}
	}

	return *pSaveConfig
}
