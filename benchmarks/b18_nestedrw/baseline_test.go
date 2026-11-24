package b18_nestedrw

import "testing"

func TestBaselineRegistry(t *testing.T) {
	r := NewRegistry()
	if CallerResolveConfig(r) != 1 {
		t.Fatal("expected 1")
	}
}
