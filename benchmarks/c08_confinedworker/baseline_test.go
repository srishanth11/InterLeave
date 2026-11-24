package c08_confinedworker

import "testing"

func TestSafeConfinedStore(t *testing.T) {
	s := NewConfinedStore()
	if s.CallerIncrement("hits", 3) != 3 {
		t.Fatal("expected 3")
	}
}
