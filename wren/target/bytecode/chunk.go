package bytecode

type Chunk struct {
	Code      []byte
	Constants []interface{}
	Lines     []int
}

func NewChunk() *Chunk {
	return &Chunk{
		Code:      make([]byte, 0),
		Constants: make([]interface{}, 0),
		Lines:     make([]int, 0),
	}
}

func (c *Chunk) WriteByte(b byte, line int) {
	c.Code = append(c.Code, b)
	c.Lines = append(c.Lines, line)
}

func (c *Chunk) WriteOp(op Opcode, line int) {
	c.WriteByte(byte(op), line)
}

func (c *Chunk) AddConstant(value interface{}) int {
	c.Constants = append(c.Constants, value)
	return len(c.Constants) - 1
}

func (c *Chunk) WriteConstant(value interface{}, line int) {
	idx := c.AddConstant(value)
	if idx <= 255 {
		c.WriteOp(OpConstant, line)
		c.WriteByte(byte(idx), line)
	} else {
		// High index constant encoding if needed
		c.WriteOp(OpConstant, line)
		c.WriteByte(byte(idx&0xFF), line)
	}
}
