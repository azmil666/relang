package runtime

import (
	"fmt"
	"strings"
	"wren/bytecode"
)

type ObjType int

const (
	ObjTypeString ObjType = iota
	ObjTypeList
	ObjTypeMap
	ObjTypeRange
	ObjTypeFn
	ObjTypeUpvalue
	ObjTypeClosure
	ObjTypeClass
	ObjTypeInstance
	ObjTypeFiber
	ObjTypeModule
	ObjTypeNativeFn
)

type Obj interface {
	Type() ObjType
	String() string
}

// ObjString
type ObjString struct {
	Value string
}

func NewObjString(val string) *ObjString {
	return &ObjString{Value: val}
}

func (o *ObjString) Type() ObjType { return ObjTypeString }
func (o *ObjString) String() string { return o.Value }

// ObjList
type ObjList struct {
	Elements []Value
}

func NewObjList(elements []Value) *ObjList {
	if elements == nil {
		elements = make([]Value, 0)
	}
	return &ObjList{Elements: elements}
}

func (o *ObjList) Type() ObjType { return ObjTypeList }
func (o *ObjList) String() string {
	parts := make([]string, len(o.Elements))
	for i, elem := range o.Elements {
		parts[i] = elem.String()
	}
	return "[" + strings.Join(parts, ", ") + "]"
}

// ObjMap
type MapKey struct {
	Type  ValueType
	Str   string
	Num   float64
	Bool  bool
	IsObj bool
	Obj   Obj
}

func MakeMapKey(val Value) MapKey {
	if val.IsString() {
		return MapKey{Type: ValObj, Str: val.AsString()}
	}
	return MapKey{Type: val.Type, Str: val.AsString(), Num: val.Num, Bool: val.Bool, IsObj: val.IsObj(), Obj: val.Obj}
}

type ObjMap struct {
	Entries map[MapKey]Value
}

func NewObjMap() *ObjMap {
	return &ObjMap{Entries: make(map[MapKey]Value)}
}

func (o *ObjMap) Type() ObjType { return ObjTypeMap }
func (o *ObjMap) String() string {
	return "{}"
}

// ObjRange
type ObjRange struct {
	From        float64
	To          float64
	IsInclusive bool
}

func NewObjRange(from, to float64, isInclusive bool) *ObjRange {
	return &ObjRange{From: from, To: to, IsInclusive: isInclusive}
}

func (o *ObjRange) Type() ObjType { return ObjTypeRange }
func (o *ObjRange) String() string {
	op := ".."
	if !o.IsInclusive {
		op = "..."
	}
	return fmt.Sprintf("%g%s%g", o.From, op, o.To)
}

// ObjFn
type ObjFn struct {
	Name         string
	Arity        int
	Chunk        *bytecode.Chunk
	UpvalueCount int
	Module       *ObjModule
}

func NewObjFn(name string, arity int, module *ObjModule) *ObjFn {
	return &ObjFn{
		Name:         name,
		Arity:        arity,
		Chunk:        bytecode.NewChunk(),
		UpvalueCount: 0,
		Module:       module,
	}
}

func (o *ObjFn) Type() ObjType { return ObjTypeFn }
func (o *ObjFn) String() string {
	if o.Name != "" {
		return fmt.Sprintf("<fn %s>", o.Name)
	}
	return "<fn>"
}

// ObjUpvalue
type ObjUpvalue struct {
	Location *Value
	Closed   Value
	IsClosed bool
	Next     *ObjUpvalue
}

func NewObjUpvalue(location *Value) *ObjUpvalue {
	return &ObjUpvalue{Location: location, IsClosed: false}
}

func (o *ObjUpvalue) Type() ObjType { return ObjTypeUpvalue }
func (o *ObjUpvalue) String() string { return "<upvalue>" }

// ObjClosure
type ObjClosure struct {
	Fn       *ObjFn
	Upvalues []*ObjUpvalue
}

func NewObjClosure(fn *ObjFn) *ObjClosure {
	return &ObjClosure{
		Fn:       fn,
		Upvalues: make([]*ObjUpvalue, fn.UpvalueCount),
	}
}

func (o *ObjClosure) Type() ObjType { return ObjTypeClosure }
func (o *ObjClosure) String() string { return o.Fn.String() }

// ObjModule
type ObjModule struct {
	Name      string
	Variables map[string]Value
	VarNames  []string
}

func NewObjModule(name string) *ObjModule {
	return &ObjModule{
		Name:      name,
		Variables: make(map[string]Value),
		VarNames:  make([]string, 0),
	}
}

func (o *ObjModule) Type() ObjType { return ObjTypeModule }
func (o *ObjModule) String() string { return fmt.Sprintf("<module %s>", o.Name) }

// Native function signature
type NativeFn func(args []Value) (Value, error)

type ObjNativeFn struct {
	Name string
	Fn   NativeFn
}

func NewObjNativeFn(name string, fn NativeFn) *ObjNativeFn {
	return &ObjNativeFn{Name: name, Fn: fn}
}

func (o *ObjNativeFn) Type() ObjType { return ObjTypeNativeFn }
func (o *ObjNativeFn) String() string { return fmt.Sprintf("<foreign fn %s>", o.Name) }
