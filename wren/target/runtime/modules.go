package runtime

import (
	"os"
	"path/filepath"
	"strings"
)

type ModuleLoader struct {
	Modules map[string]*ObjModule
	RootDir string
}

func NewModuleLoader(rootDir string) *ModuleLoader {
	if rootDir == "" {
		rootDir = "."
	}
	return &ModuleLoader{
		Modules: make(map[string]*ObjModule),
		RootDir: rootDir,
	}
}

func (m *ModuleLoader) ResolveModule(importer string, name string) string {
	if strings.HasPrefix(name, "./") || strings.HasPrefix(name, "../") {
		baseDir := m.RootDir
		if importer != "" && importer != "<main>" && importer != "<repl>" {
			baseDir = filepath.Dir(importer)
		}
		resolved := filepath.Clean(filepath.Join(baseDir, name))
		return resolved
	}
	return name
}

func (m *ModuleLoader) GetModule(name string) *ObjModule {
	return m.Modules[name]
}

func (m *ModuleLoader) AddModule(name string, mod *ObjModule) {
	m.Modules[name] = mod
}

func (m *ModuleLoader) LoadModuleSource(resolvedPath string) (string, error) {
	path := resolvedPath
	if !strings.HasSuffix(path, ".wren") {
		path = path + ".wren"
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(data), nil
}
