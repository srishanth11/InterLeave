package b14_poolpoison

import "testing"

func TestBaselinePool(t *testing.T) {
	p := NewSessionPool()
	if CallerHandleSession(p, "alice") != "alice" {
		t.Fatal("unexpected owner")
	}
}
