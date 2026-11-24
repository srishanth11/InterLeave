package b08_dclinit

import "testing"

func TestBaselineDCL(t *testing.T) {
	reg := &Registry{}
	if !CallerExecuteRPC(reg) || !CallerExecuteRPC(reg) {
		t.Fatal("expected initialized config")
	}
}
