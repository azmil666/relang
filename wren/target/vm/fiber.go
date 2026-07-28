package vm

import (
	"fmt"
	"wren/runtime"
)

type FiberState int

const (
	FiberStateTry FiberState = iota
	FiberStateCall
	FiberStateYield
	FiberStateDone
)

type CallFrame struct {
	Closure   *runtime.ObjClosure
	IP        int
	StackBase int
}

type ObjFiber struct {
	Frames       []CallFrame
	Stack        []runtime.Value
	State        FiberState
	Caller       *ObjFiber
	ErrorValue   runtime.Value
	OpenUpvalues *runtime.ObjUpvalue
}

func NewObjFiber(closure *runtime.ObjClosure) *ObjFiber {
	f := &ObjFiber{
		Frames:     make([]CallFrame, 0, 8),
		Stack:      make([]runtime.Value, 0, 64),
		State:      FiberStateCall,
		Caller:     nil,
		ErrorValue: runtime.NullValue(),
	}
	if closure != nil {
		f.Push(runtime.ObjValue(closure))
		f.Frames = append(f.Frames, CallFrame{
			Closure:   closure,
			IP:        0,
			StackBase: 0,
		})
	}
	return f
}

func (f *ObjFiber) Type() runtime.ObjType { return runtime.ObjTypeFiber }
func (f *ObjFiber) String() string        { return "<fiber>" }

func (f *ObjFiber) Push(val runtime.Value) {
	f.Stack = append(f.Stack, val)
}

func (f *ObjFiber) Pop() runtime.Value {
	if len(f.Stack) == 0 {
		return runtime.NullValue()
	}
	val := f.Stack[len(f.Stack)-1]
	f.Stack = f.Stack[:len(f.Stack)-1]
	return val
}

func (f *ObjFiber) Peek(distance int) runtime.Value {
	idx := len(f.Stack) - 1 - distance
	if idx < 0 || idx >= len(f.Stack) {
		return runtime.NullValue()
	}
	return f.Stack[idx]
}

func (f *ObjFiber) SetSlot(idx int, val runtime.Value) {
	if idx >= 0 && idx < len(f.Stack) {
		f.Stack[idx] = val
	}
}

func (f *ObjFiber) GetSlot(idx int) runtime.Value {
	if idx >= 0 && idx < len(f.Stack) {
		return f.Stack[idx]
	}
	return runtime.NullValue()
}

func (f *ObjFiber) CloseUpvalues(lastSlot int) {
	for f.OpenUpvalues != nil && (f.OpenUpvalues.Location == nil || len(f.Stack) > lastSlot) {
		up := f.OpenUpvalues
		up.Closed = *up.Location
		up.Location = &up.Closed
		up.IsClosed = true
		f.OpenUpvalues = up.Next
	}
}

func (f *ObjFiber) CaptureUpvalue(local *runtime.Value) *runtime.ObjUpvalue {
	var prev *runtime.ObjUpvalue
	curr := f.OpenUpvalues

	for curr != nil && curr.Location == local {
		return curr
	}

	created := runtime.NewObjUpvalue(local)
	created.Next = curr
	if prev == nil {
		f.OpenUpvalues = created
	} else {
		prev.Next = created
	}
	return created
}

func (f *ObjFiber) PrintStackTrace() string {
	return fmt.Sprintf("Fiber Error: %s", f.ErrorValue.String())
}
