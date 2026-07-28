package main

import (
	"fmt"
	"os"
	"path/filepath"
	"wren/runtime"
	"wren/vm"
)

const WrenVersion = "0.4.0"

func main() {
	args := os.Args[1:]

	if len(args) == 1 && (args[0] == "--help" || args[0] == "-h") {
		fmt.Println("Usage: wren [file] [arguments...]")
		fmt.Println()
		fmt.Println("Optional arguments:")
		fmt.Println("  --help     Show command line usage")
		fmt.Println("  --version  Show version")
		os.Exit(0)
	}

	if len(args) == 1 && (args[0] == "--version" || args[0] == "-v") {
		fmt.Printf("wren %s\n", WrenVersion)
		os.Exit(0)
	}

	if len(args) == 0 {
		fmt.Printf("\\\\/\"-\n \\_/   wren v%s\n", WrenVersion)
		os.Exit(0)
	}

	filePath := args[0]
	absPath, err := filepath.Abs(filePath)
	if err != nil {
		absPath = filePath
	}

	data, err := os.ReadFile(filePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Could not find file \"%s\".\n", filePath)
		os.Exit(66)
	}

	rootDir := filepath.Dir(absPath)
	loader := runtime.NewModuleLoader(rootDir)
	v := vm.NewVM(loader)

	moduleName := filepath.Base(filePath)
	if ext := filepath.Ext(moduleName); ext != "" {
		moduleName = moduleName[:len(moduleName)-len(ext)]
	}

	err = v.Interpret(moduleName, string(data))
	if err != nil {
		if v.HadError {
			// Compile error
			fmt.Fprintf(os.Stderr, "%v\n", err)
			os.Exit(65)
		} else {
			// Runtime error
			fmt.Fprintf(os.Stderr, "%v\n", err)
			os.Exit(70)
		}
	}

	os.Exit(0)
}
