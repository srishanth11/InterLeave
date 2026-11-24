package b07_condlost

import "testing"

func TestBaselineQueue(t *testing.T) {
	q := NewTaskQueue()
	if CallerProcessBatch(q, 42) != 42 {
		t.Fatal("expected 42")
	}
}
