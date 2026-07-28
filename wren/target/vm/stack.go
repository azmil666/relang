package vm

import "wren/runtime"

func (vm *VM) Push(val runtime.Value) {
	if vm.CurrentFiber != nil {
		vm.CurrentFiber.Push(val)
	}
}

func (vm *VM) Pop() runtime.Value {
	if vm.CurrentFiber != nil {
		return vm.CurrentFiber.Pop()
	}
	return runtime.NullValue()
}

func (vm *VM) Peek(distance int) runtime.Value {
	if vm.CurrentFiber != nil {
		return vm.CurrentFiber.Peek(distance)
	}
	return runtime.NullValue()
}
