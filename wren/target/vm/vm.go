package vm

import (
	"fmt"
	"path/filepath"
	"wren/bytecode"
	"wren/compiler"
	"wren/core"
	"wren/lexer"
	"wren/parser"
	"wren/runtime"
)

type VM struct {
	Core         *core.CoreClasses
	ModuleLoader *runtime.ModuleLoader
	CurrentFiber *ObjFiber
	HadError     bool
}

func NewVM(loader *runtime.ModuleLoader) *VM {
	if loader == nil {
		loader = runtime.NewModuleLoader(".")
	}
	vm := &VM{
		ModuleLoader: loader,
	}
	vm.Core = core.InitCore()
	vm.Core.CompileFn = vm.CompileString
	return vm
}

func (vm *VM) Interpret(moduleName, source string) error {
	mod := vm.ModuleLoader.GetModule(moduleName)
	if mod == nil {
		mod = runtime.NewObjModule(moduleName)
		vm.ModuleLoader.AddModule(moduleName, mod)
	}

	fn, err := vm.compileSource(mod, source)
	if err != nil {
		vm.HadError = true
		return err
	}

	closure := runtime.NewObjClosure(fn)
	fiber := NewObjFiber(closure)
	vm.CurrentFiber = fiber

	return vm.Run()
}

func (vm *VM) compileSource(mod *runtime.ObjModule, source string) (*runtime.ObjFn, error) {
	lex := lexer.NewLexer(source)
	pars := parser.NewParser(lex)
	stmts, err := pars.Parse()
	if err != nil {
		return nil, err
	}

	comp := compiler.NewCompiler(mod)
	return comp.Compile(stmts)
}

func (vm *VM) CompileString(source string) (*runtime.ObjClosure, error) {
	mod := vm.ModuleLoader.GetModule("<meta>")
	if mod == nil {
		mod = runtime.NewObjModule("<meta>")
		vm.ModuleLoader.AddModule("<meta>", mod)
	}
	fn, err := vm.compileSource(mod, source)
	if err != nil {
		return nil, err
	}
	return runtime.NewObjClosure(fn), nil
}

