package runtime

import "fmt"

type MethodKind int

const (
	MethodKindBytecode MethodKind = iota
	MethodKindNative
)

type Method struct {
	Kind        MethodKind
	Closure     *ObjClosure
	Native      NativeFn
	IsConstruct bool
}

type ObjClass struct {
	Name         string
	Superclass   *ObjClass
	MetaClass    *ObjClass
	Methods      map[string]*Method
	StaticFields map[string]Value
	NumFields    int
}

func NewObjClass(name string, superclass *ObjClass) *ObjClass {
	return &ObjClass{
		Name:         name,
		Superclass:   superclass,
		Methods:      make(map[string]*Method),
		StaticFields: make(map[string]Value),
		NumFields:    0,
	}
}

func (c *ObjClass) Type() ObjType { return ObjTypeClass }
func (c *ObjClass) String() string {
	return c.Name
}

func (c *ObjClass) BindMethod(signature string, method *Method) {
	c.Methods[signature] = method
}

func (c *ObjClass) FindMethod(signature string) *Method {
	curr := c
	for curr != nil {
		if m, ok := curr.Methods[signature]; ok {
			return m
		}
		curr = curr.Superclass
	}
	return nil
}

type ObjInstance struct {
	Class  *ObjClass
	Fields []Value
}

func NewObjInstance(class *ObjClass) *ObjInstance {
	numFields := 0
	curr := class
	for curr != nil {
		numFields += curr.NumFields
		curr = curr.Superclass
	}
	fields := make([]Value, numFields)
	for i := range fields {
		fields[i] = NullValue()
	}
	return &ObjInstance{
		Class:  class,
		Fields: fields,
	}
}

func (o *ObjInstance) Type() ObjType { return ObjTypeInstance }
func (o *ObjInstance) String() string {
	return fmt.Sprintf("instance of %s", o.Class.Name)
}
