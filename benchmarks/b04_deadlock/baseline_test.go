package b04_deadlock

import "testing"

func TestBaselineTransfer(t *testing.T) {
	w1, w2 := NewWallet(100), NewWallet(100)
	if !CallerPeerPayment(w1, w2, 40) || w1.balance != 60 || w2.balance != 140 {
		t.Fatal("baseline transfer failed")
	}
}