func (vm *VM) Run() error {
	for {
		if vm.CurrentFiber == nil || len(vm.CurrentFiber.Frames) == 0 {
			return nil
		}

		frame := &vm.CurrentFiber.Frames[len(vm.CurrentFiber.Frames)-1]
		chunk := frame.Closure.Fn.Chunk

		if frame.IP >= len(chunk.Code) {
			vm.CurrentFiber.Frames = vm.CurrentFiber.Frames[:len(vm.CurrentFiber.Frames)-1]
			if len(vm.CurrentFiber.Frames) == 0 {
				if vm.CurrentFiber.Caller != nil {
					vm.CurrentFiber = vm.CurrentFiber.Caller
				} else {
					return nil
				}
			}
			continue
		}

		op := bytecode.Opcode(chunk.Code[frame.IP])
		frame.IP++

		switch op {
		case bytecode.OpConstant:
			idx := int(chunk.Code[frame.IP])
			frame.IP++
			val := chunk.Constants[idx]
			vm.Push(vm.toValue(val))

		case bytecode.OpNull:
			vm.Push(runtime.NullValue())

		case bytecode.OpTrue:
			vm.Push(runtime.BoolValue(true))

		case bytecode.OpFalse:
			vm.Push(runtime.BoolValue(false))

		case bytecode.OpPop:
			vm.Pop()

		case bytecode.OpDup:
			val := vm.Peek(0)
			vm.Push(val)

		case bytecode.OpDefineGlobal:
			idx := int(chunk.Code[frame.IP])
			frame.IP++
			name := chunk.Constants[idx].(string)
			val := vm.Pop()
			frame.Closure.Fn.Module.Variables[name] = val

		case bytecode.OpGetGlobal:
			idx := int(chunk.Code[frame.IP])
			frame.IP++
			name := chunk.Constants[idx].(string)
			val, ok := frame.Closure.Fn.Module.Variables[name]
			if !ok {
				// Search in Core module / Builtins
				val = vm.getBuiltin(name)
			}
			vm.Push(val)

		case bytecode.OpSetGlobal:
			idx := int(chunk.Code[frame.IP])
			frame.IP++
			name := chunk.Constants[idx].(string)
			val := vm.Peek(0)
			frame.Closure.Fn.Module.Variables[name] = val

		case bytecode.OpGetLocal:
			slot := int(chunk.Code[frame.IP])
			frame.IP++
			val := vm.CurrentFiber.GetSlot(frame.StackBase + slot)
			vm.Push(val)

		case bytecode.OpSetLocal:
			slot := int(chunk.Code[frame.IP])
			frame.IP++
			val := vm.Peek(0)
			vm.CurrentFiber.SetSlot(frame.StackBase+slot, val)

		case bytecode.OpGetUpvalue:
			idx := int(chunk.Code[frame.IP])
			frame.IP++
			up := frame.Closure.Upvalues[idx]
			if up.IsClosed {
				vm.Push(up.Closed)
			} else {
				vm.Push(*up.Location)
			}

		case bytecode.OpSetUpvalue:
			idx := int(chunk.Code[frame.IP])
			frame.IP++
			val := vm.Peek(0)
			up := frame.Closure.Upvalues[idx]
			if up.IsClosed {
				up.Closed = val
			} else {
				*up.Location = val
			}

		case bytecode.OpJump:
			offset := (int(chunk.Code[frame.IP]) << 8) | int(chunk.Code[frame.IP+1])
			frame.IP += 2 + offset

		case bytecode.OpJumpIfFalse:
			offset := (int(chunk.Code[frame.IP]) << 8) | int(chunk.Code[frame.IP+1])
			frame.IP += 2
			cond := vm.Peek(0)
			if !cond.AsBool() {
				frame.IP += offset
			}

		case bytecode.OpJumpIfTrue:
			offset := (int(chunk.Code[frame.IP]) << 8) | int(chunk.Code[frame.IP+1])
			frame.IP += 2
			cond := vm.Peek(0)
			if cond.AsBool() {
				frame.IP += offset
			}

		case bytecode.OpLoop:
			offset := (int(chunk.Code[frame.IP]) << 8) | int(chunk.Code[frame.IP+1])
			frame.IP += 2
			frame.IP -= offset

		case bytecode.OpCall:
			sigIdx := int(chunk.Code[frame.IP])
			argCount := int(chunk.Code[frame.IP+1])
			frame.IP += 2

			signature := chunk.Constants[sigIdx].(string)
			if err := vm.callMethod(signature, argCount); err != nil {
				return err
			}

		case bytecode.OpSuperCall:
			sigIdx := int(chunk.Code[frame.IP])
			argCount := int(chunk.Code[frame.IP+1])
			frame.IP += 2
			signature := chunk.Constants[sigIdx].(string)
			if err := vm.callSuperMethod(frame, signature, argCount); err != nil {
				return err
			}

		case bytecode.OpClosure:
			fnIdx := int(chunk.Code[frame.IP])
			frame.IP++
			fn := chunk.Constants[fnIdx].(*runtime.ObjFn)
			closure := runtime.NewObjClosure(fn)

			for i := 0; i < fn.UpvalueCount; i++ {
				isLocal := chunk.Code[frame.IP] == 1
				index := int(chunk.Code[frame.IP+1])
				frame.IP += 2

				if isLocal {
					closure.Upvalues[i] = vm.CurrentFiber.CaptureUpvalue(&vm.CurrentFiber.Stack[frame.StackBase+index])
				} else {
					closure.Upvalues[i] = frame.Closure.Upvalues[index]
				}
			}
			vm.Push(runtime.ObjValue(closure))

		case bytecode.OpCloseUpvalue:
			vm.CurrentFiber.CloseUpvalues(len(vm.CurrentFiber.Stack) - 1)
			vm.Pop()

		case bytecode.OpConstruct:
			classVal := vm.CurrentFiber.Stack[frame.StackBase]
			if classVal.IsClass() {
				class := classVal.Obj.(*runtime.ObjClass)
				instance := runtime.NewObjInstance(class)
				vm.CurrentFiber.Stack[frame.StackBase] = runtime.ObjValue(instance)
			}

		case bytecode.OpClass:
			nameIdx := int(chunk.Code[frame.IP])
			frame.IP++
			name := chunk.Constants[nameIdx].(string)
			class := runtime.NewObjClass(name, vm.Core.ObjectClass)
			class.MetaClass = runtime.NewObjClass(name+" metaclass", vm.Core.ObjectClass.MetaClass)
			vm.Push(runtime.ObjValue(class))

		case bytecode.OpInherit:
			superVal := vm.Pop()
			classVal := vm.Peek(0)
			if superVal.IsClass() && classVal.IsClass() {
				superCls := superVal.Obj.(*runtime.ObjClass)
				subCls := classVal.Obj.(*runtime.ObjClass)
				subCls.Superclass = superCls
				if subCls.MetaClass != nil && superCls.MetaClass != nil {
					subCls.MetaClass.Superclass = superCls.MetaClass
				}
			}

		case bytecode.OpMethod:
			sigIdx := int(chunk.Code[frame.IP])
			isStatic := chunk.Code[frame.IP+1] == 1
			frame.IP += 2

			signature := chunk.Constants[sigIdx].(string)
			fnVal := vm.Pop()
			classVal := vm.Peek(0)

			if classVal.IsClass() && fnVal.IsClosure() {
				class := classVal.Obj.(*runtime.ObjClass)
				targetClass := class
				if isStatic {
					if class.MetaClass == nil {
						class.MetaClass = runtime.NewObjClass(class.Name+" metaclass", vm.Core.ObjectClass.MetaClass)
					}
					targetClass = class.MetaClass
				}
				targetClass.BindMethod(signature, &runtime.Method{
					Kind:    runtime.MethodKindBytecode,
					Closure: fnVal.Obj.(*runtime.ObjClosure),
				})
			}

		case bytecode.OpReturn:
			res := vm.Pop()
			vm.CurrentFiber.CloseUpvalues(frame.StackBase)

			// Truncate stack back to frame base
			vm.CurrentFiber.Stack = vm.CurrentFiber.Stack[:frame.StackBase]
			vm.CurrentFiber.Frames = vm.CurrentFiber.Frames[:len(vm.CurrentFiber.Frames)-1]

			if len(vm.CurrentFiber.Frames) == 0 {
				if vm.CurrentFiber.Caller != nil {
					vm.CurrentFiber = vm.CurrentFiber.Caller
					vm.CurrentFiber.Push(res)
				} else {
					return nil
				}
			} else {
				vm.Push(res)
			}

		case bytecode.OpIs:
			typeVal := vm.Pop()
			objVal := vm.Pop()
			result := vm.checkIs(objVal, typeVal)
			vm.Push(runtime.BoolValue(result))

		case bytecode.OpImport:
			pathIdx := int(chunk.Code[frame.IP])
			frame.IP++
			path := chunk.Constants[pathIdx].(string)

			resolved := vm.ModuleLoader.ResolveModule(frame.Closure.Fn.Module.Name, path)
			mod := vm.ModuleLoader.GetModule(resolved)
			if mod == nil {
				source, err := vm.ModuleLoader.LoadModuleSource(resolved)
				if err != nil {
					return fmt.Errorf("Could not import module '%s': %v", path, err)
				}
				mod = runtime.NewObjModule(resolved)
				vm.ModuleLoader.AddModule(resolved, mod)

				fn, err := vm.compileSource(mod, source)
				if err != nil {
					return err
				}
				closure := runtime.NewObjClosure(fn)
				vm.CurrentFiber.Push(runtime.ObjValue(closure))
				vm.CurrentFiber.Frames = append(vm.CurrentFiber.Frames, CallFrame{
					Closure:   closure,
					IP:        0,
					StackBase: len(vm.CurrentFiber.Stack) - 1,
				})
			} else {
				vm.Push(runtime.ObjValue(mod))
			}
		}
	}
}

