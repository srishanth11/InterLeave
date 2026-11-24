package c01_safebank

import "testing"

func TestSafeBank(t *testing.T) {
	acc := NewSafeAccount(100)
	if !CallerSafeATM(acc, 80) || CallerSafeATM(acc, 80) {
		t.Fatal("safe bank failed")
	}
}
