package core

import (
	"fmt"
	"math"
	"os"
	"runtime"
	"strconv"
	"strings"
	wruntime "wren/runtime"
)

type CoreClasses struct {
	ClassClass  *wruntime.ObjClass
	ObjectClass *wruntime.ObjClass
	BoolClass   *wruntime.ObjClass
	NumClass    *wruntime.ObjClass
	StringClass *wruntime.ObjClass
	ListClass   *wruntime.ObjClass
	MapClass    *wruntime.ObjClass
	RangeClass  *wruntime.ObjClass
	FiberClass  *wruntime.ObjClass
	FnClass     *wruntime.ObjClass
	SystemClass *wruntime.ObjClass
	MetaClass   *wruntime.ObjClass

	CompileFn func(source string) (*wruntime.ObjClosure, error)
}

func formatNum(n float64) string {
	if n == math.Trunc(n) && !math.IsInf(n, 0) && !math.IsNaN(n) {
		return strconv.FormatFloat(n, 'f', -1, 64)
	}
	if math.IsInf(n, 1) {
		return "infinity"
	}
	if math.IsInf(n, -1) {
		return "-infinity"
	}
	if math.IsNaN(n) {
		return "nan"
	}
	return strconv.FormatFloat(n, 'g', -1, 64)
}

func InitCore() *CoreClasses {
	cc := &CoreClasses{}

	cc.ObjectClass = wruntime.NewObjClass("Object", nil)
	cc.ClassClass = wruntime.NewObjClass("Class", cc.ObjectClass)

	cc.ObjectClass.MetaClass = wruntime.NewObjClass("Object metaclass", cc.ClassClass)
	cc.ClassClass.MetaClass = wruntime.NewObjClass("Class metaclass", cc.ClassClass)

	setupClass := func(name string) *wruntime.ObjClass {
		cls := wruntime.NewObjClass(name, cc.ObjectClass)
		cls.MetaClass = wruntime.NewObjClass(name+" metaclass", cc.ObjectClass.MetaClass)
		return cls
	}

	cc.BoolClass = setupClass("Bool")
	cc.NumClass = setupClass("Num")
	cc.StringClass = setupClass("String")
	cc.ListClass = setupClass("List")
	cc.MapClass = setupClass("Map")
	cc.RangeClass = setupClass("Range")
	cc.FiberClass = setupClass("Fiber")
	cc.FnClass = setupClass("Fn")
	cc.SystemClass = setupClass("System")
	cc.MetaClass = setupClass("Meta")

	// Object methods
	cc.ObjectClass.BindMethod("toString", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.ObjValue(wruntime.NewObjString(args[0].String())), nil
		},
	})
	cc.ObjectClass.BindMethod("type", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			v := args[0]
			switch v.Type {
			case wruntime.ValNull:
				return wruntime.ObjValue(cc.ObjectClass), nil
			case wruntime.ValBool:
				return wruntime.ObjValue(cc.BoolClass), nil
			case wruntime.ValNum:
				return wruntime.ObjValue(cc.NumClass), nil
			case wruntime.ValObj:
				if v.IsString() {
					return wruntime.ObjValue(cc.StringClass), nil
				}
				if v.IsList() {
					return wruntime.ObjValue(cc.ListClass), nil
				}
				if v.IsMap() {
					return wruntime.ObjValue(cc.MapClass), nil
				}
				if v.IsRange() {
					return wruntime.ObjValue(cc.RangeClass), nil
				}
				if v.IsClass() {
					return wruntime.ObjValue(cc.ClassClass), nil
				}
				if inst, ok := v.Obj.(*wruntime.ObjInstance); ok {
					return wruntime.ObjValue(inst.Class), nil
				}
			}
			return wruntime.ObjValue(cc.ObjectClass), nil
		},
	})
	cc.ObjectClass.BindMethod("same(_,_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(args[1].Equals(args[2])), nil
		},
	})
	cc.ObjectClass.BindMethod("==(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(args[0].Equals(args[1])), nil
		},
	})
	cc.ObjectClass.BindMethod("!=(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(!args[0].Equals(args[1])), nil
		},
	})
	cc.ObjectClass.BindMethod("!", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(!args[0].AsBool()), nil
		},
	})

	// Bool methods
	cc.BoolClass.BindMethod("toString", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			if args[0].AsBool() {
				return wruntime.ObjValue(wruntime.NewObjString("true")), nil
			}
			return wruntime.ObjValue(wruntime.NewObjString("false")), nil
		},
	})
	cc.BoolClass.BindMethod("!", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(!args[0].AsBool()), nil
		},
	})

	// Num methods
	cc.NumClass.BindMethod("toString", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.ObjValue(wruntime.NewObjString(formatNum(args[0].AsNum()))), nil
		},
	})
	cc.NumClass.BindMethod("+(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(args[0].AsNum() + args[1].AsNum()), nil
		},
	})
	cc.NumClass.BindMethod("-(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(args[0].AsNum() - args[1].AsNum()), nil
		},
	})
	cc.NumClass.BindMethod("*(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(args[0].AsNum() * args[1].AsNum()), nil
		},
	})
	cc.NumClass.BindMethod("/(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(args[0].AsNum() / args[1].AsNum()), nil
		},
	})
	cc.NumClass.BindMethod("%(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.Mod(args[0].AsNum(), args[1].AsNum())), nil
		},
	})
	cc.NumClass.BindMethod("<(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(args[0].AsNum() < args[1].AsNum()), nil
		},
	})
	cc.NumClass.BindMethod("<=(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(args[0].AsNum() <= args[1].AsNum()), nil
		},
	})
	cc.NumClass.BindMethod(">(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(args[0].AsNum() > args[1].AsNum()), nil
		},
	})
	cc.NumClass.BindMethod(">=(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(args[0].AsNum() >= args[1].AsNum()), nil
		},
	})
	cc.NumClass.BindMethod("==(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(args[0].Equals(args[1])), nil
		},
	})
	cc.NumClass.BindMethod("!=(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(!args[0].Equals(args[1])), nil
		},
	})
	cc.NumClass.BindMethod("-", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(-args[0].AsNum()), nil
		},
	})
	cc.NumClass.BindMethod("abs", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.Abs(args[0].AsNum())), nil
		},
	})
	cc.NumClass.BindMethod("sqrt", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.Sqrt(args[0].AsNum())), nil
		},
	})
	cc.NumClass.BindMethod("isInfinity", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(math.IsInf(args[0].AsNum(), 0)), nil
		},
	})
	cc.NumClass.BindMethod("isNan", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(math.IsNaN(args[0].AsNum())), nil
		},
	})
	cc.NumClass.BindMethod("isInteger", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			n := args[0].AsNum()
			return wruntime.BoolValue(n == math.Trunc(n) && !math.IsInf(n, 0) && !math.IsNaN(n)), nil
		},
	})
	cc.NumClass.BindMethod("floor", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.Floor(args[0].AsNum())), nil
		},
	})
	cc.NumClass.BindMethod("ceil", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.Ceil(args[0].AsNum())), nil
		},
	})
	cc.NumClass.BindMethod("round", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.Round(args[0].AsNum())), nil
		},
	})
	cc.NumClass.BindMethod("truncate", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.Trunc(args[0].AsNum())), nil
		},
	})
	cc.NumClass.BindMethod("sign", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			n := args[0].AsNum()
			if n > 0 {
				return wruntime.NumValue(1), nil
			} else if n < 0 {
				return wruntime.NumValue(-1), nil
			}
			return wruntime.NumValue(0), nil
		},
	})
	cc.NumClass.BindMethod("..(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.ObjValue(wruntime.NewObjRange(args[0].AsNum(), args[1].AsNum(), true)), nil
		},
	})
	cc.NumClass.BindMethod("...(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.ObjValue(wruntime.NewObjRange(args[0].AsNum(), args[1].AsNum(), false)), nil
		},
	})
	cc.NumClass.BindMethod("&(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(float64(int64(args[0].AsNum()) & int64(args[1].AsNum()))), nil
		},
	})
	cc.NumClass.BindMethod("|(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(float64(int64(args[0].AsNum()) | int64(args[1].AsNum()))), nil
		},
	})
	cc.NumClass.BindMethod("^(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(float64(int64(args[0].AsNum()) ^ int64(args[1].AsNum()))), nil
		},
	})
	cc.NumClass.BindMethod("<<(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(float64(int64(args[0].AsNum()) << uint(args[1].AsNum()))), nil
		},
	})
	cc.NumClass.BindMethod(">>(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(float64(int64(args[0].AsNum()) >> uint(args[1].AsNum()))), nil
		},
	})
	cc.NumClass.BindMethod("~", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(float64(^int64(args[0].AsNum()))), nil
		},
	})
	cc.NumClass.BindMethod("pow(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.Pow(args[0].AsNum(), args[1].AsNum())), nil
		},
	})
	cc.NumClass.BindMethod("log(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.Log(args[0].AsNum()) / math.Log(args[1].AsNum())), nil
		},
	})
	cc.NumClass.BindMethod("log2", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.Log2(args[0].AsNum())), nil
		},
	})
	cc.NumClass.MetaClass.BindMethod("infinity", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.Inf(1)), nil
		},
	})
	cc.NumClass.MetaClass.BindMethod("nan", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.NaN()), nil
		},
	})
	cc.NumClass.MetaClass.BindMethod("pi", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.Pi), nil
		},
	})
	cc.NumClass.MetaClass.BindMethod("tau", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.Pi * 2), nil
		},
	})
	cc.NumClass.MetaClass.BindMethod("largest", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.MaxFloat64), nil
		},
	})
	cc.NumClass.MetaClass.BindMethod("smallest", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(math.SmallestNonzeroFloat64), nil
		},
	})
	cc.NumClass.MetaClass.BindMethod("maxSafeInteger", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(9007199254740991), nil
		},
	})
	cc.NumClass.MetaClass.BindMethod("minSafeInteger", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(-9007199254740991), nil
		},
	})
	cc.NumClass.MetaClass.BindMethod("fromString(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			s := args[1].AsString()
			n, err := strconv.ParseFloat(s, 64)
			if err != nil {
				return wruntime.NullValue(), nil
			}
			return wruntime.NumValue(n), nil
		},
	})

	// String methods
	cc.StringClass.BindMethod("toString", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return args[0], nil
		},
	})
	cc.StringClass.BindMethod("+(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.ObjValue(wruntime.NewObjString(args[0].AsString() + args[1].AsString())), nil
		},
	})
	cc.StringClass.BindMethod("count", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			s := args[0].AsString()
			return wruntime.NumValue(float64(len(s))), nil
		},
	})
	cc.StringClass.BindMethod("[_]", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			str := args[0].AsString()
			if args[1].IsRange() {
				r := args[1].Obj.(*wruntime.ObjRange)
				start := int(r.From)
				if start < 0 { start += len(str) }
				end := int(r.To)
				if end < 0 { end += len(str) }
				
				step := 1
				if start > end { step = -1 }
				if !r.IsInclusive { end -= step }
				
				var result []byte
				if (step > 0 && start <= end) || (step < 0 && start >= end) {
					for i := start; ; i += step {
						if i >= 0 && i < len(str) {
							result = append(result, str[i])
						}
						if i == end { break }
					}
				}
				return wruntime.ObjValue(wruntime.NewObjString(string(result))), nil
			}
			idx := int(args[1].AsNum())
			if idx < 0 {
				idx = len(str) + idx
			}
			if idx < 0 || idx >= len(str) {
				return wruntime.NullValue(), fmt.Errorf("String index out of bounds")
			}
			return wruntime.ObjValue(wruntime.NewObjString(string(str[idx]))), nil
		},
	})
	cc.StringClass.BindMethod("bytes", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			str := args[0].AsString()
			elems := make([]wruntime.Value, len(str))
			for i := 0; i < len(str); i++ {
				elems[i] = wruntime.NumValue(float64(str[i]))
			}
			return wruntime.ObjValue(wruntime.NewObjList(elems)), nil
		},
	})
	cc.StringClass.BindMethod("codePoints", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			str := args[0].AsString()
			runes := []rune(str)
			elems := make([]wruntime.Value, len(runes))
			for i, r := range runes {
				elems[i] = wruntime.NumValue(float64(r))
			}
			return wruntime.ObjValue(wruntime.NewObjList(elems)), nil
		},
	})
	cc.StringClass.BindMethod("split(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			str := args[0].AsString()
			sep := args[1].AsString()
			var parts []string
			if sep == "" {
				for _, r := range str {
					parts = append(parts, string(r))
				}
			} else {
				parts = strings.Split(str, sep)
			}
			elems := make([]wruntime.Value, len(parts))
			for i, p := range parts {
				elems[i] = wruntime.ObjValue(wruntime.NewObjString(p))
			}
			return wruntime.ObjValue(wruntime.NewObjList(elems)), nil
		},
	})
	cc.StringClass.BindMethod("trim()", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.ObjValue(wruntime.NewObjString(strings.TrimSpace(args[0].AsString()))), nil
		},
	})
	cc.StringClass.BindMethod("trimEnd()", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.ObjValue(wruntime.NewObjString(strings.TrimRight(args[0].AsString(), " \t\n\r"))), nil
		},
	})
	cc.StringClass.BindMethod("startsWith(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(strings.HasPrefix(args[0].AsString(), args[1].AsString())), nil
		},
	})
	cc.StringClass.BindMethod("endsWith(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(strings.HasSuffix(args[0].AsString(), args[1].AsString())), nil
		},
	})
	cc.StringClass.BindMethod("contains(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(strings.Contains(args[0].AsString(), args[1].AsString())), nil
		},
	})
	cc.StringClass.BindMethod("indexOf(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			idx := strings.Index(args[0].AsString(), args[1].AsString())
			return wruntime.NumValue(float64(idx)), nil
		},
	})
	cc.StringClass.BindMethod("replace(_,_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			result := strings.ReplaceAll(args[0].AsString(), args[1].AsString(), args[2].AsString())
			return wruntime.ObjValue(wruntime.NewObjString(result)), nil
		},
	})
	cc.StringClass.BindMethod("==(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(args[0].AsString() == args[1].AsString()), nil
		},
	})
	cc.StringClass.BindMethod("!=(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(args[0].AsString() != args[1].AsString()), nil
		},
	})
	cc.StringClass.BindMethod("<(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(args[0].AsString() < args[1].AsString()), nil
		},
	})
	cc.StringClass.BindMethod("<=(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(args[0].AsString() <= args[1].AsString()), nil
		},
	})
	cc.StringClass.BindMethod(">(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(args[0].AsString() > args[1].AsString()), nil
		},
	})
	cc.StringClass.BindMethod(">=(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.BoolValue(args[0].AsString() >= args[1].AsString()), nil
		},
	})
	// iterate/iteratorValue for string (for loops)
	cc.StringClass.BindMethod("iterate(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			runes := []rune(args[0].AsString())
			if args[1].IsNull() {
				if len(runes) == 0 {
					return wruntime.BoolValue(false), nil
				}
				return wruntime.NumValue(0), nil
			}
			next := int(args[1].AsNum()) + 1
			if next >= len(runes) {
				return wruntime.BoolValue(false), nil
			}
			return wruntime.NumValue(float64(next)), nil
		},
	})
	cc.StringClass.BindMethod("iteratorValue(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			runes := []rune(args[0].AsString())
			idx := int(args[1].AsNum())
			if idx < 0 || idx >= len(runes) {
				return wruntime.NullValue(), nil
			}
			return wruntime.ObjValue(wruntime.NewObjString(string(runes[idx]))), nil
		},
	})

	// List methods
	cc.ListClass.MetaClass.BindMethod("new()", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.ObjValue(wruntime.NewObjList(make([]wruntime.Value, 0))), nil
		},
	})
	cc.ListClass.MetaClass.BindMethod("filled(_,_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			count := int(args[1].AsNum())
			val := args[2]
			elems := make([]wruntime.Value, count)
			for i := range elems {
				elems[i] = val
			}
			return wruntime.ObjValue(wruntime.NewObjList(elems)), nil
		},
	})
	cc.ListClass.BindMethod("toString", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			list := args[0].Obj.(*wruntime.ObjList)
			parts := make([]string, len(list.Elements))
			for i, e := range list.Elements {
				parts[i] = e.String()
			}
			return wruntime.ObjValue(wruntime.NewObjString("[" + strings.Join(parts, ", ") + "]")), nil
		},
	})
	cc.ListClass.BindMethod("add(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			list := args[0].Obj.(*wruntime.ObjList)
			list.Elements = append(list.Elements, args[1])
			return args[1], nil
		},
	})
	cc.ListClass.BindMethod("addAll(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			list := args[0].Obj.(*wruntime.ObjList)
			other := args[1].Obj.(*wruntime.ObjList)
			list.Elements = append(list.Elements, other.Elements...)
			return args[0], nil
		},
	})
	cc.ListClass.BindMethod("count", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			list := args[0].Obj.(*wruntime.ObjList)
			return wruntime.NumValue(float64(len(list.Elements))), nil
		},
	})
	cc.ListClass.BindMethod("isEmpty", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			list := args[0].Obj.(*wruntime.ObjList)
			return wruntime.BoolValue(len(list.Elements) == 0), nil
		},
	})
	cc.ListClass.BindMethod("clear()", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			list := args[0].Obj.(*wruntime.ObjList)
			list.Elements = make([]wruntime.Value, 0)
			return wruntime.NullValue(), nil
		},
	})
	cc.ListClass.BindMethod("[_]", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			list := args[0].Obj.(*wruntime.ObjList)
			if args[1].IsRange() {
				r := args[1].Obj.(*wruntime.ObjRange)
				start := int(r.From)
				if start < 0 { start += len(list.Elements) }
				end := int(r.To)
				if end < 0 { end += len(list.Elements) }
				
				step := 1
				if start > end { step = -1 }
				if !r.IsInclusive { end -= step }
				
				var result []wruntime.Value
				if (step > 0 && start <= end) || (step < 0 && start >= end) {
					for i := start; ; i += step {
						if i >= 0 && i < len(list.Elements) {
							result = append(result, list.Elements[i])
						}
						if i == end { break }
					}
				}
				return wruntime.ObjValue(wruntime.NewObjList(result)), nil
			}
			idx := int(args[1].AsNum())
			if idx < 0 {
				idx = len(list.Elements) + idx
			}
			if idx < 0 || idx >= len(list.Elements) {
				return wruntime.NullValue(), fmt.Errorf("Index out of bounds")
			}
			return list.Elements[idx], nil
		},
	})
	cc.ListClass.BindMethod("[_]=(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			list := args[0].Obj.(*wruntime.ObjList)
			idx := int(args[1].AsNum())
			if idx < 0 {
				idx = len(list.Elements) + idx
			}
			if idx < 0 || idx >= len(list.Elements) {
				return wruntime.NullValue(), fmt.Errorf("Index out of bounds")
			}
			list.Elements[idx] = args[2]
			return args[2], nil
		},
	})
	cc.ListClass.BindMethod("insert(_,_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			list := args[0].Obj.(*wruntime.ObjList)
			idx := int(args[1].AsNum())
			if idx < 0 {
				idx = len(list.Elements) + 1 + idx
			}
			val := args[2]
			list.Elements = append(list.Elements, wruntime.NullValue())
			copy(list.Elements[idx+1:], list.Elements[idx:])
			list.Elements[idx] = val
			return val, nil
		},
	})
	cc.ListClass.BindMethod("removeAt(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			list := args[0].Obj.(*wruntime.ObjList)
			idx := int(args[1].AsNum())
			if idx < 0 {
				idx = len(list.Elements) + idx
			}
			if idx < 0 || idx >= len(list.Elements) {
				return wruntime.NullValue(), fmt.Errorf("Index out of bounds")
			}
			val := list.Elements[idx]
			list.Elements = append(list.Elements[:idx], list.Elements[idx+1:]...)
			return val, nil
		},
	})
	cc.ListClass.BindMethod("contains(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			list := args[0].Obj.(*wruntime.ObjList)
			target := args[1]
			for _, e := range list.Elements {
				if e.Equals(target) {
					return wruntime.BoolValue(true), nil
				}
			}
			return wruntime.BoolValue(false), nil
		},
	})
	cc.ListClass.BindMethod("indexOf(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			list := args[0].Obj.(*wruntime.ObjList)
			target := args[1]
			for i, e := range list.Elements {
				if e.Equals(target) {
					return wruntime.NumValue(float64(i)), nil
				}
			}
			return wruntime.NumValue(-1), nil
		},
	})
	// List iterate/iteratorValue for for-loops
	cc.ListClass.BindMethod("iterate(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			list := args[0].Obj.(*wruntime.ObjList)
			if args[1].IsNull() {
				if len(list.Elements) == 0 {
					return wruntime.BoolValue(false), nil
				}
				return wruntime.NumValue(0), nil
			}
			next := int(args[1].AsNum()) + 1
			if next >= len(list.Elements) {
				return wruntime.BoolValue(false), nil
			}
			return wruntime.NumValue(float64(next)), nil
		},
	})
	cc.ListClass.BindMethod("iteratorValue(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			list := args[0].Obj.(*wruntime.ObjList)
			idx := int(args[1].AsNum())
			return list.Elements[idx], nil
		},
	})

	// Map methods
	cc.MapClass.MetaClass.BindMethod("new()", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.ObjValue(wruntime.NewObjMap()), nil
		},
	})
	cc.MapClass.BindMethod("count", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			m := args[0].Obj.(*wruntime.ObjMap)
			return wruntime.NumValue(float64(len(m.Entries))), nil
		},
	})
	cc.MapClass.BindMethod("isEmpty", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			m := args[0].Obj.(*wruntime.ObjMap)
			return wruntime.BoolValue(len(m.Entries) == 0), nil
		},
	})
	cc.MapClass.BindMethod("containsKey(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			m := args[0].Obj.(*wruntime.ObjMap)
			key := wruntime.MakeMapKey(args[1])
			_, ok := m.Entries[key]
			return wruntime.BoolValue(ok), nil
		},
	})
	cc.MapClass.BindMethod("remove(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			m := args[0].Obj.(*wruntime.ObjMap)
			key := wruntime.MakeMapKey(args[1])
			val, ok := m.Entries[key]
			if ok {
				delete(m.Entries, key)
				return val, nil
			}
			return wruntime.NullValue(), nil
		},
	})
	cc.MapClass.BindMethod("[_]", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			m := args[0].Obj.(*wruntime.ObjMap)
			key := wruntime.MakeMapKey(args[1])
			val, ok := m.Entries[key]
			if !ok {
				return wruntime.NullValue(), nil
			}
			return val, nil
		},
	})
	cc.MapClass.BindMethod("[_]=(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			m := args[0].Obj.(*wruntime.ObjMap)
			key := wruntime.MakeMapKey(args[1])
			m.Entries[key] = args[2]
			return args[2], nil
		},
	})
	// Map keys/values iteration
	cc.MapClass.BindMethod("keys", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			m := args[0].Obj.(*wruntime.ObjMap)
			keys := make([]wruntime.Value, 0, len(m.Entries))
			for k := range m.Entries {
				switch k.Type {
				case wruntime.ValObj:
					keys = append(keys, wruntime.ObjValue(wruntime.NewObjString(k.Str)))
				case wruntime.ValNum:
					keys = append(keys, wruntime.NumValue(k.Num))
				case wruntime.ValBool:
					keys = append(keys, wruntime.BoolValue(k.Bool))
				default:
					keys = append(keys, wruntime.NullValue())
				}
			}
			return wruntime.ObjValue(wruntime.NewObjList(keys)), nil
		},
	})
	cc.MapClass.BindMethod("values", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			m := args[0].Obj.(*wruntime.ObjMap)
			vals := make([]wruntime.Value, 0, len(m.Entries))
			for _, v := range m.Entries {
				vals = append(vals, v)
			}
			return wruntime.ObjValue(wruntime.NewObjList(vals)), nil
		},
	})

	// Range methods
	cc.RangeClass.BindMethod("from", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			r := args[0].Obj.(*wruntime.ObjRange)
			return wruntime.NumValue(r.From), nil
		},
	})
	cc.RangeClass.BindMethod("to", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			r := args[0].Obj.(*wruntime.ObjRange)
			return wruntime.NumValue(r.To), nil
		},
	})
	cc.RangeClass.BindMethod("isInclusive", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			r := args[0].Obj.(*wruntime.ObjRange)
			return wruntime.BoolValue(r.IsInclusive), nil
		},
	})
	cc.RangeClass.BindMethod("min", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			r := args[0].Obj.(*wruntime.ObjRange)
			if r.From < r.To {
				return wruntime.NumValue(r.From), nil
			}
			return wruntime.NumValue(r.To), nil
		},
	})
	cc.RangeClass.BindMethod("max", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			r := args[0].Obj.(*wruntime.ObjRange)
			if r.From > r.To {
				return wruntime.NumValue(r.From), nil
			}
			return wruntime.NumValue(r.To), nil
		},
	})
	cc.RangeClass.BindMethod("contains(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			r := args[0].Obj.(*wruntime.ObjRange)
			n := args[1].AsNum()
			if r.From <= r.To {
				if r.IsInclusive {
					return wruntime.BoolValue(n >= r.From && n <= r.To), nil
				}
				return wruntime.BoolValue(n >= r.From && n < r.To), nil
			}
			if r.IsInclusive {
				return wruntime.BoolValue(n >= r.To && n <= r.From), nil
			}
			return wruntime.BoolValue(n > r.To && n <= r.From), nil
		},
	})
	cc.RangeClass.BindMethod("toString", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.ObjValue(wruntime.NewObjString(args[0].String())), nil
		},
	})
	// Range iterate/iteratorValue for for-loops
	cc.RangeClass.BindMethod("iterate(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			r := args[0].Obj.(*wruntime.ObjRange)
			if args[1].IsNull() {
				return wruntime.NumValue(r.From), nil
			}
			cur := args[1].AsNum()
			var next float64
			if r.From <= r.To {
				next = cur + 1
				if r.IsInclusive {
					if next > r.To {
						return wruntime.BoolValue(false), nil
					}
				} else {
					if next >= r.To {
						return wruntime.BoolValue(false), nil
					}
				}
			} else {
				next = cur - 1
				if r.IsInclusive {
					if next < r.To {
						return wruntime.BoolValue(false), nil
					}
				} else {
					if next <= r.To {
						return wruntime.BoolValue(false), nil
					}
				}
			}
			return wruntime.NumValue(next), nil
		},
	})
	cc.RangeClass.BindMethod("iteratorValue(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return args[1], nil
		},
	})

	// Fn methods
	cc.FnClass.MetaClass.BindMethod("new(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			// args[1] should be the closure
			return args[1], nil
		},
	})

	// System static methods
	printValue := func(args []wruntime.Value) (wruntime.Value, error) {
		if len(args) < 2 {
			fmt.Println()
			return wruntime.NullValue(), nil
		}
		val := args[1]
		var text string
		if val.IsString() {
			text = val.AsString()
		} else {
			text = val.String()
		}
		fmt.Println(text)
		return wruntime.NullValue(), nil
	}

	cc.SystemClass.MetaClass.BindMethod("print(_)", &wruntime.Method{
		Kind:   wruntime.MethodKindNative,
		Native: printValue,
	})
	cc.SystemClass.MetaClass.BindMethod("print()", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			fmt.Println()
			return wruntime.NullValue(), nil
		},
	})
	cc.SystemClass.MetaClass.BindMethod("write(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			val := args[1]
			var text string
			if val.IsString() {
				text = val.AsString()
			} else {
				text = val.String()
			}
			fmt.Print(text)
			return wruntime.NullValue(), nil
		},
	})
	cc.SystemClass.MetaClass.BindMethod("clock", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			return wruntime.NumValue(0), nil
		},
	})
	cc.SystemClass.MetaClass.BindMethod("gc()", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			runtime.GC()
			return wruntime.NullValue(), nil
		},
	})
	cc.SystemClass.MetaClass.BindMethod("exit(_)", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			os.Exit(int(args[1].AsNum()))
			return wruntime.NullValue(), nil
		},
	})

	// Class/metaclass methods
	cc.ClassClass.BindMethod("name", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			if args[0].IsClass() {
				cls := args[0].Obj.(*wruntime.ObjClass)
				return wruntime.ObjValue(wruntime.NewObjString(cls.Name)), nil
			}
			return wruntime.ObjValue(wruntime.NewObjString("<class>")), nil
		},
	})
	cc.ClassClass.BindMethod("toString", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			if args[0].IsClass() {
				cls := args[0].Obj.(*wruntime.ObjClass)
				return wruntime.ObjValue(wruntime.NewObjString(cls.Name)), nil
			}
			return wruntime.ObjValue(wruntime.NewObjString("<class>")), nil
		},
	})
	cc.ClassClass.BindMethod("supertype", &wruntime.Method{
		Kind: wruntime.MethodKindNative,
		Native: func(args []wruntime.Value) (wruntime.Value, error) {
			if args[0].IsClass() {
				cls := args[0].Obj.(*wruntime.ObjClass)
				if cls.Superclass != nil {
					return wruntime.ObjValue(cls.Superclass), nil
				}
			}
			return wruntime.NullValue(), nil
		},
	})

	return cc
}

func FormatWrenString(text string) string {
	return strings.ReplaceAll(text, "\\n", "\n")
}
