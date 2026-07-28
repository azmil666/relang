package compiler

import "wren/runtime"

type FunctionType int

const (
	TypeScript FunctionType = iota
	TypeFn
	TypeMethod
	TypeInitializer
)

type Local struct {
	Name      string
	Depth     int
	IsUpvalue bool
	Slot      int
}

type Upvalue struct {
	Index   int
	IsLocal bool
}

type CompilerScope struct {
	Parent     *CompilerScope
	Fn         *runtime.ObjFn
	Type       FunctionType
	Locals     []Local
	Upvalues   []Upvalue
	ScopeDepth int
}

func NewCompilerScope(parent *CompilerScope, fnType FunctionType, fn *runtime.ObjFn) *CompilerScope {
	c := &CompilerScope{
		Parent:     parent,
		Fn:         fn,
		Type:       fnType,
		Locals:     make([]Local, 0),
		Upvalues:   make([]Upvalue, 0),
		ScopeDepth: 0,
	}
	// Slot 0 is reserved for receiver (this/self) or implicit call target
	c.Locals = append(c.Locals, Local{
		Name:      "",
		Depth:     0,
		IsUpvalue: false,
		Slot:      0,
	})
	return c
}

func (c *CompilerScope) AddLocal(name string) int {
	local := Local{
		Name:      name,
		Depth:     c.ScopeDepth,
		IsUpvalue: false,
		Slot:      len(c.Locals),
	}
	c.Locals = append(c.Locals, local)
	return local.Slot
}

func (c *CompilerScope) ResolveLocal(name string) int {
	for i := len(c.Locals) - 1; i >= 0; i-- {
		if c.Locals[i].Name == name {
			return c.Locals[i].Slot
		}
	}
	return -1
}

func (c *CompilerScope) AddUpvalue(index int, isLocal bool) int {
	for i, upvalue := range c.Upvalues {
		if upvalue.Index == index && upvalue.IsLocal == isLocal {
			return i
		}
	}
	c.Upvalues = append(c.Upvalues, Upvalue{Index: index, IsLocal: isLocal})
	c.Fn.UpvalueCount = len(c.Upvalues)
	return len(c.Upvalues) - 1
}

func (c *CompilerScope) ResolveUpvalue(name string) int {
	if c.Parent == nil {
		return -1
	}

	local := c.Parent.ResolveLocal(name)
	if local != -1 {
		c.Parent.Locals[local].IsUpvalue = true
		return c.AddUpvalue(local, true)
	}

	upvalue := c.Parent.ResolveUpvalue(name)
	if upvalue != -1 {
		return c.AddUpvalue(upvalue, false)
	}

	return -1
}
