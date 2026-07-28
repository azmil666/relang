package bytecode

type Opcode byte

const (
	OpConstant Opcode = iota
	OpNull
	OpTrue
	OpFalse
	OpPop
	OpDup
	OpDefineGlobal
	OpGetGlobal
	OpSetGlobal
	OpGetLocal
	OpSetLocal
	OpGetUpvalue
	OpSetUpvalue
	OpGetField
	OpSetField
	OpGetStaticField
	OpSetStaticField
	OpJump
	OpJumpIfFalse
	OpLoop
	OpCall
	OpSuperCall
	OpClosure
	OpCloseUpvalue
	OpClass
	OpInherit
	OpMethod
	OpReturn
	OpConstruct
	OpImport
	OpJumpIfTrue
	OpIs
)
