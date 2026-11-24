package c02_safepool

import "testing"

func TestSafePool(t *testing.T) {
	if CallerRunPool([]int{1, 2, 3}) != 12 {
		t.Fatal("expected sum 12")
	}
}
