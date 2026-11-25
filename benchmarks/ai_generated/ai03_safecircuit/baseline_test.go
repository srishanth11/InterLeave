package ai03_safecircuit

import "testing"

func TestSafeBreaker(t *testing.T) {
	cb := NewCircuitBreaker()
	cb.RecordFailure()
	cb.RecordFailure()
	if !cb.RecordFailure() {
		t.Fatal("expected open")
	}
}