func (vm *VM) callMethod(signature string, argCount int) error {
	args := make([]runtime.Value, argCount+1)
	for i := argCount; i >= 0; i-- {
		args[i] = vm.Pop()
	}

	receiver := args[0]
	class := vm.getClassForValue(receiver)

	if class != nil {
		method := class.FindMethod(signature)
		if method != nil {
			if method.Kind == runtime.MethodKindNative {
				res, err := method.Native(args)
				if err != nil {
					return err
				}
				vm.Push(res)
				return nil
			} else if method.Kind == runtime.MethodKindBytecode {
				vm.Push(receiver)
				for i := 1; i <= argCount; i++ {
					vm.Push(args[i])
				}
				vm.CurrentFiber.Frames = append(vm.CurrentFiber.Frames, CallFrame{
					Closure:   method.Closure,
					IP:        0,
					StackBase: len(vm.CurrentFiber.Stack) - (argCount + 1),
				})
				return nil
			}
		}
	}

	// Dynamic Fiber methods
	if receiver.IsFiber() {
		fiber := receiver.Obj.(*ObjFiber)
		if signature == "call()" || signature == "call(_)" {
			fiber.Caller = vm.CurrentFiber
			if argCount > 0 {
				fiber.Push(args[1])
			}
			vm.CurrentFiber = fiber
			return nil
		}
		if signature == "yield()" || signature == "yield(_)" {
			if vm.CurrentFiber.Caller != nil {
				res := runtime.NullValue()
				if argCount > 0 {
					res = args[1]
				}
				caller := vm.CurrentFiber.Caller
				vm.CurrentFiber = caller
				vm.CurrentFiber.Push(res)
			}
			return nil
		}
	}

	// Closure call(...) method
	if receiver.IsClosure() && (signature == "call()" || signature == "call(_)" || signature == "call(_,_)") {
		closure := receiver.Obj.(*runtime.ObjClosure)
		vm.Push(receiver)
		for i := 1; i <= argCount; i++ {
			vm.Push(args[i])
		}
		vm.CurrentFiber.Frames = append(vm.CurrentFiber.Frames, CallFrame{
			Closure:   closure,
			IP:        0,
			StackBase: len(vm.CurrentFiber.Stack) - (argCount + 1),
		})
		return nil
	}

	return fmt.Errorf("Undefined method '%s' for %s", signature, receiver.String())
}

