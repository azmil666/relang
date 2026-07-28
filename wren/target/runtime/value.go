package runtime

import (
	"math"
	"strconv"
)

type ValueType int

const (
	ValNull ValueType = iota
	ValBool
	ValNum
	ValObj
)

type Value struct {
	Type ValueType
	Num  float64
	Bool bool
	Obj  Obj
}

func NullValue() Value {
	return Value{Type: ValNull}
}

func BoolValue(b bool) Value {
	return Value{Type: ValBool, Bool: b}
}

func NumValue(n float64) Value {
	return Value{Type: ValNum, Num: n}
}

func ObjValue(o Obj) Value {
	return Value{Type: ValObj, Obj: o}
}

func (v Value) IsNull() bool { return v.Type == ValNull }
func (v Value) IsBool() bool { return v.Type == ValBool }
func (v Value) IsNum() bool  { return v.Type == ValNum }
func (v Value) IsObj() bool  { return v.Type == ValObj }

func (v Value) IsString() bool {
	return v.IsObj() && v.Obj != nil && v.Obj.Type() == ObjTypeString
}

func (v Value) IsList() bool {
	return v.IsObj() && v.Obj != nil && v.Obj.Type() == ObjTypeList
}

func (v Value) IsMap() bool {
	return v.IsObj() && v.Obj != nil && v.Obj.Type() == ObjTypeMap
}

func (v Value) IsRange() bool {
	return v.IsObj() && v.Obj != nil && v.Obj.Type() == ObjTypeRange
}

func (v Value) IsClass() bool {
	return v.IsObj() && v.Obj != nil && v.Obj.Type() == ObjTypeClass
}

func (v Value) IsInstance() bool {
	return v.IsObj() && v.Obj != nil && v.Obj.Type() == ObjTypeInstance
}

func (v Value) IsFiber() bool {
	return v.IsObj() && v.Obj != nil && v.Obj.Type() == ObjTypeFiber
}

func (v Value) IsClosure() bool {
	return v.IsObj() && v.Obj != nil && v.Obj.Type() == ObjTypeClosure
}

func (v Value) AsString() string {
	if v.IsString() {
		return v.Obj.(*ObjString).Value
	}
	return v.String()
}

func (v Value) AsNum() float64 {
	if v.IsNum() {
		return v.Num
	}
	return 0
}

func (v Value) AsBool() bool {
	if v.IsBool() {
		return v.Bool
	}
	if v.IsNull() {
		return false
	}
	return true
}

func (v Value) String() string {
	switch v.Type {
	case ValNull:
		return "null"
	case ValBool:
		if v.Bool {
			return "true"
		}
		return "false"
	case ValNum:
		if math.IsNaN(v.Num) {
			return "nan"
		}
		if math.IsInf(v.Num, 1) {
			return "infinity"
		}
		if math.IsInf(v.Num, -1) {
			return "-infinity"
		}
		if v.Num == float64(int64(v.Num)) {
			return strconv.FormatInt(int64(v.Num), 10)
		}
		return strconv.FormatFloat(v.Num, 'g', -1, 64)
	case ValObj:
		if v.Obj == nil {
			return "null"
		}
		return v.Obj.String()
	}
	return "null"
}

func (v Value) Equals(other Value) bool {
	if v.Type != other.Type {
		return false
	}
	switch v.Type {
	case ValNull:
		return true
	case ValBool:
		return v.Bool == other.Bool
	case ValNum:
		return v.Num == other.Num
	case ValObj:
		if v.Obj == nil || other.Obj == nil {
			return v.Obj == other.Obj
		}
		if s1, ok := v.Obj.(*ObjString); ok {
			if s2, ok := other.Obj.(*ObjString); ok {
				return s1.Value == s2.Value
			}
		}
		return v.Obj == other.Obj
	}
	return false
}
