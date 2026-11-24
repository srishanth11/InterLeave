package b11_ctxleak

import "testing"

func TestBaselineCtx(t *testing.T) {
	w := &Worker{}
	if !CallerQueryService(w) {
		t.Fatal("expected ok")
	}
}