func (vm *VM) getClassForValue(val runtime.Value) *runtime.ObjClass {
	switch val.Type {
	case runtime.ValNull:
		return vm.Core.ObjectClass
	case runtime.ValBool:
		return vm.Core.BoolClass
	case runtime.ValNum:
		return vm.Core.NumClass
	case runtime.ValObj:
		if val.IsString() {
			return vm.Core.StringClass
		}
		if val.IsList() {
			return vm.Core.ListClass
		}
		if val.IsMap() {
			return vm.Core.MapClass
		}
		if val.IsRange() {
			return vm.Core.RangeClass
		}
		if val.IsClass() {
			cls := val.Obj.(*runtime.ObjClass)
			if cls.MetaClass != nil {
				return cls.MetaClass
			}
			return vm.Core.ClassClass
		}
		if inst, ok := val.Obj.(*runtime.ObjInstance); ok {
			return inst.Class
		}
	}
	return vm.Core.ObjectClass
}

func (vm *VM) callSuperMethod(frame *CallFrame, signature string, argCount int) error {
	args := make([]runtime.Value, argCount+1)
	for i := argCount; i >= 0; i-- {
		args[i] = vm.Pop()
	}
	receiver := args[0]

	// Find the class that is the superclass of the current method's class
	// We search from the instance's class superclass chain
	var class *runtime.ObjClass
	if receiver.IsObj() {
		if inst, ok := receiver.Obj.(*runtime.ObjInstance); ok {
			class = inst.Class
		}
	}
	if class == nil {
		class = vm.getClassForValue(receiver)
	}

	// Skip to superclass
	if class != nil && class.Superclass != nil {
		class = class.Superclass
	}

	if class != nil {
		method := class.FindMethod(signature)
		if method != nil {
			if method.Kind == runtime.MethodKindNative {
				res, err := method.Native(args)
				if err != nil {
					return err
				}
				vm.Push(res)
				return nil
			} else if method.Kind == runtime.MethodKindBytecode {
				vm.Push(receiver)
				for i := 1; i <= argCount; i++ {
					vm.Push(args[i])
				}
				vm.CurrentFiber.Frames = append(vm.CurrentFiber.Frames, CallFrame{
					Closure:   method.Closure,
					IP:        0,
					StackBase: len(vm.CurrentFiber.Stack) - (argCount + 1),
				})
				return nil
			}
		}
	}
	return fmt.Errorf("Undefined super method '%s'", signature)
}

