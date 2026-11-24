package c07_lockedhelper

import "testing"

func TestSafeLedger(t *testing.T) {
	l := NewLedger(500, 500)
	if !CallerAtomicRebalance(l, 200) || CallerTotal(l) != 1000 {
		t.Fatal("unexpected ledger state")
	}
}