func (vm *VM) checkIs(val runtime.Value, typeVal runtime.Value) bool {
	if !typeVal.IsClass() {
		return false
	}
	targetClass := typeVal.Obj.(*runtime.ObjClass)
	valClass := vm.getClassForValue(val)
	// Walk the class hierarchy
	curr := valClass
	for curr != nil {
		if curr == targetClass {
			return true
		}
		curr = curr.Superclass
	}
	return false
}

func (vm *VM) valueToString(val runtime.Value) string {
	// Try to call toString method
	class := vm.getClassForValue(val)
	if class != nil {
		method := class.FindMethod("toString")
		if method != nil && method.Kind == runtime.MethodKindNative {
			res, err := method.Native([]runtime.Value{val})
			if err == nil && res.IsString() {
				return res.AsString()
			}
		}
	}
	return val.String()
}

func (vm *VM) getBuiltin(name string) runtime.Value {
	switch name {
	case "Object":
		return runtime.ObjValue(vm.Core.ObjectClass)
	case "Class":
		return runtime.ObjValue(vm.Core.ClassClass)
	case "Bool":
		return runtime.ObjValue(vm.Core.BoolClass)
	case "Num":
		return runtime.ObjValue(vm.Core.NumClass)
	case "String":
		return runtime.ObjValue(vm.Core.StringClass)
	case "List":
		return runtime.ObjValue(vm.Core.ListClass)
	case "Map":
		return runtime.ObjValue(vm.Core.MapClass)
	case "Range":
		return runtime.ObjValue(vm.Core.RangeClass)
	case "Fiber":
		return runtime.ObjValue(vm.Core.FiberClass)
	case "Fn":
		return runtime.ObjValue(vm.Core.FnClass)
	case "System":
		return runtime.ObjValue(vm.Core.SystemClass)
	case "Meta":
		return runtime.ObjValue(vm.Core.MetaClass)
	}
	return runtime.NullValue()
}

func (vm *VM) toValue(v interface{}) runtime.Value {
	if v == nil {
		return runtime.NullValue()
	}
	if b, ok := v.(bool); ok {
		return runtime.BoolValue(b)
	}
	if n, ok := v.(float64); ok {
		return runtime.NumValue(n)
	}
	if o, ok := v.(runtime.Obj); ok {
		return runtime.ObjValue(o)
	}
	return runtime.NullValue()
}

func GetRootDir(filePath string) string {
	if filePath == "" {
		return "."
	}
	return filepath.Dir(filePath)
}
